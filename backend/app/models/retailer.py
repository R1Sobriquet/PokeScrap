"""Modèle ORM ``retailers`` (détaillants FR suivis — PokéStock FR).

Source de vérité des cibles de veille stock. ``sitemap_url`` est éditable (le
radar nouveaux SKU lit l'URL confirmée via le ``robots.txt`` du site au go-live).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class Retailer(Base):
    __tablename__ = "retailers"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sitemap_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Phase A — endpoint XHR de dispo (JSON léger) ; placeholders {sku} {url}.
    # NULL → fallback sur le fetch de la page produit. Éditable (confirmé go-live).
    availability_url_template: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
