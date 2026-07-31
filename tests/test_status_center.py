from __future__ import annotations

from ai_store_support.client_status import ClientStatusCenter
from ai_store_support.operation_log import OperationLog
from ai_store_support.runtime_status import RuntimeStatusRegistry


def test_status_center_aggregates_runtime_and_backup_state(tmp_path):
    registry = RuntimeStatusRegistry()
    registry.register("demo:pdd:1", shop_key="demo", channel="pinduoduo", account_key="1")
    registry.set_state("demo:pdd:1", "connected")
    registry.record_received("demo:pdd:1", 4)
    registry.record_sent("demo:pdd:1", 3)
    registry.record_handoff("demo:pdd:1")
    operation_log = OperationLog(tmp_path / "operations.jsonl")
    operation_log.record("application", "start")
    center = ClientStatusCenter(registry, operation_log)
    center.set_backup_provider(
        lambda: {
            "last_success_at": "2026-07-31T12:00:00+08:00",
            "last_backup_path": "backup.db",
            "next_run_at": "2026-08-01T12:00:00+08:00",
            "last_error": "",
        }
    )
    center.start()

    snapshot = center.snapshot()
    assert snapshot["state"] == "running"
    assert snapshot["connected_runtimes"] == 1
    assert snapshot["received_messages"] == 4
    assert snapshot["sent_messages"] == 3
    assert snapshot["handoffs"] == 1
    assert snapshot["last_backup_path"] == "backup.db"
    assert snapshot["latest_operation_at"]
