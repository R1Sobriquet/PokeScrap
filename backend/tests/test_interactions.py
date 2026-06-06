"""Tests des handlers d'interaction + portefeuille (lots ouverts)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from app.models import Alert, Lot, SourcingListing, Transaction
from app.services.interactions import handle_buy_purchased, handle_ignore
from app.services.portfolio import portfolio_state, record_deposit

NOW = dt.datetime(2026, 6, 5, 12, 0, 0)


def _listing(db, *, asking=40, ship=3, prot=1):
    listing = SourcingListing(
        platform="vinted", url="https://example.test/x", raw_title="Lot test",
        asking_price=asking, shipping_cost=ship, protection_cost=prot, currency="EUR",
        estimated_total_cards=1, detected_products=[], status="flagged", detected_at=NOW,
    )
    db.add(listing)
    db.commit()
    return listing


def _buy_alert(db, listing):
    a = Alert(alert_type="buy", severity="warning", status="pending",
              sourcing_listing_id=listing.id, title="Achat", payload={}, created_at=NOW)
    db.add(a)
    db.commit()
    return a


def test_buy_purchased_creates_lot_and_transaction(db_session):
    listing = _listing(db_session)
    alert = _buy_alert(db_session, listing)

    res = handle_buy_purchased(db_session, alert.id, price_paid=44.0, fees=2.0)

    assert res["status"] == "ok"
    lot = db_session.scalar(select(Lot))
    assert float(lot.total_cost) == 44.0
    assert lot.source_listing_id == listing.id
    tx = db_session.scalar(select(Transaction).where(Transaction.tx_type == "buy"))
    assert float(tx.net_amount) == -46.0  # -(prix + frais)
    assert float(tx.platform_fees) == 2.0
    assert db_session.get(SourcingListing, listing.id).status == "bought"
    assert db_session.get(Alert, alert.id).status == "acknowledged"


def test_buy_purchased_is_idempotent(db_session):
    listing = _listing(db_session)
    alert = _buy_alert(db_session, listing)

    handle_buy_purchased(db_session, alert.id, price_paid=44.0, fees=2.0)
    replay = handle_buy_purchased(db_session, alert.id, price_paid=44.0, fees=2.0)

    assert replay["status"] == "already_processed"
    assert db_session.scalar(select(func.count()).select_from(Lot)) == 1
    assert db_session.scalar(select(func.count()).select_from(Transaction)) == 1


def test_ignore_dismisses_listing_and_alert(db_session):
    listing = _listing(db_session)
    alert = _buy_alert(db_session, listing)

    res = handle_ignore(db_session, alert.id)
    assert res["status"] == "ok"
    assert db_session.get(SourcingListing, listing.id).status == "dismissed"
    assert db_session.get(Alert, alert.id).status == "dismissed"

    replay = handle_ignore(db_session, alert.id)
    assert replay["status"] == "already_processed"


def test_portfolio_state_counts_open_lots(db_session):
    record_deposit(db_session, 150.0, occurred_at=NOW)
    listing = _listing(db_session)
    alert = _buy_alert(db_session, listing)
    handle_buy_purchased(db_session, alert.id, price_paid=44.0, fees=2.0)

    state = portfolio_state(db_session)
    assert state.cash_active == 150.0 - 46.0      # cash après sortie
    assert state.capital_invested == 44.0          # lot ouvert (non liquidé)
    assert state.operational_capital == 104.0 + 44.0
