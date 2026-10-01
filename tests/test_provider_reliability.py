import pytest

from app.providers.base import ChatProvider
from app.providers.reliable import (
    RetryPolicy,
    RetryingProvider,
)


class FlakyProvider(ChatProvider):
    def __init__(self, failures_before_success: int) -> None:
        self.failures_before_success = failures_before_success
        self.calls = 0

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> dict[str, object]:
        self.calls += 1

        if self.calls <= self.failures_before_success:
            raise TimeoutError("temporary upstream timeout")

        return {
            "content": "ok",
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }


@pytest.mark.asyncio
async def test_retrying_provider_recovers_after_timeout() -> None:
    provider = FlakyProvider(
        failures_before_success=2
    )

    retrying = RetryingProvider(
        provider=provider,
        policy=RetryPolicy(
            max_attempts=3,
            base_delay_seconds=0,
        ),
    )

    result = await retrying.complete(
        model="demo-chat",
        messages=[],
        temperature=0.2,
    )

    assert result["content"] == "ok"
    assert provider.calls == 3


@pytest.mark.asyncio
async def test_retrying_provider_stops_after_max_attempts() -> None:
    provider = FlakyProvider(
        failures_before_success=10
    )

    retrying = RetryingProvider(
        provider=provider,
        policy=RetryPolicy(
            max_attempts=3,
            base_delay_seconds=0,
        ),
    )

    with pytest.raises(TimeoutError):
        await retrying.complete(
            model="demo-chat",
            messages=[],
            temperature=0.2,
        )

    assert provider.calls == 3