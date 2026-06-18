"""``MarketDataPort`` — interface unique des sources de données marché.

Capacités déclarées par ``capabilities`` (``"quotes"`` / ``"catalog"`` /
``"releases"``) ; les méthodes non supportées renvoient ``[]`` par défaut. Ajouter
une source = un nouvel adapter implémentant ce port (zéro changement appelant).
"""

from __future__ import annotations

from abc import ABC
from collections.abc import Iterable

from app.marketdata.domain import CatalogProduct, PriceQuote, SetRelease, WatchItem


class MarketDataPort(ABC):
    #: identifiant ENUM persisté : 'ppt' | 'tcgdex' | 'ebay' | 'poketrace'
    code: str = "unknown"
    #: sous-ensemble de {"quotes", "catalog", "releases"}
    capabilities: frozenset[str] = frozenset()

    def fetch_quotes(self, items: Iterable[WatchItem]) -> list[PriceQuote]:
        """Prix courants pour des produits watchés (PPT, eBay)."""
        return []

    def list_catalog(self) -> list[CatalogProduct]:
        """Catalogue canonique multilingue (TCGdex)."""
        return []

    def list_releases(self) -> list[SetRelease]:
        """Dates de sortie de sets pour l'auto-calendrier (TCGdex, PPT)."""
        return []
