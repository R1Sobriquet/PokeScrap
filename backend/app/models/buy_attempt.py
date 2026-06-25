"""Modèle ORM ``buy_attempts`` — audit log de l'achat assisté (PokéStock FR Phase C).

Trace chaque tentative : carté / bloqué / sauté (plafond) / dry-run. Aucune
donnée de paiement n'est jamais stockée.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class BuyAttempt(Base):
    __tablename__ = "buy_attempts"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    offer_id: Mapped[int] = mapped_column(
        ForeignKey("retail_offers.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(8), nullable=False, default="online")  # online|store
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # carted|blocked|skipped|dry_run
    cart_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
