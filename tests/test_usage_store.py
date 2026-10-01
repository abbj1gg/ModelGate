from app.services.usage_store import UsageStore


def test_usage_store_records_and_lists_usage(tmp_path) -> None:
    database_path = tmp_path / "usage.db"
    store = UsageStore(str(database_path))

    store.record(
        request_id="req-001",
        key_id="key-001",
        user_id="user-001",
        application_id="app-001",
        model="demo-chat",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        latency_ms=125,
        status_code=200,
    )

    records = store.list_recent()

    assert len(records) == 1
    assert records[0]["request_id"] == "req-001"
    assert records[0]["key_id"] == "key-001"
    assert records[0]["model"] == "demo-chat"
    assert records[0]["prompt_tokens"] == 10
    assert records[0]["completion_tokens"] == 20
    assert records[0]["total_tokens"] == 30
    assert records[0]["status_code"] == 200
def test_usage_store_summarizes_usage(tmp_path) -> None:
    database_path = tmp_path / "summary.db"
    store = UsageStore(str(database_path))

    store.record(
        request_id="req-001",
        key_id="key-001",
        user_id="user-001",
        application_id="app-001",
        model="demo-chat",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        latency_ms=100,
        status_code=200,
    )

    store.record(
        request_id="req-002",
        key_id="key-001",
        user_id="user-001",
        application_id="app-001",
        model="demo-chat",
        prompt_tokens=5,
        completion_tokens=15,
        total_tokens=20,
        latency_ms=200,
        status_code=200,
    )

    summaries = store.summarize()

    assert len(summaries) == 1

    summary = summaries[0]

    assert summary["user_id"] == "user-001"
    assert summary["application_id"] == "app-001"
    assert summary["model"] == "demo-chat"
    assert summary["request_count"] == 2
    assert summary["prompt_tokens"] == 15
    assert summary["completion_tokens"] == 35
    assert summary["total_tokens"] == 50
    assert summary["success_count"] == 2
    assert summary["failure_count"] == 0