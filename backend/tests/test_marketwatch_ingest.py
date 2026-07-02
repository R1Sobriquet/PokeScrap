"""Tests d'ingestion Market Intelligence : idempotence upsert + garde-fous."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select

from app.marketwatch.domain import CardSnapshot
from app.models import CardPriceSnapshot, DataQuarantine
from app.services.marketwatch_ingest import ingest_snapshot, run_ingest
from tests.conftest import insert_setting

DAY = dt.date(2026, 6, 1)


def _snap(**kw) -> CardSnapshot:
    base = dict(card_id="sv03.5-161", source="cardmarket", language="EN",
                price_eur=Decimal("42.00"), currency="EUR", captured_at=DAY)
    base.update(kw)
    return CardSnapshot(**base)


def test_upsert_is_idempotent(db_session):
    assert ingest_snapshot(db_session, _snap(), today=DAY) == "stored"
    db_session.commit()
    # Ré-ingestion le même jour → update, pas de doublon.
    assert ingest_snapshot(db_session, _snap(price_eur=Decimal("45.00")), today=DAY) == "stored"
    db_session.commit()

    count = db_session.scalar(select(func.count()).select_from(CardPriceSnapshot))
    assert count == 1
    row = db_session.scalar(select(CardPriceSnapshot))
    assert row.price_eur == Decimal("45.00")


def test_unique_across_sources_and_languages(db_session):
    ingest_snapshot(db_session, _snap(source="cardmarket", language="EN"), today=DAY)
    ingest_snapshot(db_session, _snap(source="ppt", language="EN"), today=DAY)
    ingest_snapshot(db_session, _snap(source="cardmarket", language="FR"), today=DAY)
    db_session.commit()
    assert db_session.scalar(select(func.count()).select_from(CardPriceSnapshot)) == 3


def test_nonpositive_price_quarantined(db_session):
    assert ingest_snapshot(db_session, _snap(price_eur=Decimal("0")), today=DAY) == "quarantined"
    db_session.commit()
    assert db_session.scalar(select(func.count()).select_from(CardPriceSnapshot)) == 0
    assert db_session.scalar(select(func.count()).select_from(DataQuarantine)) == 1


def test_out_of_sanity_bounds_quarantined(db_session):
    insert_setting(db_session, "sanity_bounds_eur", '{"single": [1, 5000]}', "json")
    assert ingest_snapshot(db_session, _snap(price_eur=Decimal("9999")), today=DAY) == "quarantined"
    db_session.commit()
    q = db_session.scalar(select(DataQuarantine))
    assert "out_of_sanity_bounds" in q.reason


def test_outlier_vs_median_quarantined(db_session):
    # Trois points ~10€ puis un à 100€ (x10) → rejeté comme outlier.
    for i in range(3):
        ingest_snapshot(db_session, _snap(price_eur=Decimal("10.00"),
                                          captured_at=DAY - dt.timedelta(days=i + 1)), today=DAY)
    db_session.commit()
    assert ingest_snapshot(db_session, _snap(price_eur=Decimal("100.00")), today=DAY) == "quarantined"


class _FakeSource:
    code = "cardmarket"

    def __init__(self, snaps, unmatched=()):
        self._snaps = snaps
        self.unmatched = list(unmatched)

    def fetch(self):
        return self._snaps


def test_run_ingest_stores_and_reports_unmatched(db_session):
    src = _FakeSource([_snap(), _snap(card_id="swsh7-215")], unmatched=[("x", None)])
    res = run_ingest(db_session, sources=[src], today=DAY)
    assert res["stored"] == 2
    assert res["unmatched"] == 1
    assert db_session.scalar(select(func.count()).select_from(CardPriceSnapshot)) == 2
