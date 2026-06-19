"""Ports PokéStock FR (interfaces abstraites).

``RetailSourcePort`` : contrat d'une source détaillant (sitemap + page produit).
La notification réutilise le port ``Notifier`` existant (``app.adapters.ports``) :
le job écrit une ligne ``alerts`` que le dispatcher du bot pousse vers Discord et
Telegram — pas de mécanisme parallèle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from app.retail.domain import OfferSnapshot, Retailer, SkuRef


class RetailSourcePort(ABC):
    """Source d'un détaillant : catalogue (sitemap) + état d'une offre (page produit)."""

    @abstractmethod
    def list_catalog_skus(self, retailer: Retailer) -> Iterable[SkuRef]:
        """Énumère les SKU produits depuis le sitemap (radar nouveaux SKU)."""
        raise NotImplementedError

    @abstractmethod
    def fetch_offer(self, url: str) -> OfferSnapshot:
        """Récupère l'état stock + prix d'une page produit (JSON-LD, fallback DOM)."""
        raise NotImplementedError
