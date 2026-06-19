"""Modèle ORM ``data_quarantine`` — données rejetées par les garde-fous.

Un prix qui échoue aux bornes de sanité / cohérence devise / dédup / détection
d'outlier atterrit ici (jamais dans la donnée propre). Les compteurs alimentent
le digest santé.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class DataQuarantine(Base):
    __tablename__ = "data_quarantine"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    product_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
