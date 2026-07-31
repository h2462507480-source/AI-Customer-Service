import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_store_support.backup import (
    BackupPolicy,
    BackupScheduler,
    backup_database,
    cleanup_backups,
    export_json,
)


def test_backup_and_export(tmp_path: Path):
    db = tmp_path / "source.db"
    db.write_text("demo", encoding="utf-8")

    backup = backup_database(db, tmp_path / "backups")
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == "demo"

    exported = export_json({"ok": True}, tmp_path / "export" / "data.json")
    assert exported.exists()
    assert "true" in exported.read_text(encoding="utf-8")


def test_cleanup_backups_applies_age_and_count_limits(tmp_path: Path):
    directory = tmp_path / "backups"
    directory.mkdir()
    now = datetime.now(timezone.utc)
    paths = []
    for index in range(4):
        path = directory / f"ai-store-support-2026070{index}_000000_000000.db"
        path.write_text(str(index), encoding="utf-8")
        modified = now - timedelta(days=index * 10)
        os.utime(path, (modified.timestamp(), modified.timestamp()))
        paths.append(path)

    removed = cleanup_backups(directory, retention_days=25, max_backups=2, now=now)
    assert len(removed) == 2
    assert len(list(directory.glob("*.db"))) == 2


def test_backup_scheduler_runs_automatically(tmp_path: Path):
    source = tmp_path / "source.db"
    source.write_text("demo", encoding="utf-8")
    scheduler = BackupScheduler(
        source,
        tmp_path / "backups",
        policy=BackupPolicy(interval_seconds=0.05, retention_days=30, max_backups=5, run_on_startup=True),
    )
    scheduler.start()
    deadline = time.time() + 2
    while time.time() < deadline and scheduler.snapshot()["backup_count"] < 2:
        time.sleep(0.02)
    scheduler.stop()
    assert scheduler.snapshot()["backup_count"] >= 2
    assert len(list((tmp_path / "backups").glob("*.db"))) <= 5
