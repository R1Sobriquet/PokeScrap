"""Modèle ORM ``retail_stock_events`` (transitions d'état détectées — PokéStock FR)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class RetailStockEvent(Base):
    __tablename__ = "retail_stock_events"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    offer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("retail_offers.id", ondelete="CASCADE"), nullable=False
    )
    from_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_state: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    # Phase A — latence in-pipeline détection→alerte (instrumentation).
    detected_to_alert_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
