"""Tests domaine : filtres anti-erreurs S4 (purs)."""

from __future__ import annotations

from app.domain.filters import (
    anti_pump_block,
    fomo_block,
    illiquidity_block,
    passes_S4,
)


def test_anti_pump_block():
    assert anti_pump_block(150, 100, pump_rise_pct=40) is True       # +50%
    assert anti_pump_block(110, 100, pump_rise_pct=40) is False      # +10%
    # correction récente → on lève le blocage
    assert anti_pump_block(150, 100, pump_rise_pct=40, had_recent_correction=True) is False


def test_illiquidity_block_basic():
    assert illiquidity_block(3, False, min_sale_count=5, illiquid_approx_multiplier=2) is True
    assert illiquidity_block(6, False, min_sale_count=5, illiquid_approx_multiplier=2) is False


def test_illiquidity_block_approx_multiplier():
    # approx → exigence ×2 = 10
    assert illiquidity_block(6, True, min_sale_count=5, illiquid_approx_multiplier=2) is True
    assert illiquidity_block(12, True, min_sale_count=5, illiquid_approx_multiplier=2) is False


def test_fomo_block_global():
    assert fomo_block(fomo_freeze=True, fomo_scope="global") is True
    assert fomo_block(fomo_freeze=False, fomo_scope="global") is False


def test_fomo_block_scoped():
    assert fomo_block(fomo_freeze=True, fomo_scope="set", in_scope=True) is True
    assert fomo_block(fomo_freeze=True, fomo_scope="set", in_scope=False) is False


def test_fomo_block_trends_proxy():
    assert fomo_block(fomo_freeze=False, trends_enabled=True, trends_spike=True) is True


def test_passes_S4_aggregates_flags():
    res = passes_S4(
        avg_7d=160, avg_30d=155, sale_count=89, approx_sale_count=False,
        pump_rise_pct=40, min_sale_count=5, illiquid_approx_multiplier=2,
        fomo_freeze=False, fomo_scope="global",
    )
    assert res.passes
    assert res.flags == {"anti_pump": False, "illiquid": False, "fomo": False}

    blocked = passes_S4(
        avg_7d=160, avg_30d=155, sale_count=2, approx_sale_count=False,
        pump_rise_pct=40, min_sale_count=5, illiquid_approx_multiplier=2,
        fomo_freeze=False, fomo_scope="global",
    )
    assert not blocked.passes
    assert blocked.flags["illiquid"] is True
