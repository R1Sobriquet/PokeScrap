"""Adapter PokemonPriceTracker (source primaire) — prix scellés USD + EUR.

Quota free 100 req/jour → le JOB ne passe QUE les produits ``is_watched`` et
plafonne via ``RequestBudget``. Auth Bearer. Parsing **défensif** (l'API tierce
peut varier : on tente plusieurs chemins de champs). Une requête par produit ;
deux marchés (us=tcgplayer, eu=cardmarket) extraits de la même réponse.

NOTE: ajuster ``PPT_BASE`` / les chemins de parsing si la doc de l'API diffère —
isolé ici, sans impact sur le reste.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

from app.marketdata.domain import PriceQuote, SetRelease, WatchItem
from app.marketdata.http import JsonGet, httpx_json_get
from app.marketdata.ports import MarketDataPort

logger = logging.getLogger("marketdata.ppt")

PPT_BASE = "https://www.pokemonpricetracker.com/api/v1"


def _dec(v) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _dig(obj, *paths):
    """Renvoie la 1re valeur trouvée parmi des chemins ('a.b.c')."""
    for path in paths:
        cur = obj
        ok = True
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and cur not in (None, ""):
            return cur
    return None


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class PokemonPriceTrackerAdapter(MarketDataPort):
    code = "ppt"
    capabilities = frozenset({"quotes", "releases"})

    def __init__(self, *, api_key: str, http: JsonGet | None = None):
        self._key = api_key
        self._get = http or httpx_json_get

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._key}", "Accept": "application/json"}

    def _query(self, item: WatchItem) -> dict:
        if item.ppt_id:
            return {"id": item.ppt_id}
        params = {"name": item.name}
        if item.set_name:
            params["set"] = item.set_name
        return params

    def fetch_quotes(self, items: Iterable[WatchItem]) -> list[PriceQuote]:
        quotes: list[PriceQuote] = []
        now = _utcnow()
        for item in items:
            status, data = self._get(f"{PPT_BASE}/prices", headers=self._headers(),
                                     params=self._query(item))
            if status >= 400 or not data:
                logger.info("PPT: pas de prix pour %s (status %s).", item.product_ref, status)
                continue
            node = data.get("data") if isinstance(data, dict) and "data" in data else data
            if isinstance(node, list):
                node = node[0] if node else {}
            usd = _dec(_dig(node, "prices.tcgplayer.market", "prices.tcgplayer", "usd", "marketPrice"))
            eur = _dec(_dig(node, "prices.cardmarket.market", "prices.cardmarket", "eur"))
            if usd is not None:
                quotes.append(PriceQuote(item.product_ref, "ppt", "us", usd, "USD",
                                         item.product_type, {"raw_id": item.ppt_id}, now))
            if eur is not None:
                quotes.append(PriceQuote(item.product_ref, "ppt", "eu", eur, "EUR",
                                         item.product_type, {"raw_id": item.ppt_id}, now))
        return quotes

    def list_releases(self) -> list[SetRelease]:
        status, data = self._get(f"{PPT_BASE}/sets", headers=self._headers(), params=None)
        if status >= 400 or not data:
            return []
        rows = data.get("data") if isinstance(data, dict) else data
        out: list[SetRelease] = []
        for s in rows or []:
            if not isinstance(s, dict):
                continue
            sid = str(_dig(s, "id", "code", "setId") or "")
            name = _dig(s, "name", "setName")
            rd = _dig(s, "releaseDate", "release_date")
            if not (sid and name):
                continue
            out.append(SetRelease(sid, str(name), _parse_date(rd)))
        return out


def _parse_date(value) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
