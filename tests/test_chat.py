from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer mg_dev_123456_change_me",
}


def test_chat_completion_with_demo_model() -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=AUTH_HEADERS,
        json={
            "model": "demo-chat",
            "messages": [
                {
                    "role": "user",
                    "content": "你好，ModelGate。",
                }
            ],
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["object"] == "chat.completion"
    assert data["model"] == "demo-chat"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "ModelGate demo response" in data["choices"][0]["message"]["content"]
    assert data["usage"]["total_tokens"] > 0


def test_chat_completion_rejects_unknown_model() -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=AUTH_HEADERS,
        json={
            "model": "unknown-model",
            "messages": [
                {
                    "role": "user",
                    "content": "你好。",
                }
            ],
        },
    )

    assert response.status_code == 403