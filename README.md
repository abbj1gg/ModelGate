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
