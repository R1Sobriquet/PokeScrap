"""Registre des sources marché : construit les adapters activés via ``settings``.

Sources désactivées par défaut ; une source sans clé/flag n'est pas instanciée
(no-op silencieux). Ajouter une 4ᵉ source = un import + une entrée ici.
"""

from __future__ import annotations

import os

from app.config import get_setting
from app.marketdata.ports import MarketDataPort
from app.marketdata.sources.ebay import EbayBrowseAdapter
from app.marketdata.sources.ppt import PokemonPriceTrackerAdapter
from app.marketdata.sources.tcgdex import TCGdexAdapter


def build_sources() -> dict[str, MarketDataPort]:
    """Adapters actifs (flag source ON). Clés/secrets lus en ``settings``/env."""
    sources: dict[str, MarketDataPort] = {}

    if bool(get_setting("marketdata_ppt_enabled", default=False)):
        key = str(get_setting("ppt_api_key", default="") or os.getenv("PPT_API_KEY", ""))
        if key:
            sources["ppt"] = PokemonPriceTrackerAdapter(api_key=key)

    if bool(get_setting("marketdata_tcgdex_enabled", default=True)):
        sources["tcgdex"] = TCGdexAdapter()

    if bool(get_setting("marketdata_ebay_enabled", default=False)):
        cid = str(get_setting("ebay_client_id", default="") or os.getenv("EBAY_CLIENT_ID", ""))
        secret = str(get_setting("ebay_client_secret", default="") or os.getenv("EBAY_CLIENT_SECRET", ""))
        if cid and secret:
            sources["ebay"] = EbayBrowseAdapter(client_id=cid, client_secret=secret)

    return sources
