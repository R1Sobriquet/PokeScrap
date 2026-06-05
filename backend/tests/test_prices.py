"""Tests du service de lecture get_latest_price."""

from __future__ import annotations

import datetime as dt

from app.models import PriceSnapshot, Product
from app.services.prices import get_latest_price
from tests.conftest import insert_setting


def _product(db) -> int:
    p = Product(product_type="single", name="Test", language="EN", poketrace_id="uuid-x")
    db.add(p)
    db.commit()
    return p.id


def _snap(db, pid, *, captured_at, condition="NM", grade_company="RAW", grade=None,
          avg=100, marketplace="tcgplayer"):
    db.add(
        PriceSnapshot(
            product_id=pid, source="poketrace", market="US", marketplace=marketplace,
            grade_company=grade_company, grade=grade, condition_code=condition,
            currency="USD", price_avg=avg, captured_at=captured_at,
        )
    )
    db.commit()


def test_returns_most_recent_raw(db_session):
    insert_setting(db_session, "valuation_market", "US", "string")
    pid = _product(db_session)
    base = dt.datetime(2026, 6, 5, 10, 0, 0)
    _snap(db_session, pid, captured_at=base, avg=100)
    _snap(db_session, pid, captured_at=base + dt.timedelta(hours=2), avg=120)

    latest = get_latest_price(db_session, pid)
    assert latest is not None
    assert float(latest.price_avg) == 120


def test_filters_by_tier(db_session):
    insert_setting(db_session, "valuation_market", "US", "string")
    pid = _product(db_session)
    base = dt.datetime(2026, 6, 5, 10, 0, 0)
    _snap(db_session, pid, captured_at=base, condition="NM", avg=100)
    _snap(db_session, pid, captured_at=base, condition="LP", avg=60)
    _snap(db_session, pid, captured_at=base, grade_company="PSA", grade="10", condition=None, avg=900)

    assert float(get_latest_price(db_session, pid, condition="NM").price_avg) == 100
    assert float(get_latest_price(db_session, pid, condition="LP").price_avg) == 60
    psa = get_latest_price(db_session, pid, grade_company="PSA", grade="10", condition=None)
    assert float(psa.price_avg) == 900


def test_returns_none_when_absent(db_session):
    insert_setting(db_session, "valuation_market", "US", "string")
    pid = _product(db_session)
    assert get_latest_price(db_session, pid) is None
