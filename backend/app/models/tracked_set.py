"""Modèle ORM ``tracked_sets`` (sets cibles de l'auto-watchlist)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class TrackedSet(Base):
    __tablename__ = "tracked_sets"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    set_slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    min_value_eur: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    include_single: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    include_sealed: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    included_families: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
