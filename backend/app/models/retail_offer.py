"""Modèle ORM ``retail_offers`` (un SKU chez un détaillant — PokéStock FR).

``url`` est la clé canonique (unique). ``current_stock_state`` est un ENUM en base
(``schema.sql``) mais mappé en ``String`` ici, comme les autres modèles, pour la
portabilité des tests SQLite. ``product_id`` est le **point d'extension** vers le
produit interne PokeTrace (scalping futur) : nullable, ``ON DELETE SET NULL``.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class RetailOffer(Base):
    __tablename__ = "retail_offers"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    retailer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("retailers.id", ondelete="CASCADE"), nullable=False
    )
    retailer_sku: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    product_type: Mapped[str] = mapped_column(String(16), nullable=False, default="autre")
    current_stock_state: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    is_watched: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    # Phase A — hot-list à plusieurs niveaux : 'hot' | 'normal' | 'cold'.
    watch_tier: Mapped[str] = mapped_column(String(8), nullable=False, default="normal")
    # Requête conditionnelle (ETag) sur l'endpoint de dispo (économie d'octets).
    availability_etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    first_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    last_checked_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    last_changed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
