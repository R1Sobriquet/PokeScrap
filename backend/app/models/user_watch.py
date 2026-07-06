"""Modèles ORM des intentions de veille PER-USER (overlay des lignes partagées).

Historique mono-user : ``retail_offers.is_watched/watch_tier`` et
``store_locations.is_watched`` vivaient SUR les lignes partagées — le watch d'un
user aurait piloté la cadence de crawl de tout le monde. Ces tables portent
l'intention par utilisateur ; les flags dénormalisés des lignes partagées
deviennent l'**union** des watchers (hot = tier max), recalculée par les services.

``user_listing_status`` : statut personnel (watch/bought/dismissed…) d'une
annonce de sourcing partagée (``sourcing_listings`` reste une ligne globale).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class UserWatchedOffer(Base):
    __tablename__ = "user_watched_offers"
    __table_args__ = (
        UniqueConstraint("user_id", "offer_id", name="uq_user_watched_offer"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    offer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("retail_offers.id", ondelete="CASCADE"), nullable=False
    )
    watch_tier: Mapped[str] = mapped_column(String(8), nullable=False, default="normal")  # hot|normal|cold
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class UserWatchedStore(Base):
    __tablename__ = "user_watched_stores"
    __table_args__ = (
        UniqueConstraint("user_id", "store_id", name="uq_user_watched_store"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("store_locations.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class UserListingStatus(Base):
    __tablename__ = "user_listing_status"
    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", name="uq_user_listing"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    listing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sourcing_listings.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
