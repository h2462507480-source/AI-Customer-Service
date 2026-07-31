from __future__ import annotations

from ai_store_support.operation_log import OperationLog


def test_operation_log_records_filters_and_redacts(tmp_path):
    log = OperationLog(tmp_path / "operations.jsonl")
    log.record(
        "decision",
        "reply",
        shop_key="demo",
        conversation_id="buyer-1",
        details={
            "content": "vivo y100有吗",
            "authorization": "Bearer abcdefghijklmnop",
            "nested": {"api_key": "must-not-leak"},
        },
    )
    log.record("backup", "database_backup", result="error", details={"password": "hidden"})

    decision = log.list_recent(limit=10, category="decision")[0]
    assert decision["details"]["content"] == "vivo y100有吗"
    assert decision["details"]["authorization"] == "[REDACTED]"
    assert decision["details"]["nested"]["api_key"] == "[REDACTED]"
    assert "must-not-leak" not in (tmp_path / "operations.jsonl").read_text(encoding="utf-8")
    assert log.list_recent(limit=10, result="error")[0]["category"] == "backup"


def test_operation_log_rotates(tmp_path):
    log = OperationLog(tmp_path / "operations.jsonl", max_bytes=1024, backup_count=2)
    for index in range(30):
        log.record("runtime", "heartbeat", details={"index": index, "payload": "x" * 100})
    assert (tmp_path / "operations.jsonl").exists()
    assert (tmp_path / "operations.jsonl.1").exists()
