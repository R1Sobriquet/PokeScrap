"""Tests domaine : segmentation, routage, packing vrac sans doublon (purs)."""

from __future__ import annotations

from app.domain.liquidation import (
    BULK_THEME,
    INDIVIDUAL,
    build_bulk_lots,
    classify_segmentation,
    route_individual,
)
from app.domain.types import LiquidationCard

BULK_KW = dict(min_theme=5, target=4, min_size=2, max_size=5)


def test_classify_segmentation():
    assert classify_segmentation(None, 100, individual_threshold=5) == BULK_THEME
    assert classify_segmentation(1, 3.0, individual_threshold=5) == BULK_THEME
    assert classify_segmentation(1, 9.0, individual_threshold=5) == INDIVIDUAL
    assert classify_segmentation(1, None, individual_threshold=5) == BULK_THEME


def test_route_individual():
    assert route_individual(True, 10, individual_ebay_threshold=50) == "ebay"     # gradé
    assert route_individual(False, 60, individual_ebay_threshold=50) == "ebay"    # >= 50
    assert route_individual(False, 20, individual_ebay_threshold=50) == "cardmarket"


def _assert_no_duplicates(bins):
    for b in bins:
        assert len(set(b.product_ids)) == len(b.product_ids)


def test_bulk_no_duplicates_balanced():
    cards = [LiquidationCard(1, 3, "A"), LiquidationCard(2, 3, "A"), LiquidationCard(3, 3, "A")]
    bins = build_bulk_lots(cards, 0, **BULK_KW)
    _assert_no_duplicates(bins)
    assert len(bins) == 3                       # n = max(ceil(9/4), 3) = 3
    assert sum(b.size for b in bins) == 9       # tous les exemplaires placés
    assert all(b.size <= BULK_KW["max_size"] for b in bins)


def test_bulk_n_respects_max_copies():
    # product1 a 5 exemplaires → il faut au moins 5 bacs pour éviter les doublons.
    cards = [LiquidationCard(1, 5, "A"), LiquidationCard(2, 1, "A")]
    bins = build_bulk_lots(cards, 0, min_theme=5, target=10, min_size=2, max_size=8)
    _assert_no_duplicates(bins)
    assert len(bins) >= 5                        # n >= max_copies
    assert sum(b.size for b in bins) == 6


def test_small_themes_merged_into_mixte():
    cards = [LiquidationCard(1, 3, "A"), LiquidationCard(2, 3, "B")]  # chacun < min_theme 5
    bins = build_bulk_lots(cards, 0, **BULK_KW)
    assert all("mixte" in b.label.lower() for b in bins)
    _assert_no_duplicates(bins)
    assert sum(b.size for b in bins) == 6


def test_unidentified_generic_bins():
    bins = build_bulk_lots([], 10, **BULK_KW)
    melee = [b for b in bins if "mêlé" in b.label]
    assert len(melee) == 3                       # ceil(10/4)
    assert sum(b.size for b in melee) == 10
    assert all(b.product_ids == () for b in melee)
