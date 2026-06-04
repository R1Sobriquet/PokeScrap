"""Modèle ORM de la table ``settings`` (registre des paramètres métier)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    setting_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    setting_value: Mapped[str] = mapped_column(String(255), nullable=False)
    value_type: Mapped[str] = mapped_column(
        Enum("int", "decimal", "bool", "string", "json"),
        nullable=False,
        default="string",
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
