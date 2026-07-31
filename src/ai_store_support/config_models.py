from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class ShopSettings(Base):
    __tablename__ = "shop_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    shop_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_history_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    handoff_reply: Mapped[str] = mapped_column(String(255), nullable=False, default="亲，这个问题需要人工确认，我马上帮您转接客服。")
    fallback_reply: Mapped[str] = mapped_column(String(255), nullable=False, default="亲，这个问题我暂时不能准确确认，我帮您转人工处理。")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entry"
    __table_args__ = (UniqueConstraint("shop_key", "title", name="uix_knowledge_entry_shop_title"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    direct_reply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class RoutingRule(Base):
    __tablename__ = "routing_rule"
    __table_args__ = (UniqueConstraint("shop_key", "name", name="uix_routing_rule_shop_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    keywords_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    match_type: Mapped[str] = mapped_column(String(20), nullable=False, default="contains")
    action: Mapped[str] = mapped_column(String(30), nullable=False, default="handoff")
    reply_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reason: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    target_group: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class ChannelAccount(Base):
    """Non-secret channel account metadata used by the desktop manager."""

    __tablename__ = "channel_account"
    __table_args__ = (
        UniqueConstraint("shop_key", "channel", "account_key", name="uix_channel_account"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default="pinduoduo")
    account_key: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    transport_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    settings_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
