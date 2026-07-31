from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


APP_DIRECTORY_NAME = "AI-Customer-Service"


def _default_root() -> Path:
    configured = os.getenv("AI_STORE_HOME", "").strip()
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA", "").strip()
        if local_app_data:
            return Path(local_app_data) / APP_DIRECTORY_NAME
    state_home = os.getenv("XDG_STATE_HOME", "").strip()
    if state_home:
        return Path(state_home) / "ai-store-support"
    return Path.home() / ".ai-store-support"


@dataclass(frozen=True)
class ApplicationPaths:
    root: Path
    database: Path
    logs: Path
    operation_log: Path
    backups: Path

    @classmethod
    def from_env(cls, root: str | Path | None = None) -> "ApplicationPaths":
        resolved_root = Path(root).expanduser() if root is not None else _default_root()
        database = Path(os.getenv("AI_STORE_DB", "").strip() or resolved_root / "data" / "ai-store-support.db")
        logs = Path(os.getenv("AI_STORE_LOG_DIR", "").strip() or resolved_root / "logs")
        backups = Path(os.getenv("AI_STORE_BACKUP_DIR", "").strip() or resolved_root / "backups")
        operation_log = Path(
            os.getenv("AI_STORE_OPERATION_LOG", "").strip() or logs / "operations.jsonl"
        )
        return cls(
            root=resolved_root,
            database=database,
            logs=logs,
            operation_log=operation_log,
            backups=backups,
        )

    def ensure(self) -> "ApplicationPaths":
        self.root.mkdir(parents=True, exist_ok=True)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        self.operation_log.parent.mkdir(parents=True, exist_ok=True)
        self.backups.mkdir(parents=True, exist_ok=True)
        return self
