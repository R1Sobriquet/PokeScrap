"""Modèle ORM ``daily_signals`` — signaux de sous-valorisation par carte×langue.

Recalculé 1×/jour sur l'historique ``card_price_snapshot``. Chaque ligne porte les
composantes (toutes normalisées ~[0,1]) et le ``score`` agrégé.

⚠️ Le ``score`` **CLASSE** des candidats à vérifier par un humain — il **ne
prédit pas** un prix. C'est un outil d'aide à la décision, jamais d'achat auto.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class DailySignal(Base):
    __tablename__ = "daily_signals"
    __table_args__ = (
        UniqueConstraint("card_id", "language", "computed_at", name="uq_daily_signal_day"),
        Index("idx_daily_signal_rank", "computed_at", "score"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    card_id: Mapped[str] = mapped_column(String(40), nullable=False)  # ID TCGdex
    language: Mapped[str] = mapped_column(String(2), nullable=False)  # EN|JP|FR
    price_eur: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Composantes du score (normalisées ~[0,1]).
    near_low: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    drawdown_sma: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    bottoming: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    cross_lang: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    liquidity: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    momentum_7d: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=0)
    budget_band: Mapped[str | None] = mapped_column(String(8), nullable=True)  # lt10|10_20|lte50
    buy_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    computed_at: Mapped[dt.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
