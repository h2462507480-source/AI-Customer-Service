from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config_models import ShopSettings


@dataclass(frozen=True)
class AISettings:
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: float = 30.0
    temperature: float = 0.2
    max_tokens: int = 220

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    @classmethod
    def from_env(cls) -> "AISettings":
        return cls(
            base_url=os.getenv("AI_BASE_URL", "").strip(),
            api_key=os.getenv("AI_API_KEY", "").strip(),
            model=os.getenv("AI_MODEL", "").strip(),
            timeout_seconds=float(os.getenv("AI_TIMEOUT_SECONDS", "30")),
            temperature=float(os.getenv("AI_TEMPERATURE", "0.2")),
            max_tokens=int(os.getenv("AI_MAX_TOKENS", "220")),
        )


class ShopSettingsService:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def get(self, shop_key: str) -> ShopSettings:
        with self.session_factory() as session:
            row = session.scalar(select(ShopSettings).where(ShopSettings.shop_key == shop_key))
            if row is None:
                row = ShopSettings(shop_key=shop_key)
                session.add(row)
                session.commit()
                session.refresh(row)
            session.expunge(row)
            return row

    def update(self, shop_key: str, **values) -> ShopSettings:
        allowed = {
            "shop_name",
            "auto_reply_enabled",
            "ai_enabled",
            "max_history_messages",
            "handoff_reply",
            "fallback_reply",
        }
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
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row
