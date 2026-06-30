"""Modèle ORM ``popularity_tier`` — signal « soft » éditable à la main.

La popularité d'une carte/d'un Pokémon n'est pas automatisable de façon fiable :
on la saisit manuellement (S/A/B/C) et elle pondère le score (``tier_multiplier``).
Le ciblage peut se faire par ``card_id`` (TCGdex, précis) **ou** par ``pokemon``
(nom de base, plus large) ; au moins l'un des deux est renseigné.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class PopularityTier(Base):
    __tablename__ = "popularity_tier"
    __table_args__ = (
        # NULL multiples autorisés (MySQL/SQLite) : une ligne cible card_id OU pokemon.
        UniqueConstraint("card_id", name="uq_popularity_card"),
        UniqueConstraint("pokemon", name="uq_popularity_pokemon"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    card_id: Mapped[str | None] = mapped_column(String(40), nullable=True)   # ID TCGdex
    pokemon: Mapped[str | None] = mapped_column(String(96), nullable=True)   # nom de base
    tier: Mapped[str] = mapped_column(String(1), nullable=False)             # S|A|B|C
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
