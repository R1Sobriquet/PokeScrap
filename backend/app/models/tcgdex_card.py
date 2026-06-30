"""Modèle ORM ``tcgdex_card`` — registre canonique des cartes (clé TCGdex).

``card_id`` = identifiant TCGdex (ex. ``swsh3-136``). C'est **la clé de jointure
canonique** de la couche Market Intelligence : toute source (Cardmarket, PPT,
eBay) s'y rattache via le matcher, ce qui résout le « slug mismatch » entre
sources. Les noms multilingues servent au matching (Cardmarket FR/EN, PPT EN).

Peuplé par ``app.marketwatch.registry`` depuis le catalogue TCGdex (gratuit, sans
clé). Les ENUM MySQL sont mappés ``String`` côté ORM (portabilité tests SQLite).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TcgdexCard(Base):
    __tablename__ = "tcgdex_card"

    #: ID TCGdex (clé naturelle, ex. ``sv03.5-161``). Pas d'auto-increment.
    card_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    set_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    set_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rarity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Nom du Pokémon de base (ex. ``Umbreon``) — sert au tier de popularité.
    pokemon: Mapped[str | None] = mapped_column(String(96), nullable=True)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_fr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_jp: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
