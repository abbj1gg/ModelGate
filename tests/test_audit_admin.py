from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

ADMIN_HEADERS = {
    "Authorization": "Bearer mg_dev_123456_change_me",
}


def test_admin_can_list_failed_audit_logs() -> None:
    failed_response = client.get(
        "/v1/whoami",
        headers={
            "Authorization": "Bearer invalid-audit-admin-key",
        },
    )

    assert failed_response.status_code == 401
    request_id = failed_response.headers["x-request-id"]

    response = client.get(
        "/admin/audit-logs",
        headers=ADMIN_HEADERS,
        params={
            "limit": 100,
            "failures_only": True,
        },
    )

    assert response.status_code == 200

    records = response.json()

    matching = [
        record
        for record in records
        if record["request_id"] == request_id
    ]

    assert len(matching) == 1
    assert matching[0]["path"] == "/v1/whoami"
    assert matching[0]["status_code"] == 401
    assert matching[0]["error_detail"] == "Authentication failed"