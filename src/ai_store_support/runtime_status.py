from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
from threading import RLock


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class RuntimeStatus:
    runtime_key: str
    shop_key: str
    channel: str
    account_key: str
    display_name: str = ""
    state: str = "disconnected"
    last_error: str = ""
    started_at: str = ""
    connected_at: str = ""
    last_event_at: str = ""
    received_messages: int = 0
    sent_messages: int = 0
    handoffs: int = 0
    reconnects: int = 0


class RuntimeStatusRegistry:
    def __init__(self):
        self._lock = RLock()
        self._items: dict[str, RuntimeStatus] = {}

    def register(self, runtime_key: str, *, shop_key: str, channel: str, account_key: str, display_name: str = "") -> RuntimeStatus:
        with self._lock:
            current = self._items.get(runtime_key)
            item = current or RuntimeStatus(runtime_key, shop_key, channel, account_key, display_name)
            if current:
                item = replace(item, shop_key=shop_key, channel=channel, account_key=account_key, display_name=display_name)
            self._items[runtime_key] = item
            return item

    def set_state(self, runtime_key: str, state: str, *, error: str = "") -> RuntimeStatus:
        allowed = {"disconnected", "starting", "connecting", "connected", "reconnecting", "stopping", "error"}
        if state not in allowed:
            raise ValueError(f"运行状态不合法: {state}")
        with self._lock:
            item = self._required(runtime_key)
            now = _now()
            values = {"state": state, "last_error": str(error or "")}
            if state == "starting" and not item.started_at:
                values["started_at"] = now
            if state == "connected":
                values["connected_at"] = now
            if state == "reconnecting":
                values["reconnects"] = item.reconnects + 1
            item = replace(item, **values)
            self._items[runtime_key] = item
            return item

    def record_received(self, runtime_key: str, count: int = 1) -> None:
        with self._lock:
            item = self._required(runtime_key)
            self._items[runtime_key] = replace(item, received_messages=item.received_messages + max(0, count), last_event_at=_now())

    def record_sent(self, runtime_key: str, count: int = 1) -> None:
        with self._lock:
            item = self._required(runtime_key)
            self._items[runtime_key] = replace(item, sent_messages=item.sent_messages + max(0, count), last_event_at=_now())

    def record_handoff(self, runtime_key: str, count: int = 1) -> None:
        with self._lock:
            item = self._required(runtime_key)
            self._items[runtime_key] = replace(item, handoffs=item.handoffs + max(0, count), last_event_at=_now())

    def get(self, runtime_key: str) -> dict | None:
        with self._lock:
            item = self._items.get(runtime_key)
            return asdict(item) if item else None

    def list(self, *, shop_key: str | None = None) -> list[dict]:
        with self._lock:
            rows = list(self._items.values())
        if shop_key:
            rows = [row for row in rows if row.shop_key == shop_key]
        return [asdict(row) for row in sorted(rows, key=lambda value: (value.shop_key, value.channel, value.display_name, value.account_key))]

    def remove(self, runtime_key: str) -> None:
        with self._lock:
            self._items.pop(runtime_key, None)

    def _required(self, runtime_key: str) -> RuntimeStatus:
        item = self._items.get(runtime_key)
        if item is None:
            raise KeyError(f"运行账号未注册: {runtime_key}")
        return item
