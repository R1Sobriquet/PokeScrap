"""Modèle ORM ``card_price_snapshot`` — série temporelle de prix par carte.

Un snapshot par ``(card_id, source, language, condition_grade, captured_at)``
(contrainte unique → ingestion idempotente, re-run safe). ``card_id`` = ID
TCGdex (cf. ``tcgdex_card``). Tout en ``DECIMAL`` (jamais de float).

Nommé ``card_price_snapshot`` (et non ``price_snapshot``) pour ne pas entrer en
collision avec la table ``price_snapshots`` historique (prix watchlist par
``product_id``). Les ENUM MySQL sont mappés ``String`` côté ORM (tests SQLite).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import CHAR, Date, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class CardPriceSnapshot(Base):
    __tablename__ = "card_price_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "card_id", "source", "language", "condition_grade", "captured_at",
            name="uq_card_price_day",
        ),
        Index("idx_card_price_lookup", "card_id", "language", "captured_at"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    card_id: Mapped[str] = mapped_column(String(40), nullable=False)  # ID TCGdex
    source: Mapped[str] = mapped_column(String(16), nullable=False)   # cardmarket|ppt|tcgplayer|ebay_active
    language: Mapped[str] = mapped_column(String(2), nullable=False)  # EN|JP|FR
    condition_grade: Mapped[str] = mapped_column(String(12), nullable=False, default="NM_RAW")
    price_eur: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price_native: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(CHAR(3), nullable=True)
    trend_eur: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    active_listings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    watchers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captured_at: Mapped[dt.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
