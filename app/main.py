from datetime import datetime, timezone
from typing import Literal
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.providers.demo import DemoProvider
from app.providers.litellm_provider import LiteLLMProvider
from app.providers.reliable import (
    RetryPolicy,
    RetryingProvider,
)
from app.services.chat_service import ChatService, UnsupportedModelError
from app.core.rate_limit import enforce_rate_limit
from time import monotonic
from uuid import uuid4
from app.services.usage_store import get_usage_store
from app.core.quota import enforce_token_quota
from app.services.quota_store import get_quota_store
from app.services.audit_store import get_audit_store
from app.database.identity_store import IdentityStore
from app.core.security import get_identity_store
from app.core.security import (
    Principal,
    get_identity_store,
    require_api_key,
)
app = FastAPI(
    title="ModelGate",
    description="A lightweight multi-tenant LLM API gateway.",
    version="0.1.0",
)
# ====================== 审计中间件开始 ======================
def _audit_error_detail(status_code: int) -> str | None:
    if status_code < 400:
        return None
    descriptions = {
        401: "Authentication failed",
        403: "Permission denied",
        404: "Resource not found",
        422: "Request validation failed",
        429: "Rate limit or token quota exceeded",
    }
    if status_code >= 500:
        return "Internal server error"
    return descriptions.get(status_code, "Request failed")
def _record_audit(
    *,
    request: Request,
    status_code: int,
    latency_ms: int,
) -> None:
    principal = getattr(request.state, "principal", None)
    get_audit_store().record(
        request_id=request.state.request_id,
        method=request.method,
        path=request.url.path,
        status_code=status_code,
        error_detail=_audit_error_detail(status_code),
        key_id=getattr(principal, "key_id", None),
        user_id=getattr(principal, "user_id", None),
        application_id=getattr(
            principal,
            "application_id",
            None,
        ),
        latency_ms=latency_ms,
    )
@app.middleware("http")
async def audit_requests(request: Request, call_next):
    should_audit = request.url.path.startswith(
        ("/v1/", "/admin/")
    )
    if not should_audit:
        return await call_next(request)
    request.state.request_id = f"req_{uuid4().hex}"
    started_at = monotonic()
    try:
        response = await call_next(request)
    except Exception:
        latency_ms = int((monotonic() - started_at) * 1000)
        _record_audit(
            request=request,
            status_code=500,
            latency_ms=latency_ms,
        )
        raise
    latency_ms = int((monotonic() - started_at) * 1000)
    _record_audit(
        request=request,
        status_code=response.status_code,
        latency_ms=latency_ms,
    )
    response.headers["X-Request-ID"] = (
        request.state.request_id
    )
    principal = getattr(request.state, "principal", None)
    if (
        request.url.path == "/v1/chat/completions"
        and principal is not None
    ):
        quota = get_quota_store().get_snapshot(
            principal.key_id
        )
        response.headers["X-Quota-Used"] = str(
            quota["used_tokens"]
        )
        response.headers["X-Quota-Unlimited"] = str(
            quota["unlimited"]
        ).lower()
        if not bool(quota["unlimited"]):
            response.headers["X-Quota-Limit"] = str(
                quota["monthly_limit"]
            )
            response.headers["X-Quota-Remaining"] = str(
                quota["remaining_tokens"]
            )
    return response
# ====================== 审计中间件结束 ======================
# ========== 新增：_usage_value 工具函数（路由定义之前） ==========
def _usage_value(usage: object, field: str) -> int:
    if usage is None:
        return 0
    if isinstance(usage, dict):
        value = usage.get(field, 0)
    else:
        value = getattr(usage, field, 0)
    return int(value or 0)
