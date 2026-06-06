"""Tests d'exécution de vente : ledger + 30/70 + stages, atomique & idempotent."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from app.models import Alert, Position, Product, Transaction
from app.services.interactions import handle_sell_executed
from tests.conftest import insert_setting

NOW = dt.datetime(2026, 6, 5, 12, 0, 0)


def _setup(db, *, qty=10, avg_cost=10.0):
    insert_setting(db, "reinvest_lock_pct", "30", "decimal")
    insert_setting(db, "lock_only_positive_profit", "true", "bool")
    p = Product(product_type="single", name="Charizard", language="EN", poketrace_id="pt-1")
    db.add(p)
    db.commit()
    pos = Position(product_id=p.id, quantity=qty, avg_cost=avg_cost, acquired_at=NOW, status="held")
    db.add(pos)
    db.commit()
    return pos


def _sell_alert(db, pos, *, action="secure_capital", stages=("capital_secured",), reserve=0):
    a = Alert(
        alert_type="sell_x2", severity="critical", status="pending",
        product_id=pos.product_id, position_id=pos.id, title="Vente",
        payload={"action": action, "stages_to_set": list(stages),
                 "qty_suggested": 5, "speculative_reserve_qty": reserve},
        created_at=NOW,
    )
    db.add(a)
    db.commit()
    return a


def test_sell_executed_writes_ledger_and_locks(db_session):
    pos = _setup(db_session)
    alert = _sell_alert(db_session, pos)

    res = handle_sell_executed(db_session, alert.id, gross_amount=100.0, fees=5.0, qty=5)

    assert res["status"] == "ok"
    tx = db_session.scalar(select(Transaction).where(Transaction.tx_type == "sell"))
    assert float(tx.net_amount) == 95.0           # brut − frais
    assert float(tx.cost_basis) == 50.0           # avg_cost × qty
    assert tx.quantity == 5

    pos = db_session.get(Position, pos.id)
    assert pos.quantity == 5
    assert pos.status == "partially_sold"
    assert pos.stage_capital_secured == 1         # stage posé à l'exécution

    # 30/70 : profit 45 → verrouillage 13.5, alerte reinvest émise.
    assert res["profit"] == 45.0
    assert res["locked"] == 13.5
    reinvest = db_session.scalar(select(Alert).where(Alert.alert_type == "reinvest"))
    assert reinvest is not None and reinvest.payload["locked"] == 13.5
    assert db_session.get(Alert, alert.id).status == "acknowledged"


def test_sell_executed_idempotent(db_session):
    pos = _setup(db_session)
    alert = _sell_alert(db_session, pos)

    handle_sell_executed(db_session, alert.id, gross_amount=100.0, fees=5.0, qty=5)
    replay = handle_sell_executed(db_session, alert.id, gross_amount=100.0, fees=5.0, qty=5)

    assert replay["status"] == "already_processed"
    assert db_session.scalar(select(func.count()).select_from(Transaction)) == 1


def test_structured_sets_speculative_reserve(db_session):
    pos = _setup(db_session, qty=8)
    pos.stage_capital_secured = 1
    db_session.commit()
    alert = _sell_alert(db_session, pos, action="structured_25_50_25",
                        stages=("structured",), reserve=2)

    handle_sell_executed(db_session, alert.id, gross_amount=60.0, fees=0.0, qty=2)

    pos = db_session.get(Position, pos.id)
    assert pos.stage_structured == 1
    assert pos.is_speculative_reserve == 1


def test_sell_fully_sold_status(db_session):
    pos = _setup(db_session, qty=5)
    alert = _sell_alert(db_session, pos)
    res = handle_sell_executed(db_session, alert.id, gross_amount=100.0, fees=0.0, qty=5)
    assert res["position_status"] == "sold"
    assert db_session.get(Position, pos.id).quantity == 0
