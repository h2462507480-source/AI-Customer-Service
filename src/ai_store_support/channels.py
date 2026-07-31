from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .orchestrator import CustomerServiceOrchestrator
from .schemas import InboundMessage, SupportDecision


class ChannelAdapter(Protocol):
    def send_text(self, message: InboundMessage, text: str) -> None: ...

    def transfer_to_human(
        self,
        message: InboundMessage,
        *,
        reason: str,
        target_group: str,
        metadata: dict[str, Any],
    ) -> None: ...


class SupportRuntime:
    def __init__(self, orchestrator: CustomerServiceOrchestrator, adapters: dict[str, ChannelAdapter]):
        self.orchestrator = orchestrator
        self.adapters = adapters

    def handle(self, message: InboundMessage) -> SupportDecision:
        decision = self.orchestrator.process(message)
        adapter = self.adapters.get(message.channel)
        if adapter is None:
            raise KeyError(f"未注册渠道适配器: {message.channel}")
        if decision.action in {"reply", "handoff"} and decision.reply_text:
            adapter.send_text(message, decision.reply_text)
        if decision.action == "handoff":
            adapter.transfer_to_human(
                message,
                reason=decision.handoff_reason,
                target_group=decision.target_group,
                metadata=decision.metadata,
            )
        return decision


@dataclass
class MemoryChannelAdapter:
    sent_messages: list[tuple[str, str]] = field(default_factory=list)
    transfers: list[dict[str, Any]] = field(default_factory=list)

    def send_text(self, message: InboundMessage, text: str) -> None:
        self.sent_messages.append((message.conversation_id, text))

    def transfer_to_human(
        self,
        message: InboundMessage,
        *,
        reason: str,
        target_group: str,
        metadata: dict[str, Any],
    ) -> None:
        self.transfers.append(
            {
                "conversation_id": message.conversation_id,
                "reason": reason,
                "target_group": target_group,
                "metadata": metadata,
            }
        )
