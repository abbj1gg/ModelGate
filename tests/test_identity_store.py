import hashlib

import pytest

from app.database.identity_store import IdentityStore


def build_store(tmp_path) -> IdentityStore:
    store = IdentityStore(
        database_path=str(tmp_path / "identity.db"),
        dev_key_hash=hashlib.sha256(
            b"mg_dev_test"
        ).hexdigest(),
        gateway_model_id="deepseek-chat",
    )

    return store


def test_disable_api_key(tmp_path) -> None:
    store = build_store(tmp_path)

    user = store.create_user("disable-user")
    application = store.create_application(
        name="disable-app",
        user_id=user["id"],
    )
    api_key = store.create_api_key(
        user_id=user["id"],
        application_id=application["id"],
        allowed_models=["demo-chat"],
    )

    result = store.disable_api_key(api_key["id"])

    assert result["id"] == api_key["id"]
    assert result["status"] == "disabled"

    key_hash = hashlib.sha256(
        str(api_key["api_key"]).encode("utf-8")
    ).hexdigest()

    assert store.find_by_key_hash(key_hash) is None


def test_rotate_api_key_invalidates_old_key(tmp_path) -> None:
    store = build_store(tmp_path)

    user = store.create_user("rotate-user")
    application = store.create_application(
        name="rotate-app",
        user_id=user["id"],
    )
    old_key = store.create_api_key(
        user_id=user["id"],
        application_id=application["id"],
        allowed_models=["demo-chat"],
    )

    old_hash = hashlib.sha256(
        str(old_key["api_key"]).encode("utf-8")
    ).hexdigest()

    rotated = store.rotate_api_key(old_key["id"])

    assert rotated["id"] == old_key["id"]
    assert rotated["api_key"] != old_key["api_key"]
    assert rotated["status"] == "active"

    new_hash = hashlib.sha256(
        str(rotated["api_key"]).encode("utf-8")
    ).hexdigest()

    assert store.find_by_key_hash(old_hash) is None
    assert store.find_by_key_hash(new_hash) is not None


def test_cannot_rotate_disabled_api_key(tmp_path) -> None:
    store = build_store(tmp_path)

    user = store.create_user("disabled-rotate-user")
    application = store.create_application(
        name="disabled-rotate-app",
        user_id=user["id"],
    )
    api_key = store.create_api_key(
        user_id=user["id"],
        application_id=application["id"],
        allowed_models=["demo-chat"],
    )

    store.disable_api_key(api_key["id"])

    with pytest.raises(ValueError):
        store.rotate_api_key(api_key["id"])