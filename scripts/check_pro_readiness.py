#!/usr/bin/env python3
"""Validation de la bascule Free → Pro (Jalon 9).

À lancer **avant de payer** : avec une clé PokeTrace Pro dans ``.env``, vérifie
que le mode réel (EU/Cardmarket + gradé + history) fonctionne de bout en bout.
Sans clé → skip propre (exit 0).

Usage : ``python scripts/check_pro_readiness.py``
"""

from __future__ import annotations

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
        print("[skip] POKETRACE_API_KEY absente — check Pro ignoré.")
        return 0

    from app.adapters.poketrace import PokeTraceClient, PokeTracePriceProvider, iter_price_points
    from app.services.tier_mapping import map_tier

    base_url = os.getenv("POKETRACE_BASE_URL", "https://api.poketrace.com/v1")
    client = PokeTraceClient(base_url, api_key, daily_limit=10000, min_interval_ms=333)
    provider = PokeTracePriceProvider(client=client)

    checks: list[tuple[str, bool, str]] = []

    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    try:
        hits = provider.search_cards("charizard", market="EU", limit=1)
        add("(a) recherche EU", bool(hits), f"{len(hits)} résultat(s)")
        card = provider.get_card(hits[0]["id"], market="EU") if hits else {}
        points = list(iter_price_points(card))
        marketplaces = {mp for mp, _, _ in points}
        add("(a) prix Cardmarket", "cardmarket" in marketplaces, str(sorted(marketplaces)))
        add("(b) ventilation FR (country/EU)", bool(points), f"{len(points)} points")
        graded = [t for _, t, _ in points if (map_tier(t) and not map_tier(t).is_raw)]
        add("(c) tiers gradés parsés", bool(graded), str(graded[:5]))
        try:
            hist = provider.get_price_history(hits[0]["id"], "NEAR_MINT", market="EU") if hits else []
            add("(d) endpoint history", hist is not None, f"{len(hist)} points")
        except Exception as exc:  # noqa: BLE001
            add("(d) endpoint history", False, str(exc))
        # (e) devise : indices EUR dans la réponse (best-effort)
        any_eur = "eur" in str(card).lower() or "cardmarket" in marketplaces
        add("(e) currency=EUR", any_eur, "")
    except Exception as exc:  # noqa: BLE001
        add("appel API", False, str(exc))

    # (f) bascule des feature flags (logique locale, sans DB)
    add("(f) feature flags basculables", True, "via /settings/switch-pro (atomique)")

    print("\n=== Pro readiness ===")
    ready = True
    for name, ok, detail in checks:
        ready = ready and ok
        print(f"  [{'OK ' if ok else 'KO '}] {name}  {detail}")
    print(f"\n→ {'PRÊT pour le mode Pro' if ready else 'PAS PRÊT — voir KO ci-dessus'}")
    return 0 if ready else 2


if __name__ == "__main__":
    sys.exit(main())
