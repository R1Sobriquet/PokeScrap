"""Modèle ORM ``users`` — identités multi-utilisateurs (SaaS).

Remplace le modèle mono-admin « username en .env + hash dans settings ». La ligne
de l'admin historique est créée idempotemment au boot (``ensure_admin_user``).
Les ENUM MySQL sont mappés ``String`` côté ORM (portabilité tests SQLite).

``current_tier`` : palier de capital PER-USER (reprend ``settings.current_tier_number``
de l'installation mono-user pour l'admin ; nouveau user → NULL = palier 1 au 1er calcul).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(8), nullable=False, default="user")      # admin|user
    plan: Mapped[str] = mapped_column(String(8), nullable=False, default="free")      # free|pro
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")  # pending|active|disabled
    email_verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    current_tier: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
