from fastapi.testclient import TestClient

from app.main import app
from app.services.audit_store import get_audit_store


client = TestClient(app)


def test_invalid_api_key_request_is_audited() -> None:
    response = client.get(
        "/v1/whoami",
        headers={
            "Authorization": "Bearer invalid-audit-key",
        },
    )

    assert response.status_code == 401
    assert "x-request-id" in response.headers

    request_id = response.headers["x-request-id"]
    records = get_audit_store().list_recent(limit=100)

    record = next(
        item
        for item in records
        if item["request_id"] == request_id
    )

    assert record["method"] == "GET"
    assert record["path"] == "/v1/whoami"
    assert record["status_code"] == 401
    assert record["error_detail"] == "Authentication failed"
    assert record["key_id"] is None