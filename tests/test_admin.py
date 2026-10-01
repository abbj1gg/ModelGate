from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

ADMIN_HEADERS = {
    "Authorization": "Bearer mg_dev_123456_change_me",
}


def test_create_user_application_and_api_key() -> None:
    suffix = uuid4().hex[:8]

    user_response = client.post(
        "/admin/users",
        headers=ADMIN_HEADERS,
        json={
            "username": f"finance-user-{suffix}",
        },
    )

    assert user_response.status_code == 201

    user = user_response.json()
    user_id = user["id"]

    application_response = client.post(
        "/admin/applications",
        headers=ADMIN_HEADERS,
        json={
            "name": f"finance-app-{suffix}",
            "user_id": user_id,
        },
    )

    assert application_response.status_code == 201

    application = application_response.json()
    application_id = application["id"]

    key_response = client.post(
        "/admin/api-keys",
        headers=ADMIN_HEADERS,
        json={
            "user_id": user_id,
            "application_id": application_id,
            "allowed_models": ["demo-chat"],
        },
    )

    assert key_response.status_code == 201

    api_key = key_response.json()["api_key"]

    whoami_response = client.get(
        "/v1/whoami",
        headers={
            "Authorization": f"Bearer {api_key}",
        },
    )

    assert whoami_response.status_code == 200

    identity = whoami_response.json()

    assert identity["user_id"] == user_id
    assert identity["application_id"] == application_id
    assert identity["allowed_models"] == ["demo-chat"]