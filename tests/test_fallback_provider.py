import pytest

from app.providers.base import ChatProvider
from app.providers.fallback import FallbackProvider


class SuccessfulProvider(ChatProvider):
    def __init__(self, content: str) -> None:
        self.content = content
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
            "content": self.content,
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }


class TimeoutProvider(ChatProvider):
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
        raise TimeoutError("primary provider timeout")


@pytest.mark.asyncio
async def test_fallback_provider_uses_fallback_after_timeout() -> None:
    primary = TimeoutProvider()
    fallback = SuccessfulProvider("fallback response")

    provider = FallbackProvider(
        primary=primary,
        fallback=fallback,
    )

    result = await provider.complete(
        model="deepseek-chat",
        messages=[],
        temperature=0.2,
    )

    assert result["content"] == "fallback response"
    assert primary.calls == 1
    assert fallback.calls == 1


@pytest.mark.asyncio
async def test_fallback_provider_does_not_call_fallback_on_success() -> None:
    primary = SuccessfulProvider("primary response")
    fallback = SuccessfulProvider("fallback response")

    provider = FallbackProvider(
        primary=primary,
        fallback=fallback,
    )

    result = await provider.complete(
        model="deepseek-chat",
        messages=[],
        temperature=0.2,
    )

    assert result["content"] == "primary response"
    assert primary.calls == 1
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_fallback_provider_propagates_fallback_error() -> None:
    primary = TimeoutProvider()
    fallback = TimeoutProvider()

    provider = FallbackProvider(
        primary=primary,
        fallback=fallback,
    )

    with pytest.raises(TimeoutError):
        await provider.complete(
            model="deepseek-chat",
            messages=[],
            temperature=0.2,
        )

    assert primary.calls == 1
    assert fallback.calls == 1