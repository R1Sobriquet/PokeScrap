"""Modèle ORM ``buy_rules`` — allow-list de l'achat ASSISTÉ (PokéStock FR Phase C).

Une règle autorise le **carting** (ajout panier) d'une offre sous plafonds stricts
(prix, quantité). **Aucun paiement automatisé** : l'humain finalise toujours
(paiement + 3DS). Rien hors d'une règle active n'est carté.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class BuyRule(Base):
    __tablename__ = "buy_rules"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    #: Propriétaire (multi-user Phase B). Nullable tant que la Phase C n'a pas
    #: threadé user_id dans les services ; re-backfillé puis NOT NULL ensuite.
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False)  # 'offer' | 'product_type'
    scope_value: Mapped[str] = mapped_column(String(64), nullable=False)
    retailer_id: Mapped[int | None] = mapped_column(
        ForeignKey("retailers.id", ondelete="SET NULL"), nullable=True
    )
    max_price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    max_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_enabled: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
