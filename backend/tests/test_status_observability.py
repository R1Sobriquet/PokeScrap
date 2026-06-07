"""Tests observabilité : /status, heartbeats, dead-man's switch."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.models import AccountSnapshot, Alert, PriceSnapshot, Product, SourcingListing
from app.services.health_status import (
    get_status,
    record_backup,
    record_heartbeat,
    run_dead_mans_switch,
)

NOW = dt.datetime(2026, 6, 5, 12, 0, 0)


def _product(db):
    p = Product(product_type="single", name="X", language="EN", poketrace_id="pt-x")
    db.add(p)
    db.commit()
    return p


def test_status_aggregates_freshness(db_session):
    db = db_session
    p = _product(db)
    db.add(PriceSnapshot(product_id=p.id, source="poketrace", market="US", marketplace="tcgplayer",
                         grade_company="RAW", condition_code="NM", currency="USD", price_avg=100,
                         captured_at=NOW - dt.timedelta(minutes=30)))
    db.add(SourcingListing(platform="vinted", url="u", raw_title="t", asking_price=1,
                           status="new", detected_at=NOW - dt.timedelta(minutes=60)))
    db.add(AccountSnapshot(snapshot_date=NOW.date(), total_portfolio_value=0, capital_invested=0,
                           cash_available=0, realized_profit_net=0))
    db.commit()
    record_heartbeat(db, "scheduler", now=NOW - dt.timedelta(minutes=2))
    record_backup(db, now=NOW - dt.timedelta(hours=5))

    status = get_status(db, now=NOW)
    assert status["db"] == "ok"
    assert status["freshness"]["price_age_min"] == 30.0
    assert status["freshness"]["sourcing_age_min"] == 60.0
    assert status["freshness"]["last_snapshot_date"] == NOW.date().isoformat()
    assert status["freshness"]["backup_age_min"] == 300.0
    assert status["heartbeats_age_min"]["scheduler"] == 2.0


def test_dead_mans_switch_fires_on_stale_job(db_session):
    db = db_session
    # heartbeat scheduler vieux de 800 min > 720 → tech_error.
    record_heartbeat(db, "scheduler", now=NOW - dt.timedelta(minutes=800))
    res = run_dead_mans_switch(db, now=NOW)
    assert any(s["job"] == "scheduler" for s in res["stale"])
    alert = db.scalar(select(Alert).where(Alert.alert_type == "tech_error"))
    assert alert is not None and alert.severity == "critical"


def test_dead_mans_switch_quiet_when_fresh(db_session):
    db = db_session
    record_heartbeat(db, "scheduler", now=NOW - dt.timedelta(minutes=5))
    res = run_dead_mans_switch(db, now=NOW)
    assert res["stale"] == []
    assert db.scalar(select(Alert).where(Alert.alert_type == "tech_error")) is None


def test_dead_mans_switch_dedup(db_session):
    db = db_session
    record_heartbeat(db, "scheduler", now=NOW - dt.timedelta(minutes=800))
    run_dead_mans_switch(db, now=NOW)
    run_dead_mans_switch(db, now=NOW)  # re-run → pas de doublon
    alerts = db.scalars(select(Alert).where(Alert.alert_type == "tech_error")).all()
    assert len(alerts) == 1
