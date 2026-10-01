import pytest

from app.providers.base import ChatProvider
from app.providers.circuit_breaker import (
    CircuitBreakerProvider,
    CircuitState,
)
from app.providers.fallback import FallbackProvider
from app.providers.reliable import (
    RetryPolicy,
    RetryingProvider,
)


class FailingProvider(ChatProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> dict[str, object]:
        self.calls += 1
        raise TimeoutError("primary timeout")


class SuccessfulProvider(ChatProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> dict[str, object]:
        self.calls += 1

        return {
            "content": "fallback success",
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }


@pytest.mark.asyncio
async def test_retry_circuit_and_fallback_chain() -> None:
    primary_upstream = FailingProvider()
    fallback_upstream = SuccessfulProvider()

    primary = CircuitBreakerProvider(
        provider=RetryingProvider(
            provider=primary_upstream,
            policy=RetryPolicy(
                max_attempts=2,
                base_delay_seconds=0,
            ),
        ),
        failure_threshold=1,
        recovery_timeout_seconds=30,
    )

    provider = FallbackProvider(
        primary=primary,
        fallback=fallback_upstream,
    )

    first_result = await provider.complete(
        model="deepseek-chat",
        messages=[],
        temperature=0.2,
    )

    assert first_result["content"] == "fallback success"
    assert primary_upstream.calls == 2
    assert primary.state == CircuitState.OPEN
    assert fallback_upstream.calls == 1

    second_result = await provider.complete(
        model="deepseek-chat",
        messages=[],
        temperature=0.2,
    )

    assert second_result["content"] == "fallback success"

    # 熔断已打开，因此第二次请求不再调用主模型。
    assert primary_upstream.calls == 2
    assert fallback_upstream.calls == 2