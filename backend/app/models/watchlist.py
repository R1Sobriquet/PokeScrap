"""Modèle ORM ``watchlist``."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class Watchlist(Base):
    __tablename__ = "watchlist"
    # Unicité PAR USER (l'ancienne unicité globale product_id interdisait à deux
    # utilisateurs de suivre la même carte).
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_watch_user_product"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    #: Propriétaire (multi-user Phase B). Nullable tant que la Phase C n'a pas
    #: threadé user_id dans les services ; re-backfillé puis NOT NULL ensuite.
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    tier: Mapped[str] = mapped_column(String(8), nullable=False, default="B")
    is_trinity: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_illustration_rare: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    min_discount_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    target_resale_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority_coef: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=1)
    keywords: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'manual' (ajout utilisateur, jamais écrasé par le sync) | 'auto' (peuplé par set).
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
