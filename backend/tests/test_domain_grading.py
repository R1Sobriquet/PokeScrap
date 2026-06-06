"""Tests domaine : comparateur de grading + verdict d'authenticité (purs)."""

from __future__ import annotations

import pytest

from app.domain.grading import (
    SLAB_HARD_BLOCK,
    SLAB_WARN,
    grade_probability,
    grading_uplift,
    slab_verdict,
)

FEES = {"ebay": 12.0, "cardmarket": 5.0, "vinted": 0.0}
DEFAULT_PROB = {"10": 0.30, "9": 0.45, "le8": 0.25}


def test_grade_probability_default_when_not_pop_report():
    assert grade_probability({"10": 1}, source="default", default=DEFAULT_PROB) == DEFAULT_PROB


def test_grade_probability_from_pop_report():
    prob = grade_probability({"10": 10, "9": 30, "le8": 60}, source="pop_report", default=DEFAULT_PROB)
    assert prob["10"] == pytest.approx(0.1)
    assert prob["9"] == pytest.approx(0.3)
    assert prob["le8"] == pytest.approx(0.6)


def test_grade_probability_falls_back_when_unresolvable():
    assert grade_probability(None, source="pop_report", default=DEFAULT_PROB) == DEFAULT_PROB
    assert grade_probability({}, source="pop_report", default=DEFAULT_PROB) == DEFAULT_PROB


def test_grading_uplift_weighted_expectation():
    res = grading_uplift(
        price_nm=200, price_psa10=2000, price_psa9=600, probability=DEFAULT_PROB,
        grading_cost=120, fee_rates=FEES, sell_platform="ebay",
        min_uplift_eur=50, min_uplift_pct=50, min_card_value=100,
    )
    # raw=176 ; exp=0.3*1760+0.45*528+0.25*176=809.6 ; uplift=809.6-176-120=513.6
    assert res.raw_net == pytest.approx(176.0)
    assert res.expected_net == pytest.approx(809.6, abs=0.1)
    assert res.uplift == pytest.approx(513.6, abs=0.1)
    assert res.is_recommended is True


def test_grading_uplift_respects_100_floor():
    # raw net = 88 < 100 → jamais recommandé, même avec un gros uplift.
    res = grading_uplift(
        price_nm=100, price_psa10=2000, price_psa9=600, probability=DEFAULT_PROB,
        grading_cost=120, fee_rates=FEES, sell_platform="ebay",
        min_uplift_eur=50, min_uplift_pct=50, min_card_value=100,
    )
    assert res.raw_net == pytest.approx(88.0)
    assert res.is_recommended is False


def test_slab_verdict():
    assert slab_verdict(False) == (SLAB_HARD_BLOCK, "cert_invalid")
    assert slab_verdict(True) == (SLAB_WARN, "cert_valid_inspect")
