"""Tests du ledger : 5 KPIs + cascade sur un jeu de transactions connu."""

from __future__ import annotations

import datetime as dt

from app.models import Lot, Position, Product, Transaction
from app.services.ledger import compute_kpis
from tests.conftest import insert_setting

NOW = dt.datetime(2026, 6, 5, 12, 0, 0)


def _settings(db):
    insert_setting(db, "valuation_market", "US", "string")
    insert_setting(db, "fx_usd_eur", "0.92", "decimal")
    insert_setting(db, "reinvest_lock_pct", "30", "decimal")
    insert_setting(db, "lock_only_positive_profit", "true", "bool")
    insert_setting(db, "tax_provision_pct", "12.3", "decimal")


def test_five_kpis_on_known_set(db_session):
    db = db_session
    _settings(db)

    # Capital de départ + une vente profitable.
    db.add(Transaction(tx_type="adjustment", quantity=1, gross_amount=200, net_amount=200,
                       currency="EUR", occurred_at=NOW))
    db.add(Transaction(tx_type="sell", quantity=1, gross_amount=100, platform_fees=5,
                       net_amount=95, cost_basis=40, currency="EUR", occurred_at=NOW))
    # Capital investi : une position + un lot ouvert.
    p = Product(product_type="single", name="X", language="EN", poketrace_id="pt-x")
    db.add(p)
    db.commit()
    db.add(Position(product_id=p.id, quantity=3, avg_cost=10, acquired_at=NOW, status="held"))
    db.add(Lot(total_cost=50, currency="EUR", purchased_at=NOW, status="received"))
    db.commit()

    k = compute_kpis(db, now=NOW)

    assert k["cash_total"] == 295.0                 # 200 + 95
    assert k["capital_invested"] == 80.0            # 3×10 + lot 50
    assert k["realized_profit_net"] == 55.0         # 95 − 40
    assert k["turnover_cumulative"] == 100.0        # Σ gross(sell)
    assert k["tax_provision"] == 12.3               # 100 × 12.3 %
    assert k["cash_locked"] == 16.5                 # 30 % × 55
    assert k["cash_active"] == 278.5                # 295 − 16.5
    assert k["operational_capital"] == 358.5        # 278.5 + 80
    assert k["capital_rotation_rate"] == 0.5        # COGS 40 / 80
    # informatif : cash + valeur positions (fallback coût 30) + lot (50)
    assert k["total_portfolio_value"] == 375.0


def test_tax_provision_informative_does_not_reduce_cash_active(db_session):
    db = db_session
    _settings(db)
    insert_setting(db, "tax_provision_mode", "informative", "string")
    db.add(Transaction(tx_type="sell", quantity=1, gross_amount=100, platform_fees=0,
                       net_amount=100, cost_basis=40, currency="EUR", occurred_at=NOW))
    db.commit()
    k = compute_kpis(db, now=NOW)
    # cash_active = cash_total − cash_locked ; la provision n'entre pas dans le calcul.
    assert k["cash_active"] == k["cash_total"] - k["cash_locked"]
    assert k["tax_provision"] == 12.3
