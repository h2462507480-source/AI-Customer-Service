from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4


_SECRET_KEYS = ("api_key", "apikey", "authorization", "cookie", "credential", "password", "secret", "token")
_BEARER_PATTERN = re.compile(r"(?i)(bearer\s+)[a-z0-9._~+/=-]{8,}")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _is_secret_key(key: str) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return any(marker in normalized for marker in _SECRET_KEYS)


def sanitize(value: Any, *, key: str = "") -> Any:
    if key and _is_secret_key(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): sanitize(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return _BEARER_PATTERN.sub(r"\1[REDACTED]", value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


@dataclass(frozen=True)
class OperationEvent:
    event_id: str
    timestamp: str
    category: str
    action: str
    result: str
    summary: str = ""
    shop_key: str = ""
    conversation_id: str = ""
    runtime_key: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class OperationLog:
    """Append-only structured log for customer-service decisions and runtime actions."""

    def __init__(self, path: str | Path, *, max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5):
        self.path = Path(path)
        self.max_bytes = max(1024, int(max_bytes))
        self.backup_count = max(1, int(backup_count))
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        category: str,
        action: str,
        *,
        result: str = "success",
        summary: str = "",
        shop_key: str = "",
        conversation_id: str | int = "",
        runtime_key: str = "",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = OperationEvent(
            event_id=uuid4().hex,
            timestamp=_now(),
            category=str(category),
            action=str(action),
            result=str(result),
            summary=str(summary),
            shop_key=str(shop_key),
            conversation_id=str(conversation_id),
            runtime_key=str(runtime_key),
            details=sanitize(details or {}),
        )
        payload = asdict(event)
        encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self._lock:
            self._rotate_if_needed(len(encoded))
            with self.path.open("ab") as stream:
                stream.write(encoded)
                stream.flush()
        return payload

    def list_recent(
        self,
        *,
        limit: int = 200,
        category: str = "",
        result: str = "",
    ) -> list[dict[str, Any]]:
        maximum = max(1, min(int(limit), 5000))
        with self._lock:
            if not self.path.exists():
                return []
            lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        rows: list[dict[str, Any]] = []
        for line in reversed(lines):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if category and row.get("category") != category:
                continue
            if result and row.get("result") != result:
                continue
            rows.append(row)
            if len(rows) >= maximum:
                break
        return rows

    def latest(self) -> dict[str, Any] | None:
        rows = self.list_recent(limit=1)
        return rows[0] if rows else None

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if not self.path.exists() or self.path.stat().st_size + incoming_bytes <= self.max_bytes:
            return
        oldest = self.path.with_name(f"{self.path.name}.{self.backup_count}")
        if oldest.exists():
            oldest.unlink()
        for index in range(self.backup_count - 1, 0, -1):
            current = self.path.with_name(f"{self.path.name}.{index}")
            if current.exists():
                current.replace(self.path.with_name(f"{self.path.name}.{index + 1}"))
        self.path.replace(self.path.with_name(f"{self.path.name}.1"))
