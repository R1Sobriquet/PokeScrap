#!/usr/bin/env python3
"""Préflight auto-watchlist (Tâche 0) — vérifie la VRAIE forme de l'API.

Avec la clé du .env, interroge 1 set et observe : pagination (nextCursor/hasMore),
présence de productType/productFamily, et structure de prix du scellé (UNOPENED).
Sans clé → skip propre. NE DEVINE PAS : loggue ce qui est réellement reçu.

Usage : ``python scripts/preflight_tracked_sets.py [set_name]``
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:  # pragma: no cover
    pass


def main() -> int:
    api_key = os.getenv("POKETRACE_API_KEY", "").strip()
    if not api_key:
        print("[skip] POKETRACE_API_KEY absente — préflight ignoré.")
        return 0

    set_name = sys.argv[1] if len(sys.argv) > 1 else "prismatic evolutions"
    base_url = os.getenv("POKETRACE_BASE_URL", "https://api.poketrace.com/v1")

    from app.adapters.poketrace import PokeTraceClient, PokeTracePriceProvider
    from app.services.tracked_sets import card_product_type, card_value

    client = PokeTraceClient(base_url, api_key, daily_limit=250, min_interval_ms=2000)
    provider = PokeTracePriceProvider(client=client)

    print(f"[1/2] GET /cards?search={set_name!r}&market=US (page 1)")
    page = provider.search_page(set_name, market="US", limit=10)
    items = page["items"]
    print(f"      items={len(items)}  next_cursor={page['next_cursor']!r}")

    types = {}
    families = {}
    for c in items:
        types[c.get("productType")] = types.get(c.get("productType"), 0) + 1
        families[c.get("productFamily")] = families.get(c.get("productFamily"), 0) + 1
    print(f"      productType observés : {types}")
    print(f"      productFamily observés : {families}")

    # Inspecte la structure de prix d'un éventuel scellé (UNOPENED).
    sealed = next((c for c in items if card_product_type(c) == "sealed"), None)
    if sealed:
        card = provider.get_card(sealed.get("id"), market="US")
        prices = card.get("prices", {})
        print("[2/2] Structure prix scellé (clés) :")
        print("      " + json.dumps({mp: list(t) for mp, t in prices.items() if isinstance(t, dict)}, ensure_ascii=False))
        print(f"      card_value(scellé) = {card_value(card)}")
    else:
        print("[2/2] Aucun scellé dans cette page — relancer avec un autre set si besoin.")

    print("\n[OK] Préflight terminé — cale le code sur les observations ci-dessus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
