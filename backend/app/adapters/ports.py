"""Ports (interfaces abstraites) des sources externes et de la notification.

Principe ports & adapters : le domaine et l'application dépendent de ces
interfaces, jamais d'une implémentation concrète. Les adapters réels (PokeTrace,
PSA, scraping, Discord) les implémentent derrière ces contrats. Cela rend le
code indifférent au mode (prototype US gratuit / réel EU payant) et testable.

Les types de retour restent volontairement souples (``Any``) au Jalon 1 : les
DTO précis seront définis avec la logique métier des jalons suivants.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PriceProvider(ABC):
    """Source de prix de marché (ex. PokeTrace)."""

    @abstractmethod
    def get_price(self, product_ref: str, **kwargs: Any) -> Any:
        """Renvoie un instantané de prix pour une référence produit."""
        raise NotImplementedError


class CertProvider(ABC):
    """Source de certification / population (ex. PSA)."""

    @abstractmethod
    def get_cert(self, cert_number: str, **kwargs: Any) -> Any:
        """Renvoie les données de certification d'un slab gradé."""
        raise NotImplementedError


class SourcingProvider(ABC):
    """Source d'annonces de sourcing (Vinted, Leboncoin, …)."""

    @abstractmethod
    def fetch_listings(self, **kwargs: Any) -> Any:
        """Renvoie une liste d'annonces brutes à évaluer."""
        raise NotImplementedError


class Notifier(ABC):
    """Canal de notification sortant (ex. Discord)."""

    @abstractmethod
    def notify(self, channel: str, message: str, **kwargs: Any) -> Any:
        """Envoie un message sur un canal donné."""
        raise NotImplementedError
