"""Modèle ORM ``alerts``.

Au Jalon 2, on n'écrit que des alertes ``tech_error`` (quota/indispo). L'envoi
Discord viendra au Jalon 4 ; ici, la persistance en base suffit. Seule la FK vers
``products`` est déclarée côté ORM (les autres cibles restent de simples colonnes
pour rester portable en test ; la base réelle porte les FK complètes).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    sourcing_listing_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    position_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    sent_to_discord_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
