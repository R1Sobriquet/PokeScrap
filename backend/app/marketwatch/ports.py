"""``CardPriceSource`` — interface unique des sources de prix carte-centric.

Ajouter une source = un adapter implémentant ``fetch()``. Le contrat est
volontairement minimal (``fetch() -> list[CardSnapshot]``) ; la résolution des
clés/secrets, les quotas et les garde-fous sont portés par le JOB d'ingestion.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.marketwatch.domain import CardSnapshot


class CardPriceSource(ABC):
    #: identifiant ENUM persisté : 'cardmarket' | 'ppt' | 'tcgplayer' | 'ebay_active'
    code: str = "unknown"

    @abstractmethod
    def fetch(self) -> list[CardSnapshot]:
        """Renvoie les snapshots du jour (déjà mappés sur des card_id TCGdex)."""
        raise NotImplementedError
