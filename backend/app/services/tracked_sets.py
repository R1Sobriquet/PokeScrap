"""Auto-watchlist par set : peuplement depuis PokeTrace (filtrage CÔTÉ CODE).

L'API ignore ``?productType=sealed`` → on filtre le type/famille **dans le code**.
Le scellé est en Free/US sous ``prices.tcgplayer.UNOPENED`` (pas NEAR_MINT).
On respecte le quota : pagination bornée, intervalle de job long, logs des requêtes.
N'écrase jamais une entrée watchlist ``source='manual'``.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.poketrace import PokeTracePriceProvider
from app.config import get_setting
from app.models import TrackedSet, Watchlist
from app.services.catalog_seed import _scalar, upsert_product

logger = logging.getLogger("services.tracked_sets")

# Sets par défaut (seed initial). min_value pour éviter les communes.
_DEFAULT_SETS = [
    ("prismatic-evolutions", "Prismatic Evolutions"),
    ("151", "Pokémon 151"),
]


def ensure_default_tracked_sets(db: Session) -> int:
    if db.scalar(select(func.count()).select_from(TrackedSet)):
        return 0
    for slug, name in _DEFAULT_SETS:
        db.add(TrackedSet(set_slug=slug, name=name, is_active=1, min_value_eur=5,
                          include_single=1, include_sealed=1))
    db.commit()
    logger.info("Sets suivis par défaut amorcés : %s.", len(_DEFAULT_SETS))
    return len(_DEFAULT_SETS)


# ---------------------------------------------------------------- pur (testable)
def card_product_type(card: dict) -> str | None:
    """Type normalisé : 'single' | 'sealed' (déduit de productType/Family)."""
    ptype = (_scalar(card.get("productType")) or "").lower()
    if ptype in ("single", "sealed"):
        return ptype
    family = (_scalar(card.get("productFamily")) or "").lower()
    if family == "card":
        return "single"
    if family in ("booster_box", "booster_pack", "booster_bundle", "elite_trainer_box",
                  "booster_display", "bundle", "collection_box"):
        return "sealed"
    return None


def card_passes_filters(card: dict, *, include_single: bool, include_sealed: bool,
                        included_families: list | None) -> bool:
    ptype = card_product_type(card)
    if ptype == "single" and not include_single:
        return False
    if ptype == "sealed" and not include_sealed:
        return False
    if ptype is None:
        return False  # type inconnu → on n'ajoute pas à l'aveugle
    if included_families:
        family = (_scalar(card.get("productFamily")) or "").lower()
        if family not in [f.lower() for f in included_families]:
            return False
    return True


def card_value(card: dict) -> float | None:
    """Valeur marché : UNOPENED (scellé) ou NEAR_MINT (single), nested ou plat."""
    prices = card.get("prices")
    if isinstance(prices, dict):
        for mp in ("tcgplayer", "cardmarket", "ebay"):
            tiers = prices.get(mp)
            if isinstance(tiers, dict):
                for tier in ("UNOPENED", "NEAR_MINT", "NM"):
                    pt = tiers.get(tier)
                    if isinstance(pt, dict) and isinstance(pt.get("avg"), (int, float)):
                        return float(pt["avg"])
    for key in ("marketPrice", "price", "avgPrice", "value"):
        v = card.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _tier_for_value(value: float) -> str:
    if value >= 100:
        return "A"
    if value >= 20:
        return "B"
    return "C"


# ------------------------------------------------------------------- I/O
def _upsert_auto_watchlist(db: Session, product, value: float) -> str:
    """Crée/rafraîchit une entrée auto ; ne touche JAMAIS une entrée manuelle."""
    watch = db.scalar(select(Watchlist).where(Watchlist.product_id == product.id))
    if watch is not None and watch.source == "manual":
        return "skipped_manual"
    if watch is None:
        watch = Watchlist(product_id=product.id, source="auto")
        db.add(watch)
        action = "added"
    else:
        action = "updated"
    watch.source = "auto"
    watch.tier = _tier_for_value(value)
    watch.keywords = (product.name or "").lower()
    watch.is_active = 1
    return action


def sync_tracked_sets(db: Session, *, provider=None, now: dt.datetime | None = None) -> dict:
    """Peuple/rafraîchit la watchlist depuis les sets actifs. Respecte le quota."""
    provider = provider or PokeTracePriceProvider()
    market = str(get_setting("valuation_market", default="US"))
    max_pages = int(float(get_setting("tracked_sets_max_pages", default=5)))
    page_size = int(float(get_setting("tracked_sets_page_size", default=50)))

    stats = {"sets": 0, "added": 0, "updated": 0, "skipped": 0, "skipped_manual": 0, "requests": 0}
    sets = db.scalars(select(TrackedSet).where(TrackedSet.is_active == 1)).all()

    for tracked in sets:
        stats["sets"] += 1
        cursor = None
        for _page in range(max_pages):
            page = provider.search_page(tracked.name, market=market, limit=page_size, cursor=cursor)
            stats["requests"] += 1
            for card in page.get("items", []):
                # Restreint au bon set quand le slug est connu (anti-bruit cross-set).
                slug = _scalar(card.get("set"), "slug") if isinstance(card.get("set"), dict) else _scalar(card.get("setSlug"))
                if tracked.set_slug and slug and slug.lower() != tracked.set_slug.lower():
                    continue
                if not card_passes_filters(
                    card, include_single=bool(tracked.include_single),
                    include_sealed=bool(tracked.include_sealed),
                    included_families=tracked.included_families,
                ):
                    stats["skipped"] += 1
                    continue
                value = card_value(card)
                if value is None or value < float(tracked.min_value_eur):
                    stats["skipped"] += 1
                    continue
                product = upsert_product(db, card, {})
                action = _upsert_auto_watchlist(db, product, value)
                stats[action if action in stats else "skipped"] += 1
            cursor = page.get("next_cursor")
            if not cursor:
                break
        db.commit()

    logger.info("sync-tracked-sets : %s", stats)
    return stats
