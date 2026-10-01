from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from time import monotonic

from fastapi import Depends, HTTPException, status

from app.core.config import get_settings
from app.core.security import Principal, require_api_key


@dataclass
class _Bucket:
    window_started: float
    count: int = 0


class InMemoryRateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.limit = limit
        self.window_seconds = window_seconds
        self._buckets: dict[str, _Bucket] = {}
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, int]:
        now = monotonic()

        with self._lock:
            bucket = self._buckets.get(key)

            if bucket is None or now - bucket.window_started >= self.window_seconds:
                self._buckets[key] = _Bucket(
                    window_started=now,
                    count=1,
                )
                return True, 0

            bucket.count += 1

            if bucket.count > self.limit:
                retry_after = max(
                    1,
                    int(self.window_seconds - (now - bucket.window_started)) + 1,
                )
                return False, retry_after

            return True, 0


@lru_cache
def get_rate_limiter() -> InMemoryRateLimiter:
    settings = get_settings()

    return InMemoryRateLimiter(
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )


def enforce_rate_limit(
    principal: Principal = Depends(require_api_key),
) -> Principal:
    allowed, retry_after = get_rate_limiter().check(principal.key_id)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    return principal