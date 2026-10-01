from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services.usage_store import get_usage_store


client = TestClient(app)

ADMIN_HEADERS = {
    "Authorization": "Bearer mg_dev_123456_change_me",
}


def test_chat_is_rejected_when_token_quota_is_exhausted() -> None:
    suffix = uuid4().hex[:8]

    user_response = client.post(
        "/admin/users",
        headers=ADMIN_HEADERS,
        json={
            "username": f"quota-user-{suffix}",
        },
    )

    assert user_response.status_code == 201
    user = user_response.json()

    application_response = client.post(
        "/admin/applications",
        headers=ADMIN_HEADERS,
        json={
            "name": f"quota-app-{suffix}",
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
    api_key_record = key_response.json()

    key_id = api_key_record["id"]
    api_key = api_key_record["api_key"]

    quota_response = client.post(
        f"/admin/api-keys/{key_id}/quota",
        headers=ADMIN_HEADERS,
        json={
            "monthly_token_limit": 10,
        },
    )

    assert quota_response.status_code == 200

    get_usage_store().record(
        request_id=f"req-{suffix}",
        key_id=key_id,
        user_id=user["id"],
        application_id=application["id"],
        model="demo-chat",
        prompt_tokens=5,
        completion_tokens=5,
        total_tokens=10,
        latency_ms=1,
        status_code=200,
    )

    chat_response = client.post(
        "/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": "demo-chat",
            "messages": [
                {
                    "role": "user",
                    "content": "This request should be rejected",
                }
            ],
            "stream": False,
        },
    )

    assert chat_response.status_code == 429
    assert chat_response.json()["detail"] == "Token quota exceeded"
    assert chat_response.headers["x-quota-limit"] == "10"
    assert chat_response.headers["x-quota-used"] == "10"
    assert chat_response.headers["x-quota-remaining"] == "0"