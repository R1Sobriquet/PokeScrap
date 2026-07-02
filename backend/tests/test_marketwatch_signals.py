"""Tests des signaux : fonctions pures + intégration run_score/select_targets."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app.domain import marketwatch_signals as sig
from app.models import CardPriceSnapshot, DailySignal, TcgdexCard
from app.services.marketwatch_score import run_score, select_targets

TODAY = dt.date(2026, 6, 1)


# --- Fonctions pures --------------------------------------------------------
def test_near_low_bounds():
    assert sig.near_low(10, 10) == 1.0          # au plancher
    assert sig.near_low(20, 10) == 0.0          # 2× le plancher → 0
    assert abs(sig.near_low(11, 10) - 0.9) < 1e-9
    assert sig.near_low(None, 10) is None


def test_drawdown_sma():
    assert abs(sig.drawdown_sma(8, 10) - 0.2) < 1e-9
    assert sig.drawdown_sma(12, 10) == 0.0      # au-dessus de la moyenne → 0


def test_bottoming_requires_short_above_long_and_positive_momentum():
    assert sig.bottoming(12, 10, 0.10) == 0.5   # 10% en 7j → 0.5
    assert sig.bottoming(9, 10, 0.10) == 0.0    # SMA courte < longue → pas de retournement
    assert sig.bottoming(12, 10, -0.05) == 0.0  # momentum négatif → 0


def test_cross_lang_relative_to_history():
    assert sig.cross_lang({"EN": 10, "JP": 15}, 0.25) == 1.0
    assert sig.cross_lang({"EN": 10}, 0.25) == 0.0   # une seule langue → 0


def test_liquidity_saturates():
    assert sig.liquidity(0, 0) == 0.0
    assert sig.liquidity(5, 3) == 0.5           # 8/(8+8)


def test_tier_and_catalyst_multipliers():
    assert sig.tier_multiplier("S") == 1.30
    assert sig.tier_multiplier(None) == 1.00
    assert sig.catalyst_bonus(0) == 1.20
    assert sig.catalyst_bonus(90) == 1.00
    assert sig.catalyst_bonus(None) == 1.00
    assert sig.catalyst_bonus(120) == 1.00      # hors horizon


def test_budget_band_thresholds():
    assert sig.budget_band(9.99) == "lt10"
    assert sig.budget_band(15) == "10_20"
    assert sig.budget_band(40) == "lte50"
    assert sig.budget_band(80) is None


def test_composite_applies_tier_and_catalyst():
    base = sig.composite_score(near_low_v=1.0, drawdown_v=0.0, bottoming_v=0.0,
                               cross_lang_v=0.0, liquidity_v=0.0)
    assert abs(base - 0.35) < 1e-9
    boosted = sig.composite_score(near_low_v=1.0, drawdown_v=0.0, bottoming_v=0.0,
                                  cross_lang_v=0.0, liquidity_v=0.0,
                                  tier_mult=1.30, catalyst=1.20)
    assert abs(boosted - 0.35 * 1.30 * 1.20) < 1e-9


# --- Intégration : série → daily_signals -----------------------------------
def _seed_series(db):
    db.add(TcgdexCard(card_id="sv03.5-161", set_id="sv03.5", set_name="151",
                      number="161", pokemon="Charizard", name_en="Charizard ex"))
    # Plancher à 10 € pendant longtemps, puis remontée à 13 € sur 3 jours.
    for i in range(40, 3, -1):
        db.add(CardPriceSnapshot(card_id="sv03.5-161", source="cardmarket", language="EN",
                                 condition_grade="NM_RAW", price_eur=Decimal("10.00"),
                                 captured_at=TODAY - dt.timedelta(days=i)))
    for i in range(3, -1, -1):
        db.add(CardPriceSnapshot(card_id="sv03.5-161", source="cardmarket", language="EN",
                                 condition_grade="NM_RAW", price_eur=Decimal("13.00"),
                                 captured_at=TODAY - dt.timedelta(days=i)))
    db.commit()


def test_run_score_writes_signal(db_session):
    _seed_series(db_session)
    res = run_score(db_session, today=TODAY)
    assert res["signals"] == 1

    row = db_session.scalar(select(DailySignal))
    assert row.card_id == "sv03.5-161"
    assert row.budget_band == "10_20"           # prix courant 13 €
    assert abs(float(row.near_low) - 0.7) < 1e-6  # 13 vs plancher 10
    assert float(row.bottoming) > 0.0            # sortie de creux détectée
    assert float(row.score) > 0.0


def test_select_targets_applies_liquidity_floor(db_session):
    _seed_series(db_session)
    run_score(db_session, today=TODAY)
    # Liquidité nulle (pas d'eBay) → exclu si plancher > 0.
    assert select_targets(db_session, TODAY, min_liquidity=0.1) == {"lt10": [], "10_20": [], "lte50": []}
    # Sans plancher → la carte ressort dans sa tranche.
    bands = select_targets(db_session, TODAY, min_liquidity=0.0)
    assert [s.card_id for s in bands["10_20"]] == ["sv03.5-161"]
