from __future__ import annotations

import logging
import os
from pathlib import Path
from threading import RLock

from .admin import AdminService
from .backup import BackupPolicy, BackupScheduler
from .bridge import BridgeSupervisor
from .client_status import ClientStatusCenter
from .db import create_database
from .logging_service import configure_logging
from .operation_log import OperationLog
from .paths import ApplicationPaths
from .runtime_status import RuntimeStatusRegistry


class ApplicationRuntime:
    """Owns the long-running services used by the packaged desktop client."""

    def __init__(
        self,
        *,
        paths: ApplicationPaths | None = None,
        backup_policy: BackupPolicy | None = None,
    ):
        self.paths = (paths or ApplicationPaths.from_env()).ensure()
        self.engine, self.sessions = create_database(self.paths.database)
        self.admin = AdminService(self.sessions, self.engine)
        self.operation_log = OperationLog(self.paths.operation_log)
        self.registry = RuntimeStatusRegistry()
        self.status_center = ClientStatusCenter(self.registry, self.operation_log)
        resolved_policy = backup_policy or BackupPolicy(
            interval_seconds=float(os.getenv("AI_STORE_BACKUP_INTERVAL_SECONDS", str(24 * 60 * 60))),
            retention_days=int(os.getenv("AI_STORE_BACKUP_RETENTION_DAYS", "30")),
            max_backups=int(os.getenv("AI_STORE_BACKUP_MAX_FILES", "60")),
            run_on_startup=os.getenv("AI_STORE_BACKUP_ON_STARTUP", "true").lower() not in {"0", "false", "no"},
        )
        self.backups = BackupScheduler(
            self.paths.database,
            self.paths.backups,
            policy=resolved_policy,
            operation_log=self.operation_log,
        )
        self.status_center.set_backup_provider(self.backups.snapshot)
        self.bridge = BridgeSupervisor(self.registry, self.operation_log)
        self._lock = RLock()
        self._started = False

    @property
    def started(self) -> bool:
        with self._lock:
            return self._started

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            configure_logging(self.paths.logs)
            self._started = True
            self.status_center.start()
            self.operation_log.record(
                "application",
                "start",
                summary="Desktop client started",
                details={"database": self.paths.database, "logs": self.paths.logs},
            )
            self.backups.start()
        logging.getLogger(__name__).info("AI customer service desktop client started")

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            self.status_center.stopping()
        try:
            self.bridge.stop_all()
            self.backups.stop()
            self.operation_log.record("application", "stop", summary="Desktop client stopped")
        except Exception as exc:
            self.status_center.record_error(str(exc))
            self.operation_log.record(
                "application", "stop", result="error", summary="Desktop client shutdown failed",
                details={"error": str(exc)},
            )
            raise
        finally:
            self.engine.dispose()
            self.status_center.stop()
            with self._lock:
                self._started = False

    def backup_now(self) -> Path:
        return self.backups.run_once()
