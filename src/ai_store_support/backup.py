from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event, RLock, Thread
from typing import Callable

from .operation_log import OperationLog


BACKUP_PREFIX = "ai-store-support-"


def _now() -> datetime:
    return datetime.now().astimezone()


def _iso(value: datetime | None) -> str:
    return value.isoformat(timespec="seconds") if value else ""


def backup_database(source: str | Path, target_dir: str | Path, *, now: datetime | None = None) -> Path:
    """Create a consistent, timestamped SQLite backup.

    SQLite's online backup API is used for live databases. A regular copy is kept as
    a compatibility fallback for legacy tests and non-SQLite files.
    """

    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    directory = Path(target_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = (now or _now()).strftime("%Y%m%d_%H%M%S_%f")
    target = directory / f"{BACKUP_PREFIX}{stamp}.db"
    temporary = target.with_suffix(".tmp")
    try:
        source_connection = sqlite3.connect(f"file:{source_path.resolve().as_posix()}?mode=ro", uri=True)
        try:
            target_connection = sqlite3.connect(temporary)
            try:
                source_connection.backup(target_connection)
            finally:
                target_connection.close()
        finally:
            source_connection.close()
    except sqlite3.DatabaseError:
        if temporary.exists():
            temporary.unlink()
        shutil.copy2(source_path, temporary)
    temporary.replace(target)
    return target


def cleanup_backups(
    target_dir: str | Path,
    *,
    retention_days: int = 30,
    max_backups: int = 60,
    now: datetime | None = None,
) -> list[Path]:
    directory = Path(target_dir)
    if not directory.exists():
        return []
    reference = now or _now()
    cutoff = reference - timedelta(days=max(1, int(retention_days)))
    candidates = sorted(
        directory.glob(f"{BACKUP_PREFIX}*.db"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    removed: list[Path] = []
    keep_count = max(1, int(max_backups))
    for index, path in enumerate(candidates):
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=reference.tzinfo)
        if index >= keep_count or modified < cutoff:
            path.unlink(missing_ok=True)
            removed.append(path)
    return removed


def export_json(data: object, target: str | Path) -> Path:
    """Export admin snapshots and operation records."""

    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@dataclass(frozen=True)
class BackupPolicy:
    interval_seconds: float = 24 * 60 * 60
    retention_days: int = 30
    max_backups: int = 60
    run_on_startup: bool = True

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("backup interval must be positive")
        if self.retention_days <= 0 or self.max_backups <= 0:
            raise ValueError("backup retention values must be positive")


@dataclass
class BackupStatus:
    state: str = "stopped"
    last_success_at: str = ""
    last_backup_path: str = ""
    last_error: str = ""
    next_run_at: str = ""
    backup_count: int = 0


class BackupScheduler:
    def __init__(
        self,
        source: str | Path,
        target_dir: str | Path,
        *,
        policy: BackupPolicy | None = None,
        operation_log: OperationLog | None = None,
        clock: Callable[[], datetime] = _now,
    ):
        self.source = Path(source)
        self.target_dir = Path(target_dir)
        self.policy = policy or BackupPolicy()
        self.operation_log = operation_log
        self.clock = clock
        self._status = BackupStatus()
        self._lock = RLock()
        self._run_lock = RLock()
        self._stop = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._status.state = "running"
            self._thread = Thread(target=self._worker, name="ai-store-support-backup", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        with self._lock:
            self._thread = None
            self._status.state = "stopped"
            self._status.next_run_at = ""

    def run_once(self) -> Path:
        with self._run_lock:
            started = self.clock()
            try:
                created = backup_database(self.source, self.target_dir, now=started)
                removed = cleanup_backups(
                    self.target_dir,
                    retention_days=self.policy.retention_days,
                    max_backups=self.policy.max_backups,
                    now=started,
                )
            except Exception as exc:
                with self._lock:
                    self._status.last_error = str(exc)
                if self.operation_log:
                    self.operation_log.record(
                        "backup", "database_backup", result="error", summary="Database backup failed",
                        details={"error": str(exc), "source": self.source},
                    )
                raise
            with self._lock:
                self._status.last_success_at = _iso(started)
                self._status.last_backup_path = str(created)
                self._status.last_error = ""
                self._status.backup_count += 1
            if self.operation_log:
                self.operation_log.record(
                    "backup", "database_backup", summary="Database backup completed",
                    details={"path": created, "removed_old_backups": len(removed)},
                )
            return created

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return asdict(self._status)

    def _worker(self) -> None:
        if self.policy.run_on_startup and not self._stop.is_set():
            try:
                self.run_once()
            except Exception:
                pass
        while not self._stop.is_set():
            next_run = self.clock() + timedelta(seconds=self.policy.interval_seconds)
            with self._lock:
                self._status.next_run_at = _iso(next_run)
            if self._stop.wait(self.policy.interval_seconds):
                break
            try:
                self.run_once()
            except Exception:
                continue
