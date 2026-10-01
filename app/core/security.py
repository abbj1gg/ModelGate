import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import get_settings
from app.database.identity_store import IdentityStore

# ========== 在Principal类之前新增 ==========
bearer_scheme = HTTPBearer(auto_error=False)
# =========================================

@dataclass(frozen=True)
class Principal:
    key_id: str
    user_id: str
    username: str
    application_id: str
    allowed_models: frozenset[str]
    def can_use_model(self, model: str) -> bool:
        return "*" in self.allowed_models or model in self.allowed_models


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


@lru_cache
def get_identity_store() -> IdentityStore:
    settings = get_settings()
    return IdentityStore(
        database_path=settings.database_path,
        dev_key_hash=hash_api_key(settings.dev_api_key),
        gateway_model_id=settings.gateway_model_id,
    )


# ========== 修改后的 require_api_key ==========
def require_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    settings = get_settings()
    if not settings.auth_enabled:
        principal = Principal(
            key_id="local-development",
            user_id="local-user",
            username="local-user",
            application_id="app-local",
            allowed_models=frozenset({"*"}),
        )
        request.state.principal = principal
        return principal

    if not settings.dev_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gateway API key is not configured",
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided_key = credentials.credentials
    provided_hash = hash_api_key(provided_key)
    record = get_identity_store().find_by_key_hash(provided_hash)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is inactive or unknown",
            headers={"WWW-Authenticate": "Bearer"},
        )
    principal = Principal(
        key_id=record["key_id"],
        user_id=record["user_id"],
        username=record["username"],
        application_id=record["application_id"],
        allowed_models=frozenset(
            json.loads(record["allowed_models"])
        ),
    )
    request.state.principal = principal
    return principal
