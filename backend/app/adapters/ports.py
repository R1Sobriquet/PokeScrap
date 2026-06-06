"""Ports (interfaces abstraites) des sources externes et de la notification.

Principe ports & adapters : le domaine et l'application dépendent de ces
interfaces, jamais d'une implémentation concrète. Les adapters réels (PokeTrace,
PSA, scraping, Discord) les implémentent derrière ces contrats. Cela rend le
code indifférent au mode (prototype US gratuit / réel EU payant) et testable.

``PriceProvider``/``CertProvider`` sont précisés au Jalon 2 (couche données) ;
``SourcingProvider``/``Notifier`` restent souples (``Any``) jusqu'aux jalons qui
les implémentent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PriceProvider(ABC):
    """Source de prix de marché (ex. PokeTrace).

    Le marché est passé explicitement (``US`` / ``EU``) : l'adapter est
    indifférent au mode, c'est l'appelant qui lit ``valuation_market`` via
    ``get_setting`` et le transmet.
    """

    @abstractmethod
    def search_cards(self, query: str, *, market: str, limit: int = 20) -> list[dict]:
        """Recherche des cartes par texte libre (``GET /cards``)."""
        raise NotImplementedError

    @abstractmethod
    def get_card(self, card_id: str, *, market: str) -> dict:
        """Détail d'une carte, incluant l'objet ``prices`` par tier."""
        raise NotImplementedError

    @abstractmethod
    def get_price_history(self, card_id: str, tier: str, *, market: str) -> list[dict]:
        """Historique de prix d'un tier (réservé au mode Pro/history)."""
        raise NotImplementedError


class CertProvider(ABC):
    """Source de certification / population (ex. PSA)."""

    @abstractmethod
    def verify_cert(self, cert_number: str) -> dict:
        """Vérifie un certificat → ``{grade, grade_label, is_valid, pop_data}``."""
        raise NotImplementedError


class SourcingProvider(ABC):
    """Source d'annonces de sourcing (Vinted, Leboncoin, …)."""

    @abstractmethod
    def fetch_listings(self, **kwargs: Any) -> Any:
        """Renvoie une liste d'annonces brutes à évaluer."""
        raise NotImplementedError


class Notifier(ABC):
    """Canal de notification sortant (ex. Discord).

    Reçoit des specs neutres (``EmbedSpec`` / ``ButtonSpec``) ; l'adapter concret
    les traduit vers son SDK. Le ``channel_key`` logique (``achats``/``ventes``/
    ``portefeuille``/``systeme``) est résolu en id réel par l'adapter.
    """

    @abstractmethod
    def send(self, channel_key: str, embed: Any, buttons: Any = (), *, ping: bool = False) -> Any:
        """Envoie un message (embed + boutons) sur un salon logique.

        ``ping=True`` mentionne l'utilisateur (alertes critiques).
        """
        raise NotImplementedError
