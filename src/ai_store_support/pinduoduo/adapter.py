from __future__ import annotations

from typing import Any

from ..schemas import InboundMessage
from .models import PinduoduoAccount
from .transport import PinduoduoTransport


class PinduoduoChannelAdapter:
    def __init__(self, account: PinduoduoAccount, transport: PinduoduoTransport):
        self.account = account
        self.transport = transport

    def send_text(self, message: InboundMessage, text: str) -> None:
        recipient = str(message.metadata.get("recipient_uid") or message.customer_id)
        if not recipient:
            raise ValueError("missing customer uid")
        self.transport.send_text(recipient, text)

    def transfer_to_human(
        self,
        message: InboundMessage,
        *,
        reason: str,
        target_group: str,
        metadata: dict[str, Any],
    ) -> None:
        recipient = str(message.metadata.get("recipient_uid") or message.customer_id)
        target = str(metadata.get("target_cs_uid") or self.account.group_routes.get(target_group) or "")
        if not target:
            current = str(message.metadata.get("current_cs_uid") or self.account.current_cs_uid)
            for row in self.transport.list_customer_services():
                uid = str(row.get("uid") or row.get("csUid") or "")
                available = row.get("online", row.get("available", True))
                if uid and uid != current and available:
                    target = uid
                    break
        if not target:
            raise RuntimeError("no available human customer service")
        self.transport.transfer_conversation(recipient, target, reason=reason)
