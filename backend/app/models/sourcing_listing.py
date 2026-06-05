"""Modèle ORM ``sourcing_listings`` (annonces de sourcing)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import JSON, Computed, DateTime, Integer, Numeric, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class SourcingListing(Base):
    __tablename__ = "sourcing_listings"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str] = mapped_column(String(768), nullable=False)
    raw_title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    asking_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    protection_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    # Colonne générée STORED côté base (jamais insérée).
    acquisition_cost_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        Computed("asking_price + shipping_cost + protection_cost", persisted=True),
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    estimated_resale_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    ratio_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    passes_50_rule: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    filter_flags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    detected_products: Mapped[list | None] = mapped_column(JSON, nullable=True)
    estimated_total_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    listed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    detected_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    evaluated_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
