"""Modèle ORM ``match_review`` — file basse priorité des matchs ambigus.

Quand le matching produit↔canonique↔offre↔PokeTrace est sous le seuil de
confiance, le candidat va ici (surfacé dans le digest santé) — **sans rien
bloquer** : le produit reste snapshotté sur sa propre identité.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class MatchReview(Base):
    __tablename__ = "match_review"
    __table_args__ = (
        UniqueConstraint("product_ref", "candidate_ref", name="uq_match_review_pair"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    product_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    method: Mapped[str | None] = mapped_column(String(16), nullable=True)  # upc|set_number|fuzzy
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
