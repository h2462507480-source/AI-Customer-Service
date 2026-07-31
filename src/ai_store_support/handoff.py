from __future__ import annotations

import json
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .conversation_models import HandoffRequest


class HandoffService:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def create(
        self,
        *,
        shop_key: str,
        conversation_id: int,
        reason: str,
        target_group: str = "",
        payload: dict[str, Any] | None = None,
    ) -> int:
        with self.session_factory() as session:
            request = HandoffRequest(
                shop_key=shop_key,
                conversation_id=conversation_id,
                reason=reason,
                target_group=target_group,
                payload_json=json.dumps(payload or {}, ensure_ascii=False),
            )
            session.add(request)
            session.commit()
            return request.id

    def list_pending(self, shop_key: str | None = None) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(HandoffRequest).where(HandoffRequest.status == "pending")
            if shop_key:
                stmt = stmt.where(HandoffRequest.shop_key == shop_key)
            rows = list(session.scalars(stmt.order_by(HandoffRequest.id)))
            return [
                {
                    "id": row.id,
                    "shop_key": row.shop_key,
                    "conversation_id": row.conversation_id,
                    "reason": row.reason,
                    "target_group": row.target_group,
                    "status": row.status,
                    "payload": json.loads(row.payload_json or "{}"),
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]
