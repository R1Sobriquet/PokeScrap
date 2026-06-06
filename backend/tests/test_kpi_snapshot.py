"""Tests du snapshot KPI quotidien + transitions de palier."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.models import AccountSnapshot, Alert, TierConfig, Transaction
from app.services.kpi_snapshot import run_kpi_snapshot
from app.services.tier_state import get_current_tier_number, set_current_tier
from tests.conftest import insert_setting

NOW = dt.datetime(2026, 6, 5, 12, 0, 0)
TODAY = NOW.date()

TIERS = [
    (1, "Étape 1", 150, 300, 10),
    (2, "Étape 2", 300, 1000, 10),
    (3, "Étape 3", 1000, 2500, 5),
    (4, "Étape 4", 2500, 5000, 5),
]


def _base_settings(db):
    insert_setting(db, "valuation_market", "US", "string")
    insert_setting(db, "fx_usd_eur", "0.92", "decimal")
    insert_setting(db, "reinvest_lock_pct", "30", "decimal")
    insert_setting(db, "lock_only_positive_profit", "true", "bool")
    insert_setting(db, "tax_provision_pct", "12.3", "decimal")
    insert_setting(db, "tier_sustain_snapshots", "3", "int")
    insert_setting(db, "tier_hysteresis_pct", "10", "decimal")
    for num, name, cmin, cmax, cash in TIERS:
        db.add(TierConfig(tier_number=num, name=name, capital_min=cmin, capital_max=cmax, cash_min_pct=cash))
    db.commit()


def _prior_snapshot(db, days_ago: int, op_capital: float):
    db.add(
        AccountSnapshot(
            snapshot_date=TODAY - dt.timedelta(days=days_ago),
            total_portfolio_value=op_capital, capital_invested=0,
            cash_available=op_capital, cash_locked=0, cash_active=op_capital,
            realized_profit_net=0, turnover_cumulative=0,
        )
    )
    db.commit()


def test_snapshot_written_and_promotion_emitted(db_session):
    db = db_session
    _base_settings(db)
    set_current_tier(db, 1)
    db.add(Transaction(tx_type="adjustment", quantity=1, gross_amount=1500, net_amount=1500,
                       currency="EUR", occurred_at=NOW))
    db.commit()
    _prior_snapshot(db, 2, 1500.0)
    _prior_snapshot(db, 1, 1500.0)

    result = run_kpi_snapshot(db, now=NOW)

    snap = db.scalar(select(AccountSnapshot).where(AccountSnapshot.snapshot_date == TODAY))
    assert snap is not None
    assert float(snap.cash_active) == 1500.0
    assert result["transition"]["direction"] == "up"
    palier = db.scalar(select(Alert).where(Alert.alert_type == "palier_up", Alert.status == "pending"))
    assert palier is not None
    assert palier.payload["target_tier"] == 3
    # promotion requiert confirmation → palier courant inchangé.
    assert get_current_tier_number(db) == 1


def test_auto_demotion_with_hysteresis(db_session):
    db = db_session
    _base_settings(db)
    set_current_tier(db, 2)
    db.add(Transaction(tx_type="adjustment", quantity=1, gross_amount=250, net_amount=250,
                       currency="EUR", occurred_at=NOW))
    db.commit()
    _prior_snapshot(db, 2, 250.0)
    _prior_snapshot(db, 1, 250.0)

    result = run_kpi_snapshot(db, now=NOW)

    assert result["transition"]["direction"] == "down"
    assert result["transition"]["auto"] is True
    # rétrogradation appliquée automatiquement.
    assert get_current_tier_number(db) == 1
    assert db.scalar(select(Alert).where(Alert.alert_type == "palier_down")) is not None


def test_no_transition_when_stable(db_session):
    db = db_session
    _base_settings(db)
    set_current_tier(db, 1)
    db.add(Transaction(tx_type="adjustment", quantity=1, gross_amount=200, net_amount=200,
                       currency="EUR", occurred_at=NOW))
    db.commit()
    # capital 200 → palier 1, stable, pas assez d'historique varié.
    result = run_kpi_snapshot(db, now=NOW)
    assert result["transition"] is None
