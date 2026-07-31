from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class PinduoduoTransport(Protocol):
    """Authorized transport contract for a Pinduoduo customer-service channel."""

    def messages(self) -> AsyncIterator[str | bytes | dict[str, Any]]: ...

    def send_text(self, recipient_uid: str, text: str) -> None: ...

    def list_customer_services(self) -> list[dict[str, Any]]: ...

    def transfer_conversation(self, recipient_uid: str, cs_uid: str, *, reason: str) -> None: ...

    async def close(self) -> None: ...
