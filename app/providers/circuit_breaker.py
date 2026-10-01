import asyncio
from enum import Enum
from time import monotonic
from typing import Any, Callable

from .base import ChatProvider
from .reliable import RETRYABLE_EXCEPTIONS


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(ConnectionError):
    """Raised when an upstream provider circuit is open."""


class CircuitBreakerProvider(ChatProvider):
    def __init__(
        self,
        *,
        provider: ChatProvider,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError(
                "failure_threshold must be positive"
            )

        if recovery_timeout_seconds <= 0:
            raise ValueError(
                "recovery_timeout_seconds must be positive"
            )

        self.provider = provider
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = (
            recovery_timeout_seconds
        )
        self.clock = clock

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        self._half_open_call_in_progress = False
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    async def _before_call(self) -> bool:
        async with self._lock:
            if self._state == CircuitState.OPEN:
                opened_at = self._opened_at

                if (
                    opened_at is not None
                    and self.clock() - opened_at
                    >= self.recovery_timeout_seconds
                ):
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise CircuitOpenError(
                        "Upstream provider circuit is open"
                    )

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_call_in_progress:
                    raise CircuitOpenError(
                        "Upstream provider recovery probe "
                        "is already running"
                    )

                self._half_open_call_in_progress = True
                return True

            return False

    async def _record_success(self) -> None:
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._opened_at = None
            self._half_open_call_in_progress = False

    async def _record_retryable_failure(
        self,
        *,
        was_half_open: bool,
    ) -> None:
        async with self._lock:
            self._half_open_call_in_progress = False

            if was_half_open:
                self._state = CircuitState.OPEN
                self._opened_at = self.clock()
                return

            self._failure_count += 1

            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = self.clock()

    async def _record_non_retryable_failure(
        self,
        *,
        was_half_open: bool,
    ) -> None:
        if not was_half_open:
            return

        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._opened_at = None
            self._half_open_call_in_progress = False

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> dict[str, Any]:
        was_half_open = await self._before_call()

        try:
            result = await self.provider.complete(
                model=model,
                messages=messages,
                temperature=temperature,
            )
        except RETRYABLE_EXCEPTIONS:
            await self._record_retryable_failure(
                was_half_open=was_half_open,
            )
            raise
        except Exception:
            await self._record_non_retryable_failure(
                was_half_open=was_half_open,
            )
            raise

        await self._record_success()
        return result