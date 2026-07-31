from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from .conversation_models import Conversation, ConversationMessage
from .schemas import ChatMessage, InboundMessage


class ConversationService:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def get_or_create(self, message: InboundMessage) -> int:
        with self.session_factory() as session:
            stmt = select(Conversation).where(
                and_(
                    Conversation.shop_key == message.shop_key,
                    Conversation.channel == message.channel,
                    Conversation.external_conversation_id == message.conversation_id,
                )
            )
            conversation = session.scalar(stmt)
            if conversation is None:
                conversation = Conversation(
                    shop_key=message.shop_key,
                    channel=message.channel,
                    external_conversation_id=message.conversation_id,
                    customer_id=message.customer_id,
                )
                session.add(conversation)
                session.flush()
            elif message.customer_id and not conversation.customer_id:
                conversation.customer_id = message.customer_id
            conversation.updated_at = datetime.now()
            session.commit()
            return conversation.id

    def append(self, conversation_id: int, role: str, content: str, source: str) -> None:
        if not str(content or "").strip():
            return
        with self.session_factory() as session:
            session.add(
                ConversationMessage(
                    conversation_id=conversation_id,
                    role=role,
                    content=str(content).strip(),
                    source=source,
                )
            )
            conversation = session.get(Conversation, conversation_id)
            if conversation:
                conversation.updated_at = datetime.now()
            session.commit()

    def recent_history(self, conversation_id: int, limit: int = 12) -> list[ChatMessage]:
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(ConversationMessage)
                    .where(ConversationMessage.conversation_id == conversation_id)
                    .order_by(desc(ConversationMessage.id))
                    .limit(max(1, limit))
                )
            )
        rows.reverse()
        result: list[ChatMessage] = []
        for row in rows:
            if row.role in {"user", "assistant"}:
                result.append(ChatMessage(role=row.role, content=row.content))
        return result

    def set_status(self, conversation_id: int, status: str, *, intent: str = "") -> None:
        with self.session_factory() as session:
            conversation = session.get(Conversation, conversation_id)
            if conversation:
                conversation.status = status
                if intent:
                    conversation.last_intent = intent
                conversation.updated_at = datetime.now()
                session.commit()

    def get_status(self, conversation_id: int) -> str:
        with self.session_factory() as session:
            conversation = session.get(Conversation, conversation_id)
            return conversation.status if conversation else "ai"
