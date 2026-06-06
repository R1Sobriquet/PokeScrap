"""Modèle ORM ``grading_opportunities`` (comparateur de grading, gated Pro)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Numeric, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class GradingOpportunity(Base):
    __tablename__ = "grading_opportunities"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    raw_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    psa9_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    psa10_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    grading_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    premium_psa9_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    premium_psa10_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    expected_net_psa10: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    grade_probability: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expected_net_weighted: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_recommended: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
