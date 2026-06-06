"""Modèle ORM ``lot_items`` (pièces issues de la segmentation d'un lot)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class LotItem(Base):
    __tablename__ = "lot_items"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    lot_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("lots.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    segmentation: Mapped[str] = mapped_column(String(16), nullable=False, default="individual")
    estimated_unit_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    bulk_group_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_platform: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
