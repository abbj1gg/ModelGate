from app.services.quota_store import QuotaStore
from app.services.usage_store import UsageStore


def test_quota_store_tracks_current_month_usage(tmp_path) -> None:
    database_path = tmp_path / "quota.db"

    usage_store = UsageStore(str(database_path))
    quota_store = QuotaStore(str(database_path))

    quota_store.set_monthly_limit(
        key_id="key-001",
        monthly_token_limit=100,
    )

    usage_store.record(
        request_id="req-001",
        key_id="key-001",
        user_id="user-001",
        application_id="app-001",
        model="demo-chat",
        prompt_tokens=20,
        completion_tokens=30,
        total_tokens=50,
        latency_ms=100,
        status_code=200,
    )

    snapshot = quota_store.get_snapshot("key-001")

    assert snapshot["key_id"] == "key-001"
    assert snapshot["monthly_limit"] == 100
    assert snapshot["used_tokens"] == 50
    assert snapshot["remaining_tokens"] == 50
    assert snapshot["unlimited"] is False


def test_quota_store_without_limit_is_unlimited(tmp_path) -> None:
    database_path = tmp_path / "quota-unlimited.db"
    quota_store = QuotaStore(str(database_path))

    snapshot = quota_store.get_snapshot("key-without-limit")

    assert snapshot["monthly_limit"] is None
    assert snapshot["used_tokens"] == 0
    assert snapshot["remaining_tokens"] is None
    assert snapshot["unlimited"] is True


def test_quota_store_rejects_invalid_limit(tmp_path) -> None:
    database_path = tmp_path / "quota-invalid.db"
    quota_store = QuotaStore(str(database_path))

    try:
        quota_store.set_monthly_limit(
            key_id="key-001",
            monthly_token_limit=0,
        )
    except ValueError as exc:
        assert str(exc) == "monthly_token_limit must be positive"
    else:
        raise AssertionError("Expected ValueError")