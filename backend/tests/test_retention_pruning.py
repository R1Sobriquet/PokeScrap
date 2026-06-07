"""Tests de l'élagage price_snapshots (1/jour/tier, fenêtre détaillée préservée)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from app.models import PriceSnapshot, Product
from app.services.retention import prune_price_snapshots
from tests.conftest import insert_setting

NOW = dt.datetime(2026, 6, 5, 12, 0, 0)


def _snap(db, pid, captured_at, avg):
    db.add(PriceSnapshot(product_id=pid, source="poketrace", market="US", marketplace="tcgplayer",
                         grade_company="RAW", condition_code="NM", currency="USD",
                         price_avg=avg, captured_at=captured_at))
    db.commit()


def _setup(db):
    insert_setting(db, "price_snapshot_pruning_enabled", "true", "bool")
    insert_setting(db, "price_snapshot_detail_days", "60", "int")
    p = Product(product_type="single", name="X", language="EN", poketrace_id="pt-x")
    db.add(p)
    db.commit()
    # Jour -100 : 3 snapshots intraday (mêmes tier/jour) → 2 à élaguer, 1 gardé.
    day100 = NOW - dt.timedelta(days=100)
    for h in (8, 12, 18):
        _snap(db, p.id, day100.replace(hour=h), 100 + h)
    # Jour -90 : 1 snapshot → conservé.
    _snap(db, p.id, (NOW - dt.timedelta(days=90)).replace(hour=10), 90)
    # Dans la fenêtre détaillée (jour -1) : 2 intraday → intouchés.
    day1 = NOW - dt.timedelta(days=1)
    _snap(db, p.id, day1.replace(hour=9), 1)
    _snap(db, p.id, day1.replace(hour=15), 2)
    return p


def test_pruning_keeps_one_per_day_per_tier(db_session):
    db = db_session
    _setup(db)
    res = prune_price_snapshots(db, now=NOW)
    assert res["deleted"] == 2  # seuls les intraday du jour -100 hors fenêtre
    total = db.scalar(select(func.count()).select_from(PriceSnapshot))
    assert total == 4  # 1 (j-100) + 1 (j-90) + 2 (j-1 dans la fenêtre)


def test_pruning_preserves_detailed_window(db_session):
    db = db_session
    _setup(db)
    prune_price_snapshots(db, now=NOW)
    # Les 2 snapshots du jour -1 (dans la fenêtre) sont intacts.
    recent = db.scalar(
        select(func.count()).select_from(PriceSnapshot)
        .where(PriceSnapshot.captured_at >= NOW - dt.timedelta(days=60))
    )
    assert recent == 2


def test_pruning_disabled_is_noop(db_session):
    db = db_session
    insert_setting(db, "price_snapshot_pruning_enabled", "false", "bool")
    insert_setting(db, "price_snapshot_detail_days", "60", "int")
    p = Product(product_type="single", name="X", language="EN", poketrace_id="pt-x")
    db.add(p)
    db.commit()
    _snap(db, p.id, NOW - dt.timedelta(days=100, hours=1), 1)
    _snap(db, p.id, NOW - dt.timedelta(days=100, hours=2), 2)
    res = prune_price_snapshots(db, now=NOW)
    assert res["status"] == "disabled"
    assert db.scalar(select(func.count()).select_from(PriceSnapshot)) == 2
