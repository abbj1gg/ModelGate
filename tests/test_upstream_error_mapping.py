import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.providers.circuit_breaker import CircuitOpenError


client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer mg_dev_123456_change_me",
}


def chat_payload() -> dict[str, object]:
    return {
        "model": "demo-chat",
        "messages": [
            {
                "role": "user",
                "content": "error mapping test",
            }
        ],
        "temperature": 0.2,
        "stream": False,
    }


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (TimeoutError("upstream timeout"), 504),
        (
            CircuitOpenError("circuit is open"),
            503,
        ),
        (ConnectionError("connection failed"), 502),
    ],
)
def test_upstream_errors_map_to_http_status(
    monkeypatch,
    error: Exception,
    expected_status: int,
) -> None:
    async def failing_complete(**kwargs):
        raise error

    monkeypatch.setattr(
        main_module.chat_service,
        "complete",
        failing_complete,
    )

    response = client.post(
        "/v1/chat/completions",
        headers=AUTH_HEADERS,
        json=chat_payload(),
    )

    assert response.status_code == expected_status