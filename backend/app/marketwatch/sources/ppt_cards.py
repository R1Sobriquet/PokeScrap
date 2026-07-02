"""Source PokemonPriceTracker carte-centric — réutilise l'adapter PPT existant.

PPT renvoie deux marchés depuis une requête : US (TCGplayer, USD) et EU
(Cardmarket, EUR). On les mappe sur des ``CardSnapshot`` carte-centric :
  * US  → source ``tcgplayer`` (``price_native`` USD, ``price_eur`` = USD×fx) ;
  * EU  → source ``ppt``       (``price_eur`` EUR).
Langue ``EN`` (PPT couvre le marché occidental). Quota oblige : on ne passe QUE
les cartes ciblées (``targets``, typiquement la watchlist matchée), bornées amont.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Sequence
from decimal import Decimal

from app.marketdata.domain import WatchItem
from app.marketwatch.domain import CardSnapshot, RegistryCard
from app.marketwatch.ports import CardPriceSource

logger = logging.getLogger("marketwatch.ppt")


class PptCardSource(CardPriceSource):
    code = "ppt"

    def __init__(self, targets: Sequence[RegistryCard], adapter, *,
                 fx_usd_eur: float, captured_at: dt.date):
        self._targets = list(targets)
        self._adapter = adapter
        self._fx = Decimal(str(fx_usd_eur))
        self._captured_at = captured_at

    def fetch(self) -> list[CardSnapshot]:
        out: list[CardSnapshot] = []
        for card in self._targets:
            name = card.name_en or card.name_fr or card.name_jp
            if not name:
                continue
            item = WatchItem(product_ref=card.card_id, name=name,
                             set_name=card.set_name, number=card.number)
            try:
                quotes = self._adapter.fetch_quotes([item])
            except Exception:  # noqa: BLE001 - une carte KO ne casse pas le run
                logger.exception("ppt: échec fetch %s", card.card_id)
                continue
            for q in quotes:
                if q.price is None:
                    continue
                if q.market == "us":
                    out.append(CardSnapshot(
                        card_id=card.card_id, source="tcgplayer", language="EN",
                        price_eur=(q.price * self._fx).quantize(Decimal("0.01")),
                        price_native=q.price, currency="USD", captured_at=self._captured_at))
                elif q.market == "eu":
                    out.append(CardSnapshot(
                        card_id=card.card_id, source="ppt", language="EN",
                        price_eur=q.price, price_native=q.price, currency="EUR",
                        captured_at=self._captured_at))
        return out
