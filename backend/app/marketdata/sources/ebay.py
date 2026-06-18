"""Adapter eBay Browse (officiel, OAuth client-credentials) — annonces FR actives.

Signal SECONDAIRE : profondeur de stock (nb d'annonces) + prix. **Rétention CGU
eBay** : on ne stocke que des **agrégats dérivés** par produit/jour (nb, min,
médiane), jamais un dump des annonces. Marketplace ``EBAY_FR``.
"""

from __future__ import annotations

import base64
import datetime as dt
import logging
import statistics
from collections.abc import Callable, Iterable
from decimal import Decimal, InvalidOperation

import httpx

from app.marketdata.domain import PriceQuote, WatchItem
from app.marketdata.http import JsonGet, httpx_json_get
from app.marketdata.ports import MarketDataPort

logger = logging.getLogger("marketdata.ebay")

EBAY_OAUTH = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_BROWSE = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_SCOPE = "https://api.ebay.com/oauth/api_scope"

#: ``token_getter(client_id, client_secret) -> str|None`` — injectable en test.
TokenGetter = Callable[[str, str], "str | None"]


def _dec(v) -> Decimal | None:
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _default_token(client_id: str, client_secret: str) -> str | None:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = httpx.post(
        EBAY_OAUTH,
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "scope": EBAY_SCOPE},
        timeout=20.0,
    )
    if resp.status_code >= 400:
        logger.warning("eBay OAuth échec (status %s).", resp.status_code)
        return None
    return resp.json().get("access_token")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class EbayBrowseAdapter(MarketDataPort):
    code = "ebay"
    capabilities = frozenset({"quotes"})

    def __init__(self, *, client_id: str, client_secret: str,
                 http: JsonGet | None = None, token_getter: TokenGetter | None = None,
                 limit: int = 30):
        self._id = client_id
        self._secret = client_secret
        self._get = http or httpx_json_get
        self._token_getter = token_getter or _default_token
        self._limit = limit
        self._token: str | None = None

    def _ensure_token(self) -> str | None:
        if self._token is None:
            self._token = self._token_getter(self._id, self._secret)
        return self._token

    def fetch_quotes(self, items: Iterable[WatchItem]) -> list[PriceQuote]:
        token = self._ensure_token()
        if not token:
            return []
        headers = {"Authorization": f"Bearer {token}",
                   "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR", "Accept": "application/json"}
        now = _utcnow()
        quotes: list[PriceQuote] = []
        for item in items:
            params = {"q": item.name, "limit": str(self._limit),
                      "filter": "buyingOptions:{FIXED_PRICE},conditions:{NEW}"}
            status, data = self._get(EBAY_BROWSE, headers=headers, params=params)
            if status >= 400 or not isinstance(data, dict):
                continue
            prices = []
            for it in data.get("itemSummaries") or []:
                p = _dec((it.get("price") or {}).get("value"))
                if p is not None and p > 0:
                    prices.append(float(p))
            if not prices:
                continue
            # Agrégats dérivés UNIQUEMENT (conformité rétention eBay).
            agg = {"count": len(prices), "min": round(min(prices), 2),
                   "median": round(statistics.median(prices), 2)}
            quotes.append(PriceQuote(item.product_ref, "ebay", "eu",
                                     Decimal(str(agg["median"])), "EUR",
                                     item.product_type, agg, now))
        return quotes
