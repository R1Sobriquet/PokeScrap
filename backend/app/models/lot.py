"""Modèle ORM ``lots`` (achats groupés en attente d'intake)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class Lot(Base):
    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    source_listing_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sourcing_listings.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    platform: Mapped[str | None] = mapped_column(String(16), nullable=True)
    purchased_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="received")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
