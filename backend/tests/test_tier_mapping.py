"""Tests du mapping tier PokeTrace → colonnes price_snapshots."""

from __future__ import annotations

import pytest

from app.services.tier_mapping import map_tier


@pytest.mark.parametrize(
    "tier,company,grade,condition",
    [
        ("NEAR_MINT", "RAW", None, "NM"),
        ("LIGHTLY_PLAYED", "RAW", None, "LP"),
        ("MODERATELY_PLAYED", "RAW", None, "MP"),
        ("HEAVILY_PLAYED", "RAW", None, "HP"),
        ("DAMAGED", "RAW", None, "DMG"),
    ],
)
def test_raw_tiers(tier, company, grade, condition):
    m = map_tier(tier)
    assert m == (company, grade, condition)
    assert m.is_raw


@pytest.mark.parametrize(
    "tier,company,grade",
    [
        ("PSA_10", "PSA", "10"),
        ("PSA_9", "PSA", "9"),
        ("BGS_9.5", "BGS", "9.5"),
        ("CGC_10", "CGC", "10"),
        ("SGC_10", "SGC", "10"),
    ],
)
def test_graded_tiers(tier, company, grade):
    m = map_tier(tier)
    assert m == (company, grade, None)
    assert not m.is_raw


def test_unknown_tier_returns_none():
    assert map_tier("WEIRD_TIER") is None
    assert map_tier("FOO_10") is None  # société inconnue
