"""Modèle ORM ``products``.

Les colonnes ENUM du schéma MySQL sont mappées en ``String`` côté ORM : la base
reste la garante des valeurs (ENUM réel via ``schema.sql``), et l'ORM gagne en
portabilité (tests SQLite) et en souplesse d'écriture.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    product_type: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    set_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    set_slug: Mapped[str | None] = mapped_column(String(128), nullable=True)
    card_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    variant: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rarity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="EN")
    poketrace_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    cardmarket_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tcgplayer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
