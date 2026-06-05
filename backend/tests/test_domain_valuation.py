"""Tests domaine : valorisation de lot & règle des 50 % (purs)."""

from __future__ import annotations

import pytest

from app.domain.buying import evaluate_buy, opportunity_score
from app.domain.types import DetectedProduct, ListingInput, PriceInfo, ValuationParams
from app.domain.valuation import estimate_lot_resale_net, is_IR_lot, net_value

FEES = {"cardmarket": 5.0, "ebay": 12.0, "vinted": 0.0}


def _params(fx=1.0, ir_share=50.0):
    return ValuationParams(
        min_match_confidence=0.70,
        default_sell_platform="cardmarket",
        bulk_value_per_card=0.05,
        vinted_fee_rate=0.0,
        lot_confidence_haircut=0.85,
        fee_rates=FEES,
        ir_lot_value_share=ir_share,
        fx=fx,
    )


def test_net_value():
    assert net_value(100, "cardmarket", fee_rates=FEES) == pytest.approx(95.0)
    assert net_value(100, "ebay", fee_rates=FEES) == pytest.approx(88.0)


def test_estimate_lot_resale_net_with_fx_and_bulk():
    listing = ListingInput(
        acquisition_cost_total=0,
        estimated_total_cards=5,
        detected_products=(
            DetectedProduct(1, qty=1, confidence=0.95),
            DetectedProduct(2, qty=2, confidence=0.50),  # sous le seuil → ignoré
        ),
    )
    prices = {1: PriceInfo(price=100.0), 2: PriceInfo(price=50.0)}
    # fx 0.92 : 100→92 ; net cardmarket 5% → 87.4 ; bulk 4×0.05 = 0.2 ; ×0.85
    value = estimate_lot_resale_net(listing, prices, _params(fx=0.92))
    assert value == pytest.approx((87.4 + 0.2) * 0.85, rel=1e-4)


def test_estimate_lot_resale_net_eu_no_conversion():
    listing = ListingInput(0, 1, (DetectedProduct(1, 1, 0.95),))
    prices = {1: PriceInfo(price=100.0)}
    value = estimate_lot_resale_net(listing, prices, _params(fx=1.0))
    assert value == pytest.approx(95.0 * 0.85, rel=1e-4)


def test_is_IR_lot_threshold():
    listing = ListingInput(
        0, 2,
        (DetectedProduct(1, 1, 0.95, is_illustration_rare=True),
         DetectedProduct(2, 1, 0.95)),
    )
    prices = {1: PriceInfo(price=100.0), 2: PriceInfo(price=50.0)}
    # IR=95, total=142.5 → 66.7% ≥ 50% → lot IR ; mais < 80%.
    assert is_IR_lot(listing, prices, _params(ir_share=50)) is True
    assert is_IR_lot(listing, prices, _params(ir_share=80)) is False


def test_evaluate_buy_passes_at_or_below_50():
    listing = ListingInput(33.0, 1, (DetectedProduct(1, 1, 0.95),))
    prices = {1: PriceInfo(price=100.0)}
    d = evaluate_buy(listing, prices, _params(fx=1.0),
                     fifty_rule_threshold_pct=50, ir_min_discount_pct=30)
    # resale = 95*0.85 = 80.75 ; ratio = 33/80.75 = 40.9% ≤ 50 → passe
    assert d.passes and not d.hard_block
    assert d.ratio_pct == pytest.approx(40.87, abs=0.1)


def test_evaluate_buy_blocks_above_50():
    listing = ListingInput(50.0, 1, (DetectedProduct(1, 1, 0.95),))
    prices = {1: PriceInfo(price=100.0)}
    d = evaluate_buy(listing, prices, _params(fx=1.0),
                     fifty_rule_threshold_pct=50, ir_min_discount_pct=30)
    assert not d.passes and not d.hard_block
    assert d.reason == "ratio_above_threshold"


def test_evaluate_buy_ir_hard_block_above_70():
    listing = ListingInput(70.0, 1, (DetectedProduct(1, 1, 0.95, is_illustration_rare=True),))
    prices = {1: PriceInfo(price=100.0)}
    d = evaluate_buy(listing, prices, _params(fx=1.0, ir_share=50),
                     fifty_rule_threshold_pct=50, ir_min_discount_pct=30)
    # resale 80.75 ; ratio = 86.7% > 70 (= 100 − 30) ET lot IR → hard block
    assert d.hard_block and not d.passes
    assert d.reason == "ir_absolute_floor"


def test_opportunity_score_orders_listings():
    common = dict(threshold_pct=50, w_margin=0.5, w_liquidity=0.3, w_tier=0.2, liquidity_midpoint=5)
    good = opportunity_score(ratio_pct=30, priority_coef=1.5, sale_count=100, tier="S++", **common)
    weak = opportunity_score(ratio_pct=45, priority_coef=1.0, sale_count=5, tier="C", **common)
    assert good > weak
