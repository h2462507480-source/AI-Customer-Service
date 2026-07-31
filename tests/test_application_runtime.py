from __future__ import annotations

from ai_store_support.application_runtime import ApplicationRuntime
from ai_store_support.backup import BackupPolicy
from ai_store_support.paths import ApplicationPaths


def test_application_runtime_starts_backs_up_and_stops(tmp_path):
    paths = ApplicationPaths.from_env(tmp_path / "app").ensure()
    runtime = ApplicationRuntime(
        paths=paths,
        backup_policy=BackupPolicy(interval_seconds=60, run_on_startup=False),
    )
    runtime.start()
    assert runtime.started is True
    assert runtime.status_center.snapshot()["state"] == "running"

    backup = runtime.backup_now()
    assert backup.exists()
    assert runtime.status_center.snapshot()["last_backup_path"] == str(backup)

    runtime.stop()
    assert runtime.started is False
    assert runtime.status_center.snapshot()["state"] == "stopped"
