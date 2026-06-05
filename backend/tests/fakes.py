"""Doubles de test pour les adapters (aucun I/O réseau)."""

from __future__ import annotations

from app.adapters.ports import CertProvider, PriceProvider

# Réponse /cards/{id} conforme à la doc PokeTrace (brut + gradé).
SAMPLE_CARD = {
    "id": "uuid-charizard",
    "name": "Charizard ex",
    "prices": {
        "NEAR_MINT": {
            "avg": 165, "low": 140, "high": 195,
            "saleCount": 89, "approxSaleCount": False,
            "avg1d": 162, "avg7d": 160, "avg30d": 155,
        },
        "LIGHTLY_PLAYED": {
            "avg": 120, "low": 100, "high": 140,
            "saleCount": 30, "approxSaleCount": True,
            "avg1d": 119, "avg7d": 118, "avg30d": 115,
        },
        "PSA_10": {
            "avg": 900, "low": 820, "high": 1000,
            "saleCount": 12, "approxSaleCount": False,
            "avg1d": 905, "avg7d": 890, "avg30d": 860,
        },
    },
}


class FakePriceProvider(PriceProvider):
    """Provider espion : enregistre les appels, ne fait aucun réseau."""

    def __init__(self, card: dict | None = None, search_hits: list[dict] | None = None):
        self.card = card or SAMPLE_CARD
        self.search_hits = search_hits if search_hits is not None else [self.card]
        self.search_calls: list[tuple] = []
        self.get_card_calls: list[tuple] = []
        self.history_calls: list[tuple] = []

    def search_cards(self, query: str, *, market: str, limit: int = 20) -> list[dict]:
        self.search_calls.append((query, market, limit))
        return self.search_hits

    def get_card(self, card_id: str, *, market: str) -> dict:
        self.get_card_calls.append((card_id, market))
        return self.card

    def get_price_history(self, card_id: str, tier: str, *, market: str) -> list[dict]:
        self.history_calls.append((card_id, tier, market))
        return []


class FakeCertProvider(CertProvider):
    def __init__(self, data: dict):
        self.data = data
        self.calls: list[str] = []

    def verify_cert(self, cert_number: str) -> dict:
        self.calls.append(cert_number)
        return self.data
