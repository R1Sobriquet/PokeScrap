"""Adapter TCGdex — catalogue canonique multilingue + dates de sortie (gratuit).

Sert au matching (noms FR détaillants → produit canonique) et à l'auto-calendrier.
Cadence basse (les sets bougent peu). Sans clé. ``lang`` = 'fr' par défaut.
"""

from __future__ import annotations

import datetime as dt
import logging

from app.marketdata.domain import CatalogProduct, SetRelease
from app.marketdata.http import JsonGet, httpx_json_get
from app.marketdata.ports import MarketDataPort

logger = logging.getLogger("marketdata.tcgdex")

TCGDEX_BASE = "https://api.tcgdex.net/v2"


def _parse_date(value) -> dt.date | None:
    if not value:
        return None
    # TCGdex : 'YYYY-MM-DD'.
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


class TCGdexAdapter(MarketDataPort):
    code = "tcgdex"
    capabilities = frozenset({"catalog", "releases"})

    def __init__(self, *, lang: str = "fr", http: JsonGet | None = None):
        self._lang = lang
        self._get = http or httpx_json_get

    def _sets(self) -> list[dict]:
        status, data = self._get(f"{TCGDEX_BASE}/{self._lang}/sets", headers=None, params=None)
        if status >= 400 or not isinstance(data, list):
            logger.info("TCGdex: sets indisponibles (status %s).", status)
            return []
        return [s for s in data if isinstance(s, dict)]

    def list_releases(self) -> list[SetRelease]:
        out: list[SetRelease] = []
        for s in self._sets():
            sid = str(s.get("id") or "")
            name = s.get("name")
            if not (sid and name):
                continue
            rd = _parse_date(s.get("releaseDate"))
            out.append(SetRelease(sid, str(name), rd))
        return out

    def list_catalog(self) -> list[CatalogProduct]:
        out: list[CatalogProduct] = []
        for s in self._sets():
            sid = str(s.get("id") or "")
            name = s.get("name")
            if not (sid and name):
                continue
            out.append(CatalogProduct(canonical_id=sid, name=str(name),
                                      set_id=sid, set_name=str(name), language=self._lang))
        return out
