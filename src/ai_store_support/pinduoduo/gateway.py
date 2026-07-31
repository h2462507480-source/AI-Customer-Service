from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

from ..channels import SupportRuntime
from ..runtime_status import RuntimeStatusRegistry
from .models import PinduoduoAccount, PinduoduoConnectionStatus
from .parser import event_to_inbound_message, parse_pinduoduo_event
from .transport import PinduoduoTransport


class MessageDeduplicator:
    def __init__(self, max_items: int = 5000):
        self.max_items = max(100, max_items)
        self._order: deque[str] = deque()
        self._seen: set[str] = set()

    def is_duplicate(self, msg_id: str) -> bool:
        if not msg_id:
            return False
        if msg_id in self._seen:
            return True
        self._seen.add(msg_id)
        self._order.append(msg_id)
        while len(self._order) > self.max_items:
            self._seen.discard(self._order.popleft())
        return False


class PinduoduoGateway:
    """Consumes messages from an authorized transport and invokes the support runtime."""

    def __init__(
        self,
        *,
        account: PinduoduoAccount,
        transport: PinduoduoTransport,
        runtime: SupportRuntime,
        max_concurrent_messages: int = 20,
        runtime_status: RuntimeStatusRegistry | None = None,
        runtime_key: str = "",
    ):
        self.account = account
        self.transport = transport
        self.runtime = runtime
        self.runtime_status = runtime_status
        self.runtime_key = runtime_key
        self.status = PinduoduoConnectionStatus("disconnected")
        self._semaphore = asyncio.Semaphore(max(1, max_concurrent_messages))
        self._tasks: set[asyncio.Task[Any]] = set()
        self._deduplicator = MessageDeduplicator()
        self._stopping = False

    async def run(self) -> None:
        self.status = PinduoduoConnectionStatus("connected")
        try:
            async for raw_message in self.transport.messages():
                if self._stopping:
                    break
                event = parse_pinduoduo_event(raw_message)
                if self._deduplicator.is_duplicate(event.msg_id):
                    continue
                inbound = event_to_inbound_message(event, self.account)
                if inbound is None:
                    continue
                if self.runtime_status and self.runtime_key:
                    self.runtime_status.record_received(self.runtime_key)
                task = asyncio.create_task(self._handle(inbound))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        finally:
            self.status = PinduoduoConnectionStatus("disconnected")
            await self._drain()

    async def stop(self) -> None:
        self._stopping = True
        await self.transport.close()
        await self._drain()
        self.status = PinduoduoConnectionStatus("disconnected")

    async def _handle(self, inbound) -> None:
        async with self._semaphore:
            decision = await asyncio.to_thread(self.runtime.handle, inbound)
            if self.runtime_status and self.runtime_key:
                if decision.action in {"reply", "handoff"} and decision.reply_text:
                    self.runtime_status.record_sent(self.runtime_key)
                if decision.action == "handoff":
                    self.runtime_status.record_handoff(self.runtime_key)

    async def _drain(self) -> None:
        tasks = list(self._tasks)
        self._tasks.clear()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
