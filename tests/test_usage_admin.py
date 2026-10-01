from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

ADMIN_HEADERS = {
    "Authorization": "Bearer mg_dev_123456_change_me",
}


def test_admin_usage_summary() -> None:
    response = client.get(
        "/admin/usage",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)