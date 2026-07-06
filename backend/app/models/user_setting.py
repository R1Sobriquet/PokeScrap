"""Modèle ORM ``user_settings`` — préférences PER-USER (overlay du registre global).

Le registre ``settings`` reste la source des **défauts** (~68 clés « préférence » :
paliers/cash, frais, discipline de vente, fiscalité, grading, affichage, notif…).
Une ligne ici ne fait qu'**écraser** la valeur pour UN utilisateur — zéro seeding
par user, fallback via ``services.user_settings.get_user_setting``.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class UserSetting(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        UniqueConstraint("user_id", "setting_key", name="uq_user_setting"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    setting_key: Mapped[str] = mapped_column(String(64), nullable=False)
    setting_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(16), nullable=False, default="string")
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
