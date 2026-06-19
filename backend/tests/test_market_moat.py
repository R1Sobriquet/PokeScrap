"""Tests moat marché : garde-fous + quarantaine, snapshot idempotent, moniteur."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select

from app.marketdata.domain import PriceQuote, WatchItem
from app.marketdata.ports import MarketDataPort
from app.models import Alert, DataQuarantine, MarketPriceSnapshot, Product, Watchlist
from app.services.market_ingest import ingest_quote
from app.services.market_snapshot import run_market_snapshot
from app.services.source_health import check_sources, record_source_run
from tests.conftest import insert_setting

NOW = dt.datetime(2026, 6, 18, 9, 0, 0)


def _q(price, *, market="eu", currency="EUR", ptype="etb", ref="42", source="ppt"):
    return PriceQuote(ref, source, market, Decimal(str(price)) if price is not None else None,
                      currency, ptype, {}, NOW)


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


# --------------------------------------------------------------- garde-fous
def test_valid_quote_stored_then_idempotent(db_session):
    assert ingest_quote(db_session, _q(95.0), NOW) == "stored"
    db_session.commit()
    assert _count(db_session, MarketPriceSnapshot) == 1
    # même produit/source/marché/jour → pas de doublon, mise à jour.
    assert ingest_quote(db_session, _q(99.0), NOW) == "stored"
    db_session.commit()
    assert _count(db_session, MarketPriceSnapshot) == 1
    assert db_session.scalar(select(MarketPriceSnapshot.price)) == Decimal("99.00")


def test_currency_market_mismatch_quarantined(db_session):
    assert ingest_quote(db_session, _q(95.0, market="us", currency="EUR"), NOW) == "quarantined"
    db_session.commit()
    assert _count(db_session, MarketPriceSnapshot) == 0
    assert _count(db_session, DataQuarantine) == 1


def test_sanity_bounds_reject(db_session):
    insert_setting(db_session, "sanity_bounds_eur", '{"etb":[15,400],"autre":[1,5000]}', "json")
    assert ingest_quote(db_session, _q(2.0), NOW) == "quarantined"      # ETB à 2€ → rejet
    assert ingest_quote(db_session, _q(5000.0), NOW) == "quarantined"   # ETB à 5000€ → rejet
    db_session.commit()
    assert _count(db_session, MarketPriceSnapshot) == 0
    assert _count(db_session, DataQuarantine) == 2


def test_outlier_vs_median_quarantined(db_session):
    for i, p in enumerate((90, 92, 94)):  # historique cohérent
        db_session.add(MarketPriceSnapshot(
            product_ref="42", source="ppt", market="eu", product_type="etb",
            price=Decimal(str(p)), currency="EUR",
            captured_at=NOW - dt.timedelta(days=i + 1),
            captured_date=(NOW - dt.timedelta(days=i + 1)).date()))
    db_session.commit()
    assert ingest_quote(db_session, _q(900.0), NOW) == "quarantined"  # x~10 médiane
    db_session.commit()
    assert db_session.scalar(select(DataQuarantine.reason)).startswith("outlier")


# --------------------------------------------------------------- snapshot job
class _FakeSource(MarketDataPort):
    code = "ppt"
    capabilities = frozenset({"quotes"})

    def fetch_quotes(self, items):
        return [PriceQuote(it.product_ref, "ppt", "eu", Decimal("85.00"), "EUR",
                           it.product_type, {}, NOW) for it in items]


def _seed_watch(db):
    p = Product(product_type="sealed", name="Prismatic Evolutions ETB", language="EN")
    db.add(p)
    db.flush()
    db.add(Watchlist(product_id=p.id, tier="S", is_active=1))
    db.commit()


def test_snapshot_job_stores_and_is_idempotent(db_session):
    insert_setting(db_session, "marketdata_enabled", "true", "bool")
    _seed_watch(db_session)
    res = run_market_snapshot(db_session, sources={"ppt": _FakeSource()})
    assert res["stored"] == 1
    assert _count(db_session, MarketPriceSnapshot) == 1
    # re-run même jour → idempotent.
    run_market_snapshot(db_session, sources={"ppt": _FakeSource()})
    assert _count(db_session, MarketPriceSnapshot) == 1


def test_snapshot_disabled_noop(db_session):
    res = run_market_snapshot(db_session, sources={"ppt": _FakeSource()})
    assert "désactivé" in res["summary"]


# --------------------------------------------------------------- moniteur santé
def test_health_alert_on_stale_source(db_session):
    insert_setting(db_session, "marketdata_ppt_enabled", "true", "bool")
    # dernier run il y a 50h → muette.
    record_source_run(db_session, "ppt",
                      {"requests": 5, "stored": 5, "errors": 0, "blocked": 0, "quarantined": 0},
                      now=NOW - dt.timedelta(hours=50))
    res = check_sources(db_session, now=NOW)
    assert res["unhealthy"] == 1 and res["alerts"] == 1
    alert = db_session.scalar(select(Alert).where(Alert.alert_type == "health"))
    assert alert is not None and alert.payload["source"] == "ppt"


def test_healthy_source_no_alert(db_session):
    insert_setting(db_session, "marketdata_ppt_enabled", "true", "bool")
    record_source_run(db_session, "ppt",
                      {"requests": 5, "stored": 5, "errors": 0, "blocked": 0, "quarantined": 0},
                      now=NOW)
    res = check_sources(db_session, now=NOW)
    assert res["alerts"] == 0
    assert _count(db_session, Alert) == 0
