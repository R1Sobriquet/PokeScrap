"""Tests domaine : comptabilité pure (cascade, 30/70, KPIs)."""

from __future__ import annotations

import pytest

from app.domain import accounting


def test_lock_increment_positive_only():
    assert accounting.lock_increment(100, reinvest_lock_pct=30) == pytest.approx(30)
    assert accounting.lock_increment(-50, reinvest_lock_pct=30) == 0.0
    assert accounting.lock_increment(0, reinvest_lock_pct=30) == 0.0


def test_cash_cascade():
    active = accounting.cash_active(cash_total=295, cash_locked=16.5)
    assert active == pytest.approx(278.5)
    assert accounting.operational_capital(active, capital_invested=80) == pytest.approx(358.5)


def test_realized_profit_net():
    pairs = [(95.0, 40.0), (50.0, 30.0)]  # (net, cost_basis)
    assert accounting.realized_profit_net(pairs, isolated_fees=5.0) == pytest.approx(70.0)


def test_capital_rotation_rate():
    assert accounting.capital_rotation_rate(40, 80) == pytest.approx(0.5)
    assert accounting.capital_rotation_rate(40, 0) is None


def test_tax_provision_informative():
    assert accounting.tax_provision(100, 12.3) == pytest.approx(12.3)


def test_total_portfolio_value():
    assert accounting.total_portfolio_value(295, [30, 50]) == pytest.approx(375)
