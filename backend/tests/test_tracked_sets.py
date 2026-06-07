"""Tests auto-watchlist : filtrage single/sealed, valeur, non-écrasement manuel."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import Product, TrackedSet, Watchlist
from app.services.tracked_sets import (
    card_passes_filters,
    card_product_type,
    card_value,
    sync_tracked_sets,
)

# Formes réelles (market US) : single (NEAR_MINT) + scellé (UNOPENED).
SINGLE = {
    "id": "u-umbreon", "name": "Umbreon ex", "productType": "single", "productFamily": "card",
    "set": {"slug": "prismatic-evolutions", "name": "Prismatic Evolutions"},
    "cardNumber": "161",
    "prices": {"tcgplayer": {"NEAR_MINT": {"avg": 1400}}},
}
SEALED = {
    "id": "u-etb", "name": "Prismatic Evolutions Elite Trainer Box",
    "productType": "sealed", "productFamily": "elite_trainer_box",
    "set": {"slug": "prismatic-evolutions", "name": "Prismatic Evolutions"},
    "prices": {"tcgplayer": {"UNOPENED": {"avg": 75}}},
}
COMMON = {
    "id": "u-common", "name": "Bidoof", "productType": "single", "productFamily": "card",
    "set": {"slug": "prismatic-evolutions", "name": "Prismatic Evolutions"},
    "prices": {"tcgplayer": {"NEAR_MINT": {"avg": 0.10}}},
}


def test_product_type_detection():
    assert card_product_type(SINGLE) == "single"
    assert card_product_type(SEALED) == "sealed"
    # type inféré depuis la famille si productType manquant
    assert card_product_type({"productFamily": "booster_box"}) == "sealed"
    assert card_product_type({"productFamily": "card"}) == "single"


def test_filter_single_vs_sealed_code_side():
    # sealed exclu si include_sealed=False (le filtrage est côté code, pas via l'API)
    assert card_passes_filters(SINGLE, include_single=True, include_sealed=False, included_families=None)
    assert not card_passes_filters(SEALED, include_single=True, include_sealed=False, included_families=None)
    # single exclu si include_single=False
    assert not card_passes_filters(SINGLE, include_single=False, include_sealed=True, included_families=None)
    assert card_passes_filters(SEALED, include_single=False, include_sealed=True, included_families=None)
    # filtre par famille
    assert not card_passes_filters(SEALED, include_single=True, include_sealed=True,
                                   included_families=["booster_box"])


def test_card_value_handles_unopened_and_near_mint():
    assert card_value(SINGLE) == 1400.0     # NEAR_MINT pour un single
    assert card_value(SEALED) == 75.0       # UNOPENED pour le scellé
    assert card_value({"prices": {}}) is None


class _FakePagedProvider:
    """Provider mock : une seule page, pas de réseau."""

    def __init__(self, items):
        self._items = items
        self.calls = 0

    def search_page(self, query, *, market, limit=50, cursor=None):
        self.calls += 1
        return {"items": list(self._items), "next_cursor": None}


def test_sync_populates_and_respects_min_value(db_session):
    db = db_session
    db.add(TrackedSet(set_slug="prismatic-evolutions", name="Prismatic Evolutions",
                      is_active=1, min_value_eur=5, include_single=1, include_sealed=1))
    db.commit()

    provider = _FakePagedProvider([SINGLE, SEALED, COMMON])
    stats = sync_tracked_sets(db, provider=provider)

    # Umbreon (1400) + ETB (75) ajoutés ; Bidoof (0,10 < 5€) ignoré.
    assert stats["added"] == 2
    assert stats["skipped"] >= 1
    names = {p.name for p in db.scalars(select(Product)).all()}
    assert "Umbreon ex" in names and "Bidoof" not in names
    autos = db.scalars(select(Watchlist).where(Watchlist.source == "auto")).all()
    assert len(autos) == 2


def test_sync_does_not_overwrite_manual_entry(db_session):
    db = db_session
    db.add(TrackedSet(set_slug="prismatic-evolutions", name="Prismatic Evolutions",
                      is_active=1, min_value_eur=5, include_single=1, include_sealed=1))
    db.commit()
    # Entrée MANUELLE pré-existante sur Umbreon (tier S++, keywords custom).
    p = Product(product_type="single", name="Umbreon ex", set_slug="prismatic-evolutions",
                language="EN", poketrace_id="u-umbreon")
    db.add(p)
    db.commit()
    db.add(Watchlist(product_id=p.id, tier="S++", keywords="moonbreon", source="manual",
                     is_trinity=1, priority_coef=1))
    db.commit()

    sync_tracked_sets(db, provider=_FakePagedProvider([SINGLE]))

    watch = db.scalar(select(Watchlist).where(Watchlist.product_id == p.id))
    assert watch.source == "manual"      # inchangé
    assert watch.tier == "S++"           # non écrasé
    assert watch.keywords == "moonbreon"
    assert watch.is_trinity == 1
    # pas de doublon de watchlist
    assert db.scalar(select(func.count()).select_from(Watchlist)) == 1
