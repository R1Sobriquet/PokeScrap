"""Modèle ORM ``market_price_snapshots`` — le moat de données possédé.

Un snapshot par ``(product_ref, source, market, captured_date)`` (contrainte
unique → job idempotent, re-run safe). ``product_ref`` = identité canonique
interne (``products.id`` si matché, sinon ``"<source>:<external_id>"``). Les
ENUM du schéma MySQL sont mappés ``String`` côté ORM (portabilité tests SQLite).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import JSON, CHAR, Date, DateTime, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class MarketPriceSnapshot(Base):
    __tablename__ = "market_price_snapshots"
    __table_args__ = (
        UniqueConstraint("product_ref", "source", "market", "captured_date",
                         name="uq_market_snapshot_day"),
        Index("idx_market_ref_date", "product_ref", "captured_date"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    product_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # ppt|tcgdex|ebay|poketrace
    market: Mapped[str] = mapped_column(String(2), nullable=False)   # us|eu
    product_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="EUR")
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    captured_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    captured_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
