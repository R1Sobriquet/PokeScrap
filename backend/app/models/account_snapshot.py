"""Modèle ORM ``account_snapshots`` (photo quotidienne des KPIs)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[dt.date] = mapped_column(Date, unique=True, nullable=False)
    total_portfolio_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    capital_invested: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cash_available: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cash_locked: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    cash_active: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    realized_profit_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    capital_rotation_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    turnover_cumulative: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    current_tier_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tiers_config.id", ondelete="SET NULL"), nullable=True
    )
    tax_provision: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
