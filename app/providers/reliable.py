import asyncio
from dataclasses import dataclass
from typing import Any

import litellm

from .base import ChatProvider


RETRYABLE_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    litellm.Timeout,
    litellm.APIConnectionError,
    litellm.RateLimitError,
    litellm.ServiceUnavailableError,
)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.25

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")

        if self.base_delay_seconds < 0:
            raise ValueError(
                "base_delay_seconds cannot be negative"
            )


class RetryingProvider(ChatProvider):
    def __init__(
        self,
        *,
        provider: ChatProvider,
        policy: RetryPolicy | None = None,
    ) -> None:
        self.provider = provider
        self.policy = policy or RetryPolicy()

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(self.policy.max_attempts):
            try:
                return await self.provider.complete(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                )
            except RETRYABLE_EXCEPTIONS as exc:
                last_error = exc

                if attempt == self.policy.max_attempts - 1:
                    raise

                delay = self.policy.base_delay_seconds * (
                    2**attempt
                )

                await asyncio.sleep(delay)

        raise RuntimeError(
            "Retry loop exited without a result"
        ) from last_error