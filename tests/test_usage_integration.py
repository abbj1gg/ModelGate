from fastapi.testclient import TestClient

from app.main import app
from app.services.usage_store import get_usage_store


client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer mg_dev_123456_change_me",
}


def test_chat_completion_records_usage() -> None:
    store = get_usage_store()

    before_ids = {
        str(record["request_id"])
        for record in store.list_recent()
    }

    response = client.post(
        "/v1/chat/completions",
        headers=AUTH_HEADERS,
        json={
            "model": "demo-chat",
            "messages": [
                {
                    "role": "user",
                    "content": "usage logging test",
                }
            ],
            "stream": False,
        },
    )

    assert response.status_code == 200

    records = store.list_recent()
    new_records = [
        record
        for record in records
        if str(record["request_id"]) not in before_ids
    ]

    assert new_records

    latest = new_records[0]

    assert latest["key_id"] == "key-development"
    assert latest["user_id"] == "user-local"
    assert latest["application_id"] == "app-local"
    assert latest["model"] == "demo-chat"
    assert latest["status_code"] == 200
    assert latest["latency_ms"] >= 0