#!/usr/bin/env python3
"""Smoke-test réel de l'adapter PokeTrace (pré-vol Jalon 3).

But : vérifier, contre l'API **réelle**, que l'adapter parse correctement la
réponse et que le mapping vers ``price_snapshots`` produit des lignes valides.

  * Si ``POKETRACE_API_KEY`` est présente (.env) : appelle
    ``GET /cards?search=charizard&market=US&limit=1`` puis ``GET /cards/{id}``,
    aplatit ``prices`` (marketplace → tier), mappe chaque point, et imprime un
    tableau « champ API → colonne DB → valeur » pour inspection humaine.
  * Sinon : skip propre (exit 0), sans bloquer le build.

Usage : ``python scripts/smoke_poketrace.py``
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
except Exception:  # pragma: no cover - dotenv toujours présent en pratique
    pass


def main() -> int:
    api_key = os.getenv("POKETRACE_API_KEY", "").strip()
    if not api_key:
        print("[skip] POKETRACE_API_KEY absente — smoke-test PokeTrace ignoré.")
        return 0

    base_url = os.getenv("POKETRACE_BASE_URL", "https://api.poketrace.com/v1")

    from app.adapters.poketrace import (
        PokeTraceClient,
        PokeTracePriceProvider,
        iter_price_points,
    )
    from app.services.tier_mapping import map_tier

    client = PokeTraceClient(base_url, api_key, daily_limit=250, min_interval_ms=2000)
    provider = PokeTracePriceProvider(client=client)

    print(f"[1/3] GET {base_url}/cards?search=charizard&market=US&limit=1")
    hits = provider.search_cards("charizard", market="US", limit=1)
    assert hits, "Recherche vide : structure /cards inattendue."
    card_id = hits[0].get("id")
    assert card_id, f"Pas de champ 'id' dans le résultat de recherche : {hits[0]!r}"
    print(f"      → id={card_id}  refs={hits[0].get('refs')}")

    print(f"[2/3] GET {base_url}/cards/{card_id}")
    card = provider.get_card(card_id, market="US")
    points = list(iter_price_points(card))
    assert points, "Objet 'prices' vide ou structure inattendue (marketplace→tier)."

    print("[3/3] Mapping tier → price_snapshots")
    header = f"{'marketplace':<12} {'tier':<16} {'grade_company':<13} {'grade':<6} {'cond':<5} {'price_avg':>10} {'avg_7d':>8} {'sales':>6}"
    print(header)
    print("-" * len(header))

    mapped = 0
    for marketplace, tier, p in points:
        m = map_tier(tier)
        if m is None:
            print(f"{marketplace:<12} {tier:<16} (tier non reconnu — ignoré)")
            continue
        # (b) types corrects
        for field in ("avg", "low", "high", "avg1d", "avg7d", "avg30d"):
            assert p.get(field) is None or isinstance(p[field], (int, float)), (
                f"{marketplace}/{tier}: champ {field} de type inattendu {type(p.get(field))}"
            )
        assert p.get("saleCount") is None or isinstance(p["saleCount"], int)
        assert isinstance(p.get("approxSaleCount", False), bool)
        mapped += 1
        print(
            f"{marketplace:<12} {tier:<16} {m.grade_company:<13} "
            f"{(m.grade or '-'):<6} {(m.condition_code or '-'):<5} "
            f"{str(p.get('avg')):>10} {str(p.get('avg7d')):>8} {str(p.get('saleCount')):>6}"
        )

    assert mapped > 0, "Aucun tier mappable : mapping/structure à revoir."
    print(f"\n[OK] {mapped} point(s) de prix mappé(s) vers price_snapshots.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
