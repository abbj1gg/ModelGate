# ModelGate
ModelGate 是一个基于 FastAPI、LiteLLM 和 SQLite 实现的多租户大模型 API 网关，兼容 OpenAI Chat Completions 风格接口。
## 已实现功能
- API Key 鉴权
- 用户、应用和 API Key 管理
- 模型访问权限控制
- API Key 禁用与轮换
- 按 API Key 请求限流
- 月度 Token 配额
- 配额耗尽返回 HTTP 429
- 调用日志和 Token 用量统计
- 失败请求审计日志
- 配额响应头
- Swagger/OpenAPI 文档
- Demo Provider 与 LiteLLM Provider
- SQLite 持久化
- Docker Compose 配置
- 上游模型指数退避重试
- 可配置的备用模型故障降级

- 熔断器与半开恢复探测


## 系统架构
```mermaid
flowchart LR
    Client[OpenAI兼容客户端] --> Gateway[FastAPI Gateway]
    Gateway --> Auth[API Key鉴权]
    Auth --> Limit[请求限流]
    Limit --> Quota[Token配额检查]
    Quota --> Permission[模型权限检查]
    Permission --> Provider[Provider抽象层]
    Provider --> Demo[Demo Provider]
    Provider --> LiteLLM[LiteLLM Provider]
    LiteLLM --> Model[OpenAI兼容模型服务]
    Gateway --> SQLite[(SQLite)]
    SQLite --> Usage[用量统计]
    SQLite --> Audit[审计日志]


## 环境变量

复制 `.env.example` 为 `.env`，再根据实际环境填写：

```text
DEMO_MODE=true

GATEWAY_MODEL_ID=deepseek-chat
LITELLM_MODEL=deepseek/deepseek-chat
LITELLM_API_KEY=
LITELLM_API_BASE=https://api.deepseek.com
LITELLM_TIMEOUT_SECONDS=60

# Optional fallback provider
FALLBACK_LITELLM_MODEL=
FALLBACK_LITELLM_API_KEY=
FALLBACK_LITELLM_API_BASE=
FALLBACK_LITELLM_TIMEOUT_SECONDS=30

# Circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS=30

AUTH_ENABLED=true
DEV_API_KEY=replace-with-a-random-admin-key
DATABASE_PATH=data/modelgate.db

RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
```

说明：

- `LITELLM_API_KEY` 用于上游模型服务；
- `FALLBACK_LITELLM_*` 用于可选备用模型；
- `FALLBACK_LITELLM_MODEL` 和 `FALLBACK_LITELLM_API_KEY` 都为空时，不启用备用模型；
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD` 表示连续失败多少次后打开熔断；
- `CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS` 表示熔断后等待多少秒再进行恢复探测。

不要将真实 API Key 提交到 Git。