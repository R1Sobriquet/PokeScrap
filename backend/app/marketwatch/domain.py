"""DTO de la couche Market Intelligence (dataclasses, zéro I/O).

Argent en ``Decimal`` (jamais de float). ``CardSnapshot`` mappe directement la
table ``card_price_snapshot`` ; ``RegistryCard`` et ``CardmarketProduct`` sont les
entrées du matcher.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

#: Sources reconnues (= ENUM ``card_price_snapshot.source``).
SOURCES = ("cardmarket", "ppt", "tcgplayer", "ebay_active")
#: Langues reconnues (= ENUM ``card_price_snapshot.language``), priorité décroissante.
LANGUAGES = ("EN", "JP", "FR")


@dataclass(frozen=True)
class CardSnapshot:
    """Un prix d'une carte chez une source, pour un jour donné (→ card_price_snapshot)."""
    card_id: str            # ID TCGdex (clé canonique)
    source: str             # cardmarket|ppt|tcgplayer|ebay_active
    language: str           # EN|JP|FR
    price_eur: Decimal
    condition_grade: str = "NM_RAW"
    price_native: Decimal | None = None
    currency: str | None = None
    trend_eur: Decimal | None = None
    active_listings: int | None = None
    watchers: int | None = None
    captured_at: dt.date | None = None
    meta: dict = field(default_factory=dict)  # diagnostic (non persisté)


@dataclass(frozen=True)
class RegistryCard:
    """Carte du registre canonique TCGdex (entrée du matcher)."""
    card_id: str
    set_id: str | None = None
    set_name: str | None = None
    number: str | None = None
    name_en: str | None = None
    name_fr: str | None = None
    name_jp: str | None = None

    def names(self) -> tuple[str, ...]:
        return tuple(n for n in (self.name_en, self.name_fr, self.name_jp) if n)


@dataclass(frozen=True)
class CardmarketProduct:
    """Ligne du catalogue produits Cardmarket (idProduct ↔ carte)."""
    id_product: str
    name: str
    expansion: str | None = None
    number: str | None = None


@dataclass(frozen=True)
class MatchResult:
    """Résultat du matcher : carte canonique + confiance + méthode."""
    card_id: str
    confidence: float       # 0..1
    method: str             # set_number|name