# ==============================================================
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)
class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool = False
# ========== 【新增：3个Admin请求Model，放在ChatCompletionRequest后面】 ==========
class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
class CreateApplicationRequest(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    user_id: str
class CreateApiKeyRequest(BaseModel):
    user_id: str
    application_id: str
    allowed_models: list[str] = Field(min_length=1)
# ========== 新增配额更新请求模型 ==========
class QuotaUpdateRequest(BaseModel):
    monthly_token_limit: int = Field(gt=0)
# ============================================================================
settings = get_settings()
providers = {
    "demo-chat": DemoProvider(),
}
if settings.litellm_api_key:
    providers[settings.gateway_model_id] = RetryingProvider(
        provider=LiteLLMProvider(
            provider_model=settings.litellm_model,
            api_key=settings.litellm_api_key,
            api_base=settings.litellm_api_base,
            timeout=settings.litellm_timeout_seconds,
        ),
        policy=RetryPolicy(
            max_attempts=3,
            base_delay_seconds=0.25,
        ),
    )
chat_service = ChatService(providers=providers)
def require_bootstrap_admin(
    principal: Principal = Depends(enforce_rate_limit),
) -> Principal:
    allowed_admin_keys = {
        "key-development",
        "local-development",
    }
    if principal.key_id not in allowed_admin_keys:
        raise HTTPException(
            status_code=403,
            detail="Administrator permission required",
        )
    return principal
# 别名，满足 Depends(require_admin) 的写法
require_admin = require_bootstrap_admin
# ============================================================================
available_models = [
    {
        "id": model_id,
        "object": "model",
        "owned_by": "modelgate",
    }
    for model_id in providers
]
@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "modelgate",
        "version": app.version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
@app.get("/v1/models", tags=["models"])
async def list_models(
    principal: Principal = Depends(require_api_key),
) -> dict[str, object]:
    visible_models = [
        model
        for model in available_models
        if principal.can_use_model(model["id"])
    ]
    return {
        "object": "list",
        "data": visible_models,
    }
@app.get("/v1/whoami", tags=["identity"])
async def who_am_i(
    principal: Principal = Depends(require_api_key),
) -> dict[str, object]:
    return {
        "key_id": principal.key_id,
        "user_id": principal.user_id,
        "username": principal.username,
        "application_id": principal.application_id,
        "allowed_models": sorted(principal.allowed_models),
    }
# ========== 【新增：3个admin接口，放在whoami后面】 ==========
@app.post("/admin/users", status_code=201, tags=["admin"])
async def create_user(
    request: CreateUserRequest,
    _: Principal = Depends(require_bootstrap_admin),
) -> dict[str, str]:
    try:
        return get_identity_store().create_user(request.username)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
@app.post(
    "/admin/applications",
    status_code=201,
    tags=["admin"],
)
async def create_application(
    request: CreateApplicationRequest,
    _: Principal = Depends(require_bootstrap_admin),
) -> dict[str, str]:
    try:
        return get_identity_store().create_application(
            name=request.name,
            user_id=request.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
# ========= 新增 /admin/usage 用量汇总接口（管理员专用）=========
@app.get("/admin/usage", tags=["admin"])
def get_usage_summary(
    _admin: Principal = Depends(require_admin),
) -> list[dict[str, object]]:
    return get_usage_store().summarize()
@app.get("/admin/audit-logs", tags=["admin"])
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    failures_only: bool = False,
    _admin: Principal = Depends(require_admin),
) -> list[dict[str, object]]:
    return get_audit_store().list_recent(
        limit=limit,
        failures_only=failures_only,
    )
# ============================================================
# ========== 新增配额管理接口 ==========
@app.post(
    "/admin/api-keys/{key_id}/quota",
    tags=["admin"],
)
def set_api_key_quota(
    key_id: str,
    request: QuotaUpdateRequest,
    _admin: Principal = Depends(require_admin),
) -> dict[str, object]:
    get_quota_store().set_monthly_limit(
        key_id=key_id,
        monthly_token_limit=request.monthly_token_limit,
    )
    return get_quota_store().get_snapshot(key_id)
@app.get(
    "/admin/api-keys/{key_id}/quota",
    tags=["admin"],
)
def get_api_key_quota(
    key_id: str,
    _admin: Principal = Depends(require_admin),
) -> dict[str, object]:
    return get_quota_store().get_snapshot(key_id)
# ========= 新增：禁用、轮转密钥接口 =========
@app.post(
    "/admin/api-keys/{key_id}/disable",
    tags=["admin"],
)
def disable_api_key(
    key_id: str,
    _admin: Principal = Depends(require_admin),
) -> dict[str, str]:
    try:
        return get_identity_store().disable_api_key(key_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
@app.post(
    "/admin/api-keys/{key_id}/rotate",
    tags=["admin"],
)
def rotate_api_key(
    key_id: str,
    _admin: Principal = Depends(require_admin),
) -> dict[str, object]:
    try:
        return get_identity_store().rotate_api_key(key_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
# =====================================
@app.post(
    "/admin/api-keys",
    status_code=201,
    tags=["admin"],
)
async def create_api_key(
    request: CreateApiKeyRequest,
    _: Principal = Depends(require_bootstrap_admin),
) -> dict[str, object]:
    valid_models = {
        model["id"]
        for model in available_models
    }
    unknown_models = (
        set(request.allowed_models) - valid_models
    )
    if unknown_models:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown models: {sorted(unknown_models)}",
        )
    try:
        return get_identity_store().create_api_key(
            user_id=request.user_id,
            application_id=request.application_id,
            allowed_models=request.allowed_models,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
# ======================================================
@app.post("/v1/chat/completions", tags=["chat"])
async def chat_completions(
    request: ChatCompletionRequest,
    principal: Principal = Depends(enforce_token_quota),
):
    if not principal.can_use_model(request.model):
        raise HTTPException(
            status_code=403,
            detail=f"Model is not allowed for this API key: {request.model}",
        )
    try:
        # 新增用量统计逻辑，保留原有chat_service.complete全部参数
        request_id = f"req_{uuid4().hex}"
        started_at = monotonic()
        response = await chat_service.complete(
            model=request.model,
            messages=[
                message.model_dump()
                for message in request.messages
            ],
            temperature=request.temperature,
        )
        latency_ms = int((monotonic() - started_at) * 1000)
        # ========= 这里按你的要求修改 =========
        if isinstance(response, dict):
            usage = response.get("usage", {})
        else:
            usage = getattr(response, "usage", None)
        # =====================================
        get_usage_store().record(
            request_id=request_id,
            key_id=principal.key_id,
            user_id=principal.user_id,
            application_id=principal.application_id,
            model=request.model,
            prompt_tokens=_usage_value(usage, "prompt_tokens"),
            completion_tokens=_usage_value(usage, "completion_tokens"),
            total_tokens=_usage_value(usage, "total_tokens"),
            latency_ms=latency_ms,
            status_code=200,
        )
        return response
    except UnsupportedModelError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
