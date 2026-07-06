"""Modèle ORM ``auth_sessions`` — refresh tokens opaques, rotatifs, révocables.

Le refresh token n'est JAMAIS stocké en clair : seule son empreinte SHA-256
(``refresh_hash``) est persistée. Rotation : chaque ``/auth/refresh`` révoque la
ligne courante et en émet une nouvelle ; le logout révoque. Un token présenté
mais déjà révoqué/expiré → 401 (et révocation de toute la famille en cas de
réutilisation détectée — vol probable).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
