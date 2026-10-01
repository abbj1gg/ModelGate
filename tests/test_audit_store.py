from app.services.audit_store import AuditStore


def test_audit_store_records_failed_request(tmp_path) -> None:
    store = AuditStore(str(tmp_path / "audit.db"))

    store.record(
        request_id="req-audit-001",
        method="POST",
        path="/v1/chat/completions",
        status_code=429,
        error_detail="Token quota exceeded",
        key_id="key-001",
        user_id="user-001",
        application_id="app-001",
        latency_ms=3,
    )

    records = store.list_recent(failures_only=True)

    assert len(records) == 1

    record = records[0]

    assert record["request_id"] == "req-audit-001"
    assert record["method"] == "POST"
    assert record["path"] == "/v1/chat/completions"
    assert record["status_code"] == 429
    assert record["error_detail"] == "Token quota exceeded"
    assert record["key_id"] == "key-001"
    assert record["latency_ms"] == 3