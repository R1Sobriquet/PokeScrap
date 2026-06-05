"""Modèle ORM de la table ``tiers_config`` (paliers de capital)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import JSON, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class TierConfig(Base):
    __tablename__ = "tiers_config"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    tier_number: Mapped[int] = mapped_column(SmallInteger, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    capital_min: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    capital_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    alloc_stock_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    alloc_cash_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    cash_min_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    strategy_mix: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
