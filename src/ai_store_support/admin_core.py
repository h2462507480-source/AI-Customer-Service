from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import distinct, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .config_models import ChannelAccount, KnowledgeEntry, ShopSettings
from .conversation_models import Conversation, HandoffRequest
from .models import PhoneModelSupport, UnknownPhoneModelQuery

_ALLOWED_UNKNOWN_STATUSES = {"pending", "resolved", "ignored"}
_ALLOWED_CONVERSATION_STATUSES = {"ai", "human", "closed"}
_ALLOWED_HANDOFF_STATUSES = {"pending", "resolved", "cancelled", "failed"}
_SECRET_MARKERS = ("cookie", "token", "password", "secret", "api_key", "apikey", "credential")


def _iso(value: datetime | None) -> str:
    return value.isoformat(timespec="seconds") if value else ""


def _json_loads(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def _contains_secret_key(value: Any, path: str = "settings") -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower().replace("-", "_")
            if any(marker in key_text for marker in _SECRET_MARKERS):
                return f"{path}.{key}"
            found = _contains_secret_key(nested, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found = _contains_secret_key(nested, f"{path}[{index}]")
            if found:
                return found
    return None


class AdminCoreMixin:

    def __init__(self, session_factory: Callable[[], Session], engine: Engine | None = None):
            self.session_factory = session_factory
            self.engine = engine

    def list_shops(self) -> list[str]:
            tables = (
                (ShopSettings, ShopSettings.shop_key),
                (PhoneModelSupport, PhoneModelSupport.shop_key),
                (KnowledgeEntry, KnowledgeEntry.shop_key),
                (Conversation, Conversation.shop_key),
                (ChannelAccount, ChannelAccount.shop_key),
            )
            shops: set[str] = set()
            with self.session_factory() as session:
                for model, column in tables:
                    shops.update(str(item) for item in session.scalars(select(distinct(column))) if item)
            return sorted(shops)

    def dashboard(self, shop_key: str) -> dict[str, int]:
            with self.session_factory() as session:
                scalar = session.scalar
                return {
                    "models": int(scalar(select(func.count()).select_from(PhoneModelSupport).where(PhoneModelSupport.shop_key == shop_key)) or 0),
                    "supported_models": int(scalar(select(func.count()).select_from(PhoneModelSupport).where(PhoneModelSupport.shop_key == shop_key, PhoneModelSupport.supported.is_(True))) or 0),
                    "unknown_pending": int(scalar(select(func.count()).select_from(UnknownPhoneModelQuery).where(UnknownPhoneModelQuery.shop_key == shop_key, UnknownPhoneModelQuery.status == "pending")) or 0),
                    "unknown_queries": int(scalar(select(func.coalesce(func.sum(UnknownPhoneModelQuery.query_count), 0)).where(UnknownPhoneModelQuery.shop_key == shop_key)) or 0),
                    "knowledge_enabled": int(scalar(select(func.count()).select_from(KnowledgeEntry).where(KnowledgeEntry.shop_key == shop_key, KnowledgeEntry.enabled.is_(True))) or 0),
                    "conversations_ai": int(scalar(select(func.count()).select_from(Conversation).where(Conversation.shop_key == shop_key, Conversation.status == "ai")) or 0),
                    "conversations_human": int(scalar(select(func.count()).select_from(Conversation).where(Conversation.shop_key == shop_key, Conversation.status == "human")) or 0),
                    "handoffs_pending": int(scalar(select(func.count()).select_from(HandoffRequest).where(HandoffRequest.shop_key == shop_key, HandoffRequest.status == "pending")) or 0),
                    "channel_accounts": int(scalar(select(func.count()).select_from(ChannelAccount).where(ChannelAccount.shop_key == shop_key, ChannelAccount.enabled.is_(True))) or 0),
                }
