from __future__ import annotations

from datetime import datetime
from threading import RLock
from time import monotonic
from typing import Any, Callable

from .operation_log import OperationLog
from .runtime_status import RuntimeStatusRegistry


class ClientStatusCenter:
    """Aggregates application, channel, backup and operation-log status for the desktop client."""

    def __init__(self, registry: RuntimeStatusRegistry, operation_log: OperationLog):
        self.registry = registry
        self.operation_log = operation_log
        self._lock = RLock()
        self._state = "stopped"
        self._started_at = ""
        self._started_monotonic = 0.0
        self._last_error = ""
        self._backup_provider: Callable[[], dict[str, Any]] | None = None

    def set_backup_provider(self, provider: Callable[[], dict[str, Any]]) -> None:
        self._backup_provider = provider

    def start(self) -> None:
        with self._lock:
            if self._state == "running":
                return
            self._state = "running"
            self._started_at = datetime.now().astimezone().isoformat(timespec="seconds")
            self._started_monotonic = monotonic()
            self._last_error = ""

    def stopping(self) -> None:
        with self._lock:
            self._state = "stopping"

    def stop(self) -> None:
        with self._lock:
            self._state = "stopped"

    def record_error(self, error: str) -> None:
        with self._lock:
            self._last_error = str(error)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            app_state = self._state
            started_at = self._started_at
            started_monotonic = self._started_monotonic
            last_error = self._last_error
        runtimes = self.registry.list()
        state_counts: dict[str, int] = {}
        for row in runtimes:
            state = str(row["state"])
            state_counts[state] = state_counts.get(state, 0) + 1
        channel_error = next((row["last_error"] for row in runtimes if row.get("last_error")), "")
        if app_state == "running" and state_counts.get("error", 0):
            display_state = "degraded"
        else:
            display_state = app_state
        backup = self._backup_provider() if self._backup_provider else {}
        latest_operation = self.operation_log.latest()
        return {
            "state": display_state,
            "started_at": started_at,
            "uptime_seconds": int(monotonic() - started_monotonic) if started_monotonic else 0,
            "runtime_count": len(runtimes),
            "connected_runtimes": state_counts.get("connected", 0),
            "error_runtimes": state_counts.get("error", 0),
            "reconnecting_runtimes": state_counts.get("reconnecting", 0),
            "received_messages": sum(int(row["received_messages"]) for row in runtimes),
            "sent_messages": sum(int(row["sent_messages"]) for row in runtimes),
            "handoffs": sum(int(row["handoffs"]) for row in runtimes),
            "reconnects": sum(int(row["reconnects"]) for row in runtimes),
            "last_error": last_error or channel_error or str(backup.get("last_error", "")),
            "last_backup_at": str(backup.get("last_success_at", "")),
            "last_backup_path": str(backup.get("last_backup_path", "")),
            "next_backup_at": str(backup.get("next_run_at", "")),
            "latest_operation_at": str((latest_operation or {}).get("timestamp", "")),
        }
