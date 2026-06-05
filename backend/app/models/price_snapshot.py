"""Modèle ORM ``price_snapshots``."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    market: Mapped[str | None] = mapped_column(String(2), nullable=True)
    marketplace: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grade_company: Mapped[str] = mapped_column(String(8), nullable=False, default="RAW")
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    condition_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    price_avg: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_low: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_high: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    avg_1d: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    avg_7d: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    avg_30d: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sale_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approx_sale_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    captured_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
