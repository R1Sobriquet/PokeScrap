"""Tests domaine : moteur de vente (hiérarchie, idempotence) — purs."""

from __future__ import annotations

from app.domain.selling import (
    FORCED_DERISK,
    NO_ACTION,
    SECURE_CAPITAL,
    STRUCTURED_25_50_25,
    discipline_reminder,
    sell_engine,
    speculation_signal,
)
from app.domain.types import SellPosition

TH = dict(
    parabolic_multiple=4.0,
    double_multiple=2.0,
    explosion_multiple=3.0,
    forced_sell_pct=50.0,
    partial_sell_pct=25.0,
    speculative_reserve_pct=25.0,
)


def test_secure_capital_quantity():
    pos = SellPosition(quantity=10, avg_cost=10.0)
    d = sell_engine(pos, 2.0, False, **TH)
    assert d.action == SECURE_CAPITAL
    assert d.qty_to_sell == 5          # ceil(10 / 2)
    assert d.stages_to_set == ("capital_secured",)
    assert d.severity == "critical"


def test_secure_capital_rounds_up():
    pos = SellPosition(quantity=7, avg_cost=10.0)
    assert sell_engine(pos, 2.0, False, **TH).qty_to_sell == 4  # ceil(7/2)


def test_structured_on_residual_after_secured():
    # capital déjà sécurisé, quantité résiduelle 8, m ≥ explosion.
    pos = SellPosition(quantity=8, avg_cost=10.0, stage_capital_secured=True)
    d = sell_engine(pos, 3.0, False, **TH)
    assert d.action == STRUCTURED_25_50_25
    assert d.qty_to_sell == 2          # 25% de 8
    assert d.speculative_reserve_qty == 2  # 25% réservés
    assert d.stages_to_set == ("structured",)
    assert d.severity == "warning"


def test_slow_climb_x2_before_structured():
    # à m=3 mais capital non sécurisé → c'est le CAPITAL qui prime, pas le structuré.
    pos = SellPosition(quantity=10, avg_cost=10.0)
    assert sell_engine(pos, 3.0, False, **TH).action == SECURE_CAPITAL


def test_spike_forced_short_circuits():
    pos = SellPosition(quantity=10, avg_cost=10.0)
    d = sell_engine(pos, 5.0, False, **TH)  # m ≥ parabolic
    assert d.action == FORCED_DERISK
    # sécurise d'abord (ceil(10/5)=2), puis 50% du résidu (8) = 4 → total 6
    assert d.qty_to_sell == 6
    assert d.stages_to_set == ("capital_secured", "forced")
    assert d.keeps_wick is True
    assert d.severity == "critical"


def test_forced_keeps_a_wick():
    pos = SellPosition(quantity=10, avg_cost=10.0, stage_capital_secured=True)
    d = sell_engine(pos, 5.0, False, **TH)
    # résidu 10, 50% = 5 vendus, 5 gardés → jamais tout liquidé
    assert d.qty_to_sell == 5
    assert d.qty_to_sell < pos.quantity


def test_speculation_signal_forces_even_below_parabolic():
    pos = SellPosition(quantity=10, avg_cost=10.0)
    d = sell_engine(pos, 2.5, True, **TH)  # spec_signal court-circuite
    assert d.action == FORCED_DERISK


def test_idempotence_stages_block_repeat():
    # capital sécurisé + structuré déjà faits → plus rien sauf forcé.
    pos = SellPosition(quantity=5, avg_cost=10.0, stage_capital_secured=True, stage_structured=True)
    assert sell_engine(pos, 3.5, False, **TH).action == NO_ACTION
    # forcé déjà posé → terminal, plus d'action.
    pos2 = SellPosition(quantity=5, avg_cost=10.0, stage_capital_secured=True,
                        stage_structured=True, stage_forced=True)
    assert sell_engine(pos2, 9.0, True, **TH).action == NO_ACTION


def test_no_action_below_double():
    assert sell_engine(SellPosition(10, 10.0), 1.5, False, **TH).action == NO_ACTION


def test_speculation_signal_helper():
    assert speculation_signal(speculation_flag=True, volume_spike_pct=0,
                              speculation_volume_spike_pct=200, m=1, parabolic_multiple=4) is True
    assert speculation_signal(speculation_flag=False, volume_spike_pct=250,
                              speculation_volume_spike_pct=200, m=5, parabolic_multiple=4) is True
    assert speculation_signal(speculation_flag=False, volume_spike_pct=100,
                              speculation_volume_spike_pct=200, m=5, parabolic_multiple=4) is False


def test_discipline_reminder_suppressed_when_stage_active():
    common = dict(mv_unit=15.0, avg_cost=10.0, target_sell_price=None, default_profit_target=1.5)
    assert discipline_reminder(stage_active=False, **common) is True   # 15 ≥ 10×1.5
    assert discipline_reminder(stage_active=True, **common) is False   # supprimé
    assert discipline_reminder(stage_active=False, mv_unit=15.0, avg_cost=10.0,
                               target_sell_price=20.0, default_profit_target=1.5) is False
