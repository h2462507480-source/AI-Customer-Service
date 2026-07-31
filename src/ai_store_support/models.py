from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PhoneModelSupport(Base):
    __tablename__ = "phone_model_support"
    __table_args__ = (
        UniqueConstraint(
            "shop_key",
            "material_name",
            "brand",
            "normalized_model",
            name="uix_phone_model_support",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    material_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    brand: Mapped[str] = mapped_column(String(50), nullable=False, default="", index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    aliases_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    stock_status: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    source_file: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class UnknownPhoneModelQuery(Base):
    __tablename__ = "unknown_phone_model_query"
    __table_args__ = (
        UniqueConstraint(
            "shop_key",
            "brand",
            "normalized_model",
            name="uix_unknown_phone_model_query",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    brand: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    raw_query: Mapped[str] = mapped_column(Text, nullable=False, default="")
    query_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
