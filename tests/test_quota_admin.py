from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

ADMIN_HEADERS = {
    "Authorization": "Bearer mg_dev_123456_change_me",
}


def test_admin_can_set_and_read_api_key_quota() -> None:
    key_id = "key-quota-test"

    update_response = client.post(
        f"/admin/api-keys/{key_id}/quota",
        headers=ADMIN_HEADERS,
        json={
            "monthly_token_limit": 1000,
        },
    )

    assert update_response.status_code == 200

    updated = update_response.json()

    assert updated["key_id"] == key_id
    assert updated["monthly_limit"] == 1000
    assert updated["used_tokens"] == 0
    assert updated["remaining_tokens"] == 1000
    assert updated["unlimited"] is False

    get_response = client.get(
        f"/admin/api-keys/{key_id}/quota",
        headers=ADMIN_HEADERS,
    )

    assert get_response.status_code == 200

    current = get_response.json()

    assert current["key_id"] == key_id
    assert current["monthly_limit"] == 1000
    assert current["remaining_tokens"] == 1000


def test_admin_rejects_invalid_quota() -> None:
    response = client.post(
        "/admin/api-keys/key-quota-invalid/quota",
        headers=ADMIN_HEADERS,
        json={
            "monthly_token_limit": 0,
        },
    )

    assert response.status_code == 422