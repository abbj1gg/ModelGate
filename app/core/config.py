from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    demo_mode: bool = True
    gateway_model_id: str = "deepseek-chat"
    litellm_model: str = "deepseek/deepseek-chat"
    litellm_api_key: str | None = None
    litellm_api_base: str | None = None
    litellm_timeout_seconds: float = 30.0

    fallback_litellm_model: str | None = None
    fallback_litellm_api_key: str | None = None
    fallback_litellm_api_base: str | None = None
    fallback_litellm_timeout_seconds: float = 30.0

    # 熔断器配置（放在重试/备用模型配置附近，4空格缩进）
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_recovery_timeout_seconds: float = 30.0

    auth_enabled: bool = False
    dev_api_key: str = ""
    database_path: str = "data/modelgate.db"
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

@lru_cache
def get_settings() -> Settings:
    return Settings()
