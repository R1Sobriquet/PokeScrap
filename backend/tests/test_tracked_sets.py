"""Tests auto-watchlist : matching set robuste, filtrage single/sealed, comptage."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import Product, TrackedSet, Watchlist
from app.services.tracked_sets import (
    card_passes_filters,
    card_product_type,
    card_value,
    set_slug_matches,
    sync_tracked_sets,
)

# Formes RÉELLES (market US) : l'API préfixe le slug de série (sv-), le scellé a
# cardNumber/rarity null et son prix sous UNOPENED.
SINGLE = {
    "id": "u-umbreon", "name": "Umbreon ex", "productType": "single", "productFamily": "card",
    "set": {"slug": "sv-prismatic-evolutions", "name": "Prismatic Evolutions"},
    "cardNumber": "161", "rarity": "Special Illustration Rare",
    "prices": {"tcgplayer": {"NEAR_MINT": {"avg": 1400}}},
}
SEALED = {
    "id": "u-etb", "name": "Prismatic Evolutions Elite Trainer Box",
    "productType": "sealed", "productFamily": "box_collection",
    "set": {"slug": "sv-prismatic-evolutions", "name": "Prismatic Evolutions"},
    "cardNumber": None, "rarity": None,
    "prices": {"tcgplayer": {"UNOPENED": {"avg": 75}}},
}
COMMON = {
    "id": "u-common", "name": "Bidoof", "productType": "single", "productFamily": "card",
    "set": {"slug": "sv-prismatic-evolutions", "name": "Prismatic Evolutions"},
    "prices": {"tcgplayer": {"NEAR_MINT": {"avg": 0.10}}},
}
ACCESSORY = {
    "id": "u-acc", "name": "Sleeves Prismatic", "productType": "accessory",
    "productFamily": "accessory",
    "set": {"slug": "sv-prismatic-evolutions", "name": "Prismatic Evolutions"},
    "prices": {"tcgplayer": {"UNOPENED": {"avg": 12}}},
}


def test_set_slug_matches_handles_series_prefix():
    assert set_slug_matches("sv-prismatic-evolutions", "prismatic-evolutions") is True
    assert set_slug_matches("sv-151", "151") is True
    assert set_slug_matches("prismatic-evolutions", "prismatic-evolutions") is True
    assert set_slug_matches("sv-obsidian-flames", "prismatic-evolutions") is False
    assert set_slug_matches(None, "151") is False
    assert set_slug_matches("sv-151", "") is True  # pas de slug suivi → on n'exclut pas


def test_product_type_detection():
    assert card_product_type(SINGLE) == "single"
    assert card_product_type(SEALED) == "sealed"        # famille box_collection
    assert card_product_type({"productFamily": "booster_pack"}) == "sealed"
    assert card_product_type({"productFamily": "card"}) == "single"
    assert card_product_type(ACCESSORY) is None          # accessoire → exclu


def test_filter_single_vs_sealed_code_side():
    assert card_passes_filters(SINGLE, include_single=True, include_sealed=False, included_families=None)
    assert not card_passes_filters(SEALED, include_single=True, include_sealed=False, included_families=None)
    assert not card_passes_filters(SINGLE, include_single=False, include_sealed=True, included_families=None)
    assert card_passes_filters(SEALED, include_single=False, include_sealed=True, included_families=None)
    assert not card_passes_filters(ACCESSORY, include_single=True, include_sealed=True, included_families=None)
    assert not card_passes_filters(SEALED, include_single=True, include_sealed=True,
                                   included_families=["booster_box"])


def test_card_value_handles_unopened_and_near_mint():
    assert card_value(SINGLE) == 1400.0
    assert card_value(SEALED) == 75.0      # UNOPENED
    assert card_value({"prices": {}}) is None


class _FakePagedProvider:
    def __init__(self, items):
        self._items = items
        self.calls = 0

    def search_page(self, query, *, market, limit=50, cursor=None):
        self.calls += 1
        return {"items": list(self._items), "next_cursor": None}


def test_sync_matches_prefixed_slug_and_counts(db_session):
    db = db_session
    db.add(TrackedSet(set_slug="prismatic-evolutions", name="Prismatic Evolutions",
                      is_active=1, min_value_eur=5, include_single=1, include_sealed=1))
    db.commit()

    provider = _FakePagedProvider([SINGLE, SEALED, COMMON, ACCESSORY])
    stats = sync_tracked_sets(db, provider=provider)

    # Le mismatch sv- est résolu : Umbreon (single) + ETB (sealed) retenus.
    assert stats["received"] == 4
    assert stats["added"] == 2
    assert stats["rejected"]["mismatch_set"] == 0       # plus de rejet silencieux
    assert stats["rejected"]["sous_min_value"] == 1     # Bidoof 0,10€
    assert stats["rejected"]["type_non_suivi"] == 1     # accessoire
    # le scellé est bien typé 'sealed' dans products
    etb = db.scalar(select(Product).where(Product.poketrace_id == "u-etb"))
    assert etb.product_type == "sealed"
    assert etb.card_number is None
    autos = db.scalars(select(Watchlist).where(Watchlist.source == "auto")).all()
    assert len(autos) == 2


def test_sync_rejects_wrong_set_with_reason(db_session):
    db = db_session
    db.add(TrackedSet(set_slug="151", name="Pokémon 151", is_active=1, min_value_eur=5,
                      include_single=1, include_sealed=1))
    db.commit()
    # SINGLE appartient à prismatic, pas à 151 → mismatch compté (pas silencieux).
    stats = sync_tracked_sets(db, provider=_FakePagedProvider([SINGLE]))
    assert stats["received"] == 1
    assert stats["added"] == 0
    assert stats["rejected"]["mismatch_set"] == 1


def test_sync_does_not_overwrite_manual_entry(db_session):
    db = db_session
    db.add(TrackedSet(set_slug="prismatic-evolutions", name="Prismatic Evolutions",
                      is_active=1, min_value_eur=5, include_single=1, include_sealed=1))
    db.commit()
    p = Product(product_type="single", name="Umbreon ex", set_slug="prismatic-evolutions",
                language="EN", poketrace_id="u-umbreon")
    db.add(p)
    db.commit()
    db.add(Watchlist(product_id=p.id, tier="S++", keywords="moonbreon", source="manual",
                     is_trinity=1, priority_coef=1))
    db.commit()

    sync_tracked_sets(db, provider=_FakePagedProvider([SINGLE]))

    watch = db.scalar(select(Watchlist).where(Watchlist.product_id == p.id))
    assert watch.source == "manual" and watch.tier == "S++" and watch.keywords == "moonbreon"
    assert db.scalar(select(func.count()).select_from(Watchlist)) == 1
