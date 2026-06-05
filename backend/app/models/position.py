"""Modèle ORM ``positions`` (sous-ensemble utile au Jalon 3).

Le portefeuille n'est lu qu'en agrégat (``avg_cost × quantity``) au Jalon 3 ; le
ledger complet (stages de vente, réserve spéculative…) sera exploité au Jalon 5.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, func
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
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="held")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
