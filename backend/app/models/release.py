"""Modèle ORM ``releases`` (calendrier de sorties curé à la main — PokéStock FR)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class Release(Base):
    __tablename__ = "releases"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    set_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    release_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    preorder_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    source_note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
