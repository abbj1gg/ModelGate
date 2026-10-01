from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

ADMIN_HEADERS = {
    "Authorization": "Bearer mg_dev_123456_change_me",
}


def create_test_key() -> tuple[str, str]:
    suffix = uuid4().hex[:8]

    user_response = client.post(
        "/admin/users",
        headers=ADMIN_HEADERS,
        json={
            "username": f"lifecycle-user-{suffix}",
        },
    )
    assert user_response.status_code == 201
    user = user_response.json()

    application_response = client.post(
        "/admin/applications",
        headers=ADMIN_HEADERS,
        json={
            "name": f"lifecycle-app-{suffix}",
            "user_id": user["id"],
        },
    )
    assert application_response.status_code == 201
    application = application_response.json()

    key_response = client.post(
        "/admin/api-keys",
        headers=ADMIN_HEADERS,
        json={
            "user_id": user["id"],
            "application_id": application["id"],
            "allowed_models": ["demo-chat"],
        },
    )
    assert key_response.status_code == 201

    key = key_response.json()

    return key["id"], key["api_key"]


def test_disable_api_key_rejects_old_key() -> None:
    key_id, api_key = create_test_key()

    disable_response = client.post(
        f"/admin/api-keys/{key_id}/disable",
        headers=ADMIN_HEADERS,
    )

    assert disable_response.status_code == 200
    assert disable_response.json()["status"] == "disabled"

    whoami_response = client.get(
        "/v1/whoami",
        headers={
            "Authorization": f"Bearer {api_key}",
        },
    )

    assert whoami_response.status_code == 401


def test_rotate_api_key_invalidates_old_key() -> None:
    key_id, old_api_key = create_test_key()

    rotate_response = client.post(
        f"/admin/api-keys/{key_id}/rotate",
        headers=ADMIN_HEADERS,
    )

    assert rotate_response.status_code == 200

    rotated = rotate_response.json()
    new_api_key = rotated["api_key"]

    assert rotated["id"] == key_id
    assert new_api_key != old_api_key

    old_response = client.get(
        "/v1/whoami",
        headers={
            "Authorization": f"Bearer {old_api_key}",
        },
    )

    assert old_response.status_code == 401

    new_response = client.get(
        "/v1/whoami",
        headers={
            "Authorization": f"Bearer {new_api_key}",
        },
    )

    assert new_response.status_code == 200