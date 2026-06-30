"""Modèle ORM ``catalyst_event`` — catalyseurs marché éditables à la main.

Événements connus qui peuvent porter la demande (set anniversaire, rotation
format, sortie de jeu vidéo…). Saisis à la main ; un catalyseur à moins de
``CATALYST_HORIZON_DAYS`` jours applique un bonus au score (``catalyst_bonus``).
``scope`` cible la portée : ``global``, un set (``set:sv03.5``) ou un Pokémon
(``pokemon:Umbreon``).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class CatalystEvent(Base):
    __tablename__ = "catalyst_event"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    event_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    scope: Mapped[str] = mapped_column(String(96), nullable=False, default="global")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
