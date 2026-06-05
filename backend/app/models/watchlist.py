"""Modèle ORM ``watchlist``."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    tier: Mapped[str] = mapped_column(String(8), nullable=False, default="B")
    is_trinity: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_illustration_rare: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    min_discount_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    target_resale_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority_coef: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=1)
    keywords: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
