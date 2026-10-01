from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer mg_dev_123456_change_me",
}


def test_chat_response_contains_quota_headers() -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=AUTH_HEADERS,
        json={
            "model": "demo-chat",
            "messages": [
                {
                    "role": "user",
                    "content": "quota header test",
                }
            ],
            "stream": False,
        },
    )

    assert response.status_code == 200
    assert "x-quota-used" in response.headers
    assert "x-quota-unlimited" in response.headers

    if response.headers["x-quota-unlimited"] == "false":
        assert "x-quota-limit" in response.headers
        assert "x-quota-remaining" in response.headers