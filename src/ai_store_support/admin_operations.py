from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import delete, desc, func, select

from .admin_core import (
    _ALLOWED_CONVERSATION_STATUSES,
    _ALLOWED_HANDOFF_STATUSES,
    _contains_secret_key,
    _iso,
    _json_loads,
)
from .config_models import ChannelAccount, ShopSettings
from .conversation_models import Conversation, ConversationMessage, HandoffRequest


class AdminOperationsMixin:

    def list_conversations(self, shop_key: str, *, status: str = "all", limit: int = 500) -> list[dict[str, Any]]:
            stmt = select(Conversation).where(Conversation.shop_key == shop_key)
            if status != "all":
                stmt = stmt.where(Conversation.status == status)
            stmt = stmt.order_by(desc(Conversation.updated_at)).limit(max(1, min(limit, 5000)))
            with self.session_factory() as session:
                rows = list(session.scalars(stmt))
                result = []
                for row in rows:
                    count = session.scalar(select(func.count()).select_from(ConversationMessage).where(ConversationMessage.conversation_id == row.id)) or 0
                    result.append(
                        {
                            "id": row.id,
                            "channel": row.channel,
                            "external_conversation_id": row.external_conversation_id,
                            "customer_id": row.customer_id,
                            "status": row.status,
                            "last_intent": row.last_intent,
                            "message_count": int(count),
                            "updated_at": _iso(row.updated_at),
                        }
                    )
                return result

    def conversation_messages(self, conversation_id: int, *, limit: int = 200) -> list[dict[str, Any]]:
            stmt = select(ConversationMessage).where(ConversationMessage.conversation_id == int(conversation_id)).order_by(desc(ConversationMessage.id)).limit(max(1, min(limit, 2000)))
            with self.session_factory() as session:
                rows = list(session.scalars(stmt))
            rows.reverse()
            return [{"id": row.id, "role": row.role, "content": row.content, "source": row.source, "created_at": _iso(row.created_at)} for row in rows]

    def set_conversation_status(self, conversation_id: int, status: str) -> None:
            if status not in _ALLOWED_CONVERSATION_STATUSES:
                raise ValueError(f"会话状态不合法: {status}")
            with self.session_factory() as session:
                row = session.get(Conversation, int(conversation_id))
                if row is None:
                    raise KeyError(f"会话不存在: {conversation_id}")
                row.status = status
                row.updated_at = datetime.now()
                session.commit()

    def list_handoffs(self, shop_key: str, *, status: str = "pending", limit: int = 500) -> list[dict[str, Any]]:
            stmt = select(HandoffRequest).where(HandoffRequest.shop_key == shop_key)
            if status != "all":
                stmt = stmt.where(HandoffRequest.status == status)
            stmt = stmt.order_by(desc(HandoffRequest.id)).limit(max(1, min(limit, 5000)))
            with self.session_factory() as session:
                rows = list(session.scalars(stmt))
            return [
                {
                    "id": row.id,
                    "conversation_id": row.conversation_id,
                    "reason": row.reason,
                    "target_group": row.target_group,
                    "status": row.status,
                    "payload": _json_loads(row.payload_json, {}),
                    "created_at": _iso(row.created_at),
                    "resolved_at": _iso(row.resolved_at),
                }
                for row in rows
            ]

    def resolve_handoff(self, row_id: int, *, status: str = "resolved", conversation_status: str | None = None) -> None:
            if status not in _ALLOWED_HANDOFF_STATUSES - {"pending"}:
                raise ValueError(f"转人工状态不合法: {status}")
            if conversation_status is not None and conversation_status not in _ALLOWED_CONVERSATION_STATUSES:
                raise ValueError(f"会话状态不合法: {conversation_status}")
            with self.session_factory() as session:
                row = session.get(HandoffRequest, int(row_id))
                if row is None:
                    raise KeyError(f"转人工记录不存在: {row_id}")
                row.status = status
                row.resolved_at = datetime.now()
                if conversation_status:
                    conversation = session.get(Conversation, row.conversation_id)
                    if conversation:
                        conversation.status = conversation_status
                        conversation.updated_at = datetime.now()
                session.commit()

    def get_settings(self, shop_key: str) -> dict[str, Any]:
            with self.session_factory() as session:
                row = session.scalar(select(ShopSettings).where(ShopSettings.shop_key == shop_key))
                if row is None:
                    row = ShopSettings(shop_key=shop_key)
                    session.add(row)
                    session.commit()
                return {
                    "shop_key": row.shop_key,
                    "shop_name": row.shop_name,
                    "auto_reply_enabled": row.auto_reply_enabled,
                    "ai_enabled": row.ai_enabled,
                    "max_history_messages": row.max_history_messages,
                    "handoff_reply": row.handoff_reply,
                    "fallback_reply": row.fallback_reply,
                }

    def update_settings(self, shop_key: str, **values: Any) -> dict[str, Any]:
            allowed = {"shop_name", "auto_reply_enabled", "ai_enabled", "max_history_messages", "handoff_reply", "fallback_reply"}
            unknown = set(values) - allowed
            if unknown:
                raise ValueError(f"不支持的店铺设置: {', '.join(sorted(unknown))}")
            with self.session_factory() as session:
                row = session.scalar(select(ShopSettings).where(ShopSettings.shop_key == shop_key))
                if row is None:
                    row = ShopSettings(shop_key=shop_key)
                    session.add(row)
                for key, value in values.items():
                    setattr(row, key, value)
                row.updated_at = datetime.now()
                session.commit()
            return self.get_settings(shop_key)

    def list_channel_accounts(self, shop_key: str) -> list[dict[str, Any]]:
            with self.session_factory() as session:
                rows = list(session.scalars(select(ChannelAccount).where(ChannelAccount.shop_key == shop_key).order_by(ChannelAccount.channel, ChannelAccount.display_name, ChannelAccount.account_key)))
            return [
                {
                    "id": row.id,
                    "channel": row.channel,
                    "account_key": row.account_key,
                    "display_name": row.display_name,
                    "transport_name": row.transport_name,
                    "enabled": row.enabled,
                    "settings": _json_loads(row.settings_json, {}),
                    "updated_at": _iso(row.updated_at),
                }
                for row in rows
            ]

    def save_channel_account(self, shop_key: str, *, channel: str, account_key: str, display_name: str = "", transport_name: str = "", enabled: bool = True, settings: dict[str, Any] | None = None, row_id: int | None = None) -> int:
            channel = str(channel or "").strip()
            account_key = str(account_key or "").strip()
            if not channel or not account_key:
                raise ValueError("渠道和账号标识不能为空")
            safe_settings = settings or {}
            secret_path = _contains_secret_key(safe_settings)
            if secret_path:
                raise ValueError(f"渠道设置不能保存凭据字段: {secret_path}")
            with self.session_factory() as session:
                row = session.get(ChannelAccount, int(row_id)) if row_id else None
                if row is None:
                    row = session.scalar(
                        select(ChannelAccount).where(
                            ChannelAccount.shop_key == shop_key,
                            ChannelAccount.channel == channel,
                            ChannelAccount.account_key == account_key,
                        )
                    )
                if row is None:
                    row = ChannelAccount(shop_key=shop_key, channel=channel, account_key=account_key)
                    session.add(row)
                elif row.shop_key != shop_key:
                    raise ValueError("不能跨店铺修改渠道账号")
                row.channel = channel
                row.account_key = account_key
                row.display_name = str(display_name or "").strip()
                row.transport_name = str(transport_name or "").strip()
                row.enabled = bool(enabled)
                row.settings_json = json.dumps(safe_settings, ensure_ascii=False)
                row.updated_at = datetime.now()
                session.commit()
                return row.id

    def delete_channel_account(self, row_id: int) -> bool:
            with self.session_factory() as session:
                row = session.get(ChannelAccount, int(row_id))
                if row is None:
                    return False
                session.delete(row)
                session.commit()
                return True
