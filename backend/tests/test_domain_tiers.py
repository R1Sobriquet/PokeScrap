"""Tests domaine : paliers & garde-fou cash (fonctions pures, sans DB)."""

from __future__ import annotations

from app.domain.tiers import (
    OBJECTIVE_REACHED,
    PRE_TIER,
    can_buy,
    cash_min_pct,
    evaluate_tier_transition,
    resolve_current_tier,
)
from app.domain.types import PortfolioState, TierBand

TIERS = [
    TierBand(1, 150, 300, 10),
    TierBand(2, 300, 1000, 10),
    TierBand(3, 1000, 2500, 5),
    TierBand(4, 2500, 5000, 5),
]


def test_resolve_pre_tier():
    assert resolve_current_tier(100, TIERS) == PRE_TIER


def test_resolve_objective_reached():
    assert resolve_current_tier(5000, TIERS) == OBJECTIVE_REACHED
    assert resolve_current_tier(6000, TIERS) == OBJECTIVE_REACHED


def test_resolve_bounds_inclusive_min_exclusive_max():
    assert resolve_current_tier(150, TIERS).tier_number == 1
    assert resolve_current_tier(299.99, TIERS).tier_number == 1
    assert resolve_current_tier(300, TIERS).tier_number == 2
    assert resolve_current_tier(1500, TIERS).tier_number == 3
    assert resolve_current_tier(2500, TIERS).tier_number == 4


def test_cash_min_pct_below_150():
    assert cash_min_pct(120, None, cash_min_below_150_pct=15) == 15


def test_cash_min_pct_uses_tier():
    assert cash_min_pct(500, TIERS[1], cash_min_below_150_pct=15) == 10


def test_can_buy_allow():
    state = PortfolioState(cash_active=200, capital_invested=0)  # op = 200
    d = can_buy(150, state, cash_min_pct=10)  # floor = 20 ; projected = 50
    assert d.allowed


def test_can_buy_block_cash_min():
    state = PortfolioState(cash_active=200, capital_invested=0)
    d = can_buy(190, state, cash_min_pct=10)  # floor = 20 ; projected = 10
    assert not d.allowed
    assert d.reason == "cash_min"
    assert d.detail["missing"] == 10.0


def test_can_buy_uses_operational_capital():
    # capital investi gonfle le plancher même si le cash actif est identique.
    state = PortfolioState(cash_active=200, capital_invested=800)  # op = 1000
    d = can_buy(150, state, cash_min_pct=10)  # floor = 100 ; projected = 50 < 100
    assert not d.allowed


def test_tier_transition_promotion_requires_confirm():
    t = evaluate_tier_transition(1, [1500, 1500, 1500], TIERS, sustain_snapshots=3, hysteresis_pct=10)
    assert t is not None
    assert t.direction == "up"
    assert t.target_tier == 3
    assert t.requires_confirm and not t.auto


def test_tier_transition_demotion_auto_with_hysteresis():
    # tier 2 (min 300) ; floor = 300*0.9 = 270 ; série soutenue sous 270.
    t = evaluate_tier_transition(2, [250, 240, 230], TIERS, sustain_snapshots=3, hysteresis_pct=10)
    assert t is not None
    assert t.direction == "down"
    assert t.auto and not t.requires_confirm


def test_tier_transition_none_when_insufficient_history():
    assert evaluate_tier_transition(1, [1500, 1500], TIERS, sustain_snapshots=3, hysteresis_pct=10) is None


def test_tier_transition_demotion_not_triggered_within_hysteresis():
    # 290 > 270 (floor) → pas de rétrogradation malgré < capital_min.
    assert evaluate_tier_transition(2, [290, 290, 290], TIERS, sustain_snapshots=3, hysteresis_pct=10) is None
