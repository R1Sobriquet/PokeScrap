"""Modèle ORM ``store_locations`` — magasins physiques suivis (PokéStock FR Phase B).

Dispo en magasin via le widget « disponible en magasin / click & collect » des
enseignes. ``store_code`` = identifiant interne du magasin côté enseigne
(éditable, confirmé à l'inspection). Liste volontairement courte (zone Agen).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class StoreLocation(Base):
    __tablename__ = "store_locations"
    __table_args__ = (UniqueConstraint("retailer_id", "store_code", name="uq_store_retailer_code"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    retailer_id: Mapped[int] = mapped_column(
        ForeignKey("retailers.id", ondelete="CASCADE"), nullable=False
    )
    store_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    city: Mapped[str | None] = mapped_column(String(96), nullable=True)
    postal: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_watched: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
