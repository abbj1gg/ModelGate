from app.core.rate_limit import InMemoryRateLimiter


def test_rate_limiter_rejects_requests_after_limit() -> None:
    limiter = InMemoryRateLimiter(
        limit=2,
        window_seconds=60,
    )

    allowed, retry_after = limiter.check("key-a")
    assert allowed is True
    assert retry_after == 0

    allowed, retry_after = limiter.check("key-a")
    assert allowed is True
    assert retry_after == 0

    allowed, retry_after = limiter.check("key-a")
    assert allowed is False
    assert retry_after > 0


def test_rate_limiter_separates_api_keys() -> None:
    limiter = InMemoryRateLimiter(
        limit=1,
        window_seconds=60,
    )

    assert limiter.check("key-a")[0] is True
    assert limiter.check("key-a")[0] is False

    assert limiter.check("key-b")[0] is True