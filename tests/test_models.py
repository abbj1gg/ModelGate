from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer mg_dev_123456_change_me",
}


def test_list_models() -> None:
    response = client.get(
        "/v1/models",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["object"] == "list"

    model_ids = {
        model["id"]
        for model in data["data"]
    }

    assert "demo-chat" in model_ids
    assert "deepseek-chat" in model_ids