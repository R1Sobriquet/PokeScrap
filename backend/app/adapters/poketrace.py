"""Adapter PokeTrace (``PriceProvider``) — mode Free/US.

Le client HTTP applique :
  * un **throttle de burst** (intervalle minimal entre requêtes, dérivé de
    ``poketrace_min_interval_ms``) ;
  * un **garde-quota journalier** (``poketrace_daily_limit``, reset à minuit UTC) ;
  * un **backoff exponentiel** sur ``429``.

Le cache anti-gaspillage (TTL sur ``price_snapshots``) est géré côté ingestion,
au plus près de la base.

**Structure de réponse confirmée (pré-vol Jalon 3, cf. docs/jalon3_preflight.md).**
``GET /cards/{id}`` renvoie un objet ``prices`` **imbriqué par marketplace puis
par tier** — et non un dict plat de tiers ::

    "prices": {
      "tcgplayer": { "NEAR_MINT": { "avg": ..., "avg7d": ..., "saleCount": ... } },
      "ebay":      { "NEAR_MINT": { ... }, "PSA_10": { ... } }
    }

Cartes US → marketplaces ``tcgplayer`` + ``ebay`` ; cartes EU → ``cardmarket``.
Les champs d'un point de prix (``avg/low/high/saleCount/approxSaleCount/avg1d/
avg7d/avg30d``) sont confirmés conformes. ``iter_price_points`` aplatit cette
structure pour l'ingestion.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from collections.abc import Iterator
from typing import Callable

import httpx

from app.adapters.ports import PriceProvider
from app.config import get_setting, get_settings

logger = logging.getLogger("adapters.poketrace")


class QuotaExceeded(RuntimeError):
    """Levée quand le budget de requêtes du jour est épuisé."""


#: Clés de tableau de résultats possibles selon l'enveloppe de la réponse.
_LIST_KEYS = ("data", "cards", "results", "items", "history")
#: Clés d'objet (détail) possibles.
_OBJ_KEYS = ("data", "card", "result")


def _result_list(payload) -> list[dict]:
    """Extrait le tableau de résultats, quelle que soit l'enveloppe.

    La réponse réelle de PokeTrace enveloppe les résultats sous ``data`` (avec un
    objet ``pagination`` à côté) ; on tolère aussi une liste nue ou d'autres clés.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in _LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _result_obj(payload) -> dict:
    """Extrait l'objet de détail, en dépliant une éventuelle enveloppe ``data``."""
    if isinstance(payload, dict):
        for key in _OBJ_KEYS:
            value = payload.get(key)
            if isinstance(value, dict):
                return value
        return payload
    return {}


def iter_price_points(card: dict) -> Iterator[tuple[str, str, dict]]:
    """Aplatit ``card['prices']`` en triplets ``(marketplace, tier, point)``.

    Tolère l'absence de ``prices`` et ignore les valeurs mal formées (un
    marketplace ou un point qui ne serait pas un dict).
    """
    prices = card.get("prices") or {}
    if not isinstance(prices, dict):
        return
    for marketplace, tiers in prices.items():
        if not isinstance(tiers, dict):
            continue
        for tier, point in tiers.items():
            if isinstance(point, dict):
                yield marketplace, tier, point


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class PokeTraceClient:
    """Client HTTP bas-niveau, mode-agnostique, avec garde-quota et throttle."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        daily_limit: int,
        min_interval_ms: int,
        http_client: httpx.Client | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], dt.datetime] = _utcnow,
        max_retries: int = 4,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._daily_limit = daily_limit
        self._interval = max(min_interval_ms, 0) / 1000.0
        self._http = http_client or httpx.Client(timeout=20.0)
        self._monotonic = monotonic
        self._sleep = sleep
        self._now = now
        self._max_retries = max_retries
        self._last_request: float | None = None
        self._count = 0
        self._day = now().date()

    # -- garde-quota -------------------------------------------------------
    @property
    def requests_today(self) -> int:
        self._reset_if_new_day()
        return self._count

    def _reset_if_new_day(self) -> None:
        today = self._now().date()
        if today != self._day:
            self._day = today
            self._count = 0

    def _check_quota(self) -> None:
        self._reset_if_new_day()
        if self._count >= self._daily_limit:
            raise QuotaExceeded(
                f"Quota PokeTrace atteint ({self._count}/{self._daily_limit} req/jour)"
            )

    # -- throttle de burst -------------------------------------------------
    def _throttle(self) -> None:
        if self._last_request is not None and self._interval > 0:
            elapsed = self._monotonic() - self._last_request
            wait = self._interval - elapsed
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._monotonic()

    # -- requête -----------------------------------------------------------
    def get(self, path: str, params: dict | None = None) -> dict | list:
        self._check_quota()
        url = f"{self._base}{path}"
        backoff = 1.0
        for _ in range(self._max_retries):
            self._throttle()
            self._count += 1
            resp = self._http.get(url, params=params, headers={"X-API-Key": self._key})
            if resp.status_code == 429:
                logger.warning("429 PokeTrace — backoff %.1fs (%s)", backoff, path)
                self._sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        raise QuotaExceeded(f"429 répétés sur {path}")


class PokeTracePriceProvider(PriceProvider):
    """Implémentation ``PriceProvider`` adossée à ``PokeTraceClient``."""

    def __init__(self, client: PokeTraceClient | None = None) -> None:
        if client is None:
            settings = get_settings()
            client = PokeTraceClient(
                settings.poketrace_base_url,
                settings.poketrace_api_key,
                daily_limit=int(get_setting("poketrace_daily_limit", default=250)),
                min_interval_ms=int(get_setting("poketrace_min_interval_ms", default=2000)),
            )
        self._client = client

    @property
    def client(self) -> PokeTraceClient:
        return self._client

    def search_cards(self, query: str, *, market: str, limit: int = 20) -> list[dict]:
        # Normalisation de la requête (espaces superflus, casse) par sécurité ;
        # la recherche serveur est insensible à la casse.
        q = " ".join(str(query).split()).lower()
        data = self._client.get(
            "/cards", params={"search": q, "market": market, "limit": limit}
        )
        return _result_list(data)

    def search_page(self, query: str, *, market: str, limit: int = 50, cursor: str | None = None) -> dict:
        """Une page de recherche : ``{items, next_cursor}`` (pagination par cursor).

        L'API renvoie ``{data:[...], pagination:{hasMore, nextCursor, count}}``.
        ``next_cursor`` vaut ``None`` quand il n'y a plus de page.
        """
        q = " ".join(str(query).split()).lower()
        params = {"search": q, "market": market, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        data = self._client.get("/cards", params=params)
        items = _result_list(data)
        next_cursor = None
        if isinstance(data, dict):
            pag = data.get("pagination") or {}
            if isinstance(pag, dict) and pag.get("hasMore"):
                next_cursor = pag.get("nextCursor")
        return {"items": items, "next_cursor": next_cursor}

    def get_card(self, card_id: str, *, market: str) -> dict:
        data = self._client.get(f"/cards/{card_id}", params={"market": market})
        return _result_obj(data)

    def get_price_history(self, card_id: str, tier: str, *, market: str) -> list[dict]:
        data = self._client.get(
            f"/cards/{card_id}/prices/{tier}/history", params={"market": market}
        )
        return _result_list(data)
