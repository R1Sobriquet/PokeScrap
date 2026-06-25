"""Modèle ORM ``offer_store_availability`` — dispo d'une offre par magasin.

Un état par ``(offer_id, store_id)`` (contrainte unique → upsert idempotent).
``availability_state`` : in_store / out_of_store / limited / unknown.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class OfferStoreAvailability(Base):
    __tablename__ = "offer_store_availability"
    __table_args__ = (UniqueConstraint("offer_id", "store_id", name="uq_offer_store"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    offer_id: Mapped[int] = mapped_column(
        ForeignKey("retail_offers.id", ondelete="CASCADE"), nullable=False
    )
    store_id: Mapped[int] = mapped_column(
        ForeignKey("store_locations.id", ondelete="CASCADE"), nullable=False
    )
    availability_state: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    price: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    last_checked_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    last_changed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
