"""Modèle ORM ``positions``.

Inclut les colonnes exploitées par le moteur de vente (réf. S5) : prix cible,
base capital initiale, réserve spéculative et les drapeaux d'étape ``stage_*``
qui garantissent l'idempotence (chaque étape ne se déclenche qu'une fois).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    lot_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    grade_company: Mapped[str] = mapped_column(String(8), nullable=False, default="RAW")
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    acquired_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    target_sell_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    initial_capital_basis: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_speculative_reserve: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    stage_capital_secured: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    stage_structured: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    stage_forced: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="held")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
