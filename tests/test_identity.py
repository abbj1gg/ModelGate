from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer mg_dev_123456_change_me",
}


def test_whoami_returns_user_and_application() -> None:
    response = client.get(
        "/v1/whoami",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["key_id"] == "key-development"
    assert data["user_id"] == "user-local"
    assert data["username"] == "local-user"
    assert data["application_id"] == "app-local"
    assert "demo-chat" in data["allowed_models"]