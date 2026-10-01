import pytest
from fastapi import HTTPException
from app.core.quota import enforce_token_quota
from app.core.security import Principal

class FakeQuotaStore:
    def __init__(self, snapshot: dict[str, object]) -> None:
        self.snapshot = snapshot
    def get_snapshot(self, key_id: str) -> dict[str, object]:
        return self.snapshot

def make_principal() -> Principal:
    return Principal(
        key_id="key-quota-test",
        user_id="user-quota-test",
        username="quota-user",
        application_id="app-quota-test",
        allowed_models=frozenset({"demo-chat"}),
    )

def test_unlimited_key_is_allowed(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.quota.get_quota_store",
        lambda: FakeQuotaStore(
            {
                "key_id": "key-quota-test",
                "monthly_limit": None,
                "used_tokens": 0,
                "remaining_tokens": None,
                "unlimited": True,
            }
        ),
    )
    principal = enforce_token_quota(
        make_principal()
    )
    assert principal.key_id == "key-quota-test"

def test_exhausted_key_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.quota.get_quota_store",
        lambda: FakeQuotaStore(
            {
                "key_id": "key-quota-test",
                "monthly_limit": 100,
                "used_tokens": 100,
                "remaining_tokens": 0,
                "unlimited": False,
            }
        ),
    )
    with pytest.raises(HTTPException) as error:
        enforce_token_quota(
            make_principal()
        )
    assert error.value.status_code == 429
    assert error.value.detail == "Token quota exceeded"
    assert error.value.headers["X-Quota-Limit"] == "100"
    assert error.value.headers["X-Quota-Used"] == "100"
    assert error.value.headers["X-Quota-Remaining"] == "0"
