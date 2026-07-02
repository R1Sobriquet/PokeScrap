"""Source eBay « annonces ACTIVES » — réutilise l'adapter eBay Browse existant.

Browse API uniquement : ``item_summary/search`` pour les annonces actives (prix
DEMANDÉS, agrégats count/min/median — jamais d'annonce individuelle stockée, TOS
eBay) + ``getItem`` pour les ``watchers`` (proxy de demande). Les prix VENDUS sont
verrouillés côté API → on ne les cherche pas.

Marché eBay FR pour le contexte FR (langue ``FR``). ``watchers`` est best-effort :
fourni par un callable injectable ``watchers_for(card)`` (``None`` si indisponible).
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Sequence

from app.marketdata.domain import WatchItem
from app.marketwatch.domain import CardSnapshot, RegistryCard
from app.marketwatch.ports import CardPriceSource

logger = logging.getLogger("marketwatch.ebay")


class EbayActiveCardSource(CardPriceSource):
    code = "ebay_active"

    def __init__(self, targets: Sequence[RegistryCard], adapter, *,
                 captured_at: dt.date, language: str = "FR", watchers_for=None):
        self._targets = list(targets)
        self._adapter = adapter
        self._captured_at = captured_at
        self._language = language
        self._watchers_for = watchers_for  # callable(card) -> int|None (getItem)

    def fetch(self) -> list[CardSnapshot]:
        out: list[CardSnapshot] = []
        for card in self._targets:
            name = card.name_en or card.name_fr or card.name_jp
            if not name:
                continue
            query = " ".join(p for p in (name, card.set_name, card.number) if p)
            item = WatchItem(product_ref=card.card_id, name=query,
                             set_name=card.set_name, number=card.number)
            try:
                quotes = self._adapter.fetch_quotes([item])
            except Exception:  # noqa: BLE001
                logger.exception("ebay: échec fetch %s", card.card_id)
                continue
            for q in quotes:
                if q.price is None:
                    continue
                extra = q.extra or {}
                watchers = None
                if self._watchers_for is not None:
                    try:
                        watchers = self._watchers_for(card)
                    except Exception:  # noqa: BLE001
                        watchers = None
                out.append(CardSnapshot(
                    card_id=card.card_id, source="ebay_active", language=self._language,
                    price_eur=q.price, price_native=q.price, currency="EUR",
                    active_listings=extra.get("count"), watchers=watchers,
                    captured_at=self._captured_at))
        return out
