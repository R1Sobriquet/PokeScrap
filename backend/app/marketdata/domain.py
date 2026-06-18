"""DTO de la couche données marché (dataclasses, zéro I/O)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class WatchItem:
    """Cible de snapshot : identité interne + indices de requête pour les sources."""
    product_ref: str
    name: str
    product_type: str | None = None
    set_name: str | None = None
    number: str | None = None
    upc: str | None = None
    ppt_id: str | None = None  # identifiant côté agrégateur si connu


@dataclass(frozen=True)
class PriceQuote:
    """Prix courant d'un produit chez une source/marché (→ market_price_snapshots)."""
    product_ref: str
    source: str            # ppt|tcgdex|ebay|poketrace
    market: str            # us|eu
    price: Decimal | None
    currency: str = "EUR"
    product_type: str | None = None
    extra: dict = field(default_factory=dict)
    captured_at: dt.datetime | None = None


@dataclass(frozen=True)
class CatalogProduct:
    """Produit canonique (TCGdex) pour le matching multilingue."""
    canonical_id: str
    name: str
    set_id: str | None = None
    set_name: str | None = None
    number: str | None = None
    language: str | None = None
    upc: str | None = None


@dataclass(frozen=True)
class SetRelease:
    """Métadonnée de set pour l'auto-calendrier."""
    set_id: str
    set_name: str
    release_date: dt.date | None = None
    preorder_date: dt.date | None = None
    product_name: str | None = None
    product_type: str | None = None
