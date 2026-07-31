from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .orchestrator import CustomerServiceOrchestrator
from .operation_log import OperationLog
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
    def __init__(
        self,
        orchestrator: CustomerServiceOrchestrator,
        adapters: dict[str, ChannelAdapter],
        operation_log: OperationLog | None = None,
    ):
        self.orchestrator = orchestrator
        self.adapters = adapters
        self.operation_log = operation_log

    def handle(self, message: InboundMessage) -> SupportDecision:
        if self.operation_log:
            self.operation_log.record(
                "conversation",
                "message_received",
                summary="Buyer message received",
                shop_key=message.shop_key,
                conversation_id=message.conversation_id,
                details={"channel": message.channel, "customer_id": message.customer_id, "content": message.content},
            )
        try:
            decision = self.orchestrator.process(message)
        except Exception as exc:
            if self.operation_log:
                self.operation_log.record(
                    "decision", "process_message", result="error", summary="Customer-service decision failed",
                    shop_key=message.shop_key, conversation_id=message.conversation_id,
                    details={"error": str(exc)},
                )
            raise
        adapter = self.adapters.get(message.channel)
        if adapter is None:
            raise KeyError(f"未注册渠道适配器: {message.channel}")
        try:
            if decision.action in {"reply", "handoff"} and decision.reply_text:
                adapter.send_text(message, decision.reply_text)
            if decision.action == "handoff":
                adapter.transfer_to_human(
                    message,
                    reason=decision.handoff_reason,
                    target_group=decision.target_group,
                    metadata=decision.metadata,
                )
        except Exception as exc:
            if self.operation_log:
                self.operation_log.record(
                    "channel", "execute_decision", result="error", summary="Channel action failed",
                    shop_key=message.shop_key, conversation_id=message.conversation_id,
                    details={"action": decision.action, "error": str(exc)},
                )
            raise
        if self.operation_log:
            self.operation_log.record(
                "decision",
                "process_message",
                result="success" if decision.action != "ignore" else "ignored",
                summary=f"Decision: {decision.action}",
                shop_key=message.shop_key,
                conversation_id=message.conversation_id,
                details={
                    "action": decision.action,
                    "intent": decision.intent,
                    "source": decision.source,
                    "reply": decision.reply_text,
                    "handoff_reason": decision.handoff_reason,
                    "target_group": decision.target_group,
                },
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
