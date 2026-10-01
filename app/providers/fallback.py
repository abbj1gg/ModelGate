from typing import Any

from .base import ChatProvider
from .reliable import RETRYABLE_EXCEPTIONS


class FallbackProvider(ChatProvider):
    def __init__(
        self,
        *,
        primary: ChatProvider,
        fallback: ChatProvider,
    ) -> None:
        self.primary = primary
        self.fallback = fallback

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> dict[str, Any]:
        try:
            return await self.primary.complete(
                model=model,
                messages=messages,
                temperature=temperature,
            )
        except RETRYABLE_EXCEPTIONS:
            return await self.fallback.complete(
                model=model,
                messages=messages,
                temperature=temperature,
            )