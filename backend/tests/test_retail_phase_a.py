"""Tests PokéStock FR Phase A : tiers, endpoint dispo, ETag, token bucket, latence."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app.models import Alert, Retailer, RetailOffer, RetailStockEvent
from app.retail import politeness
from app.retail.fetch import HttpRetailSource
from app.retail.domain import Retailer as RetailerDC
from app.retail.parse import parse_availability_json
from app.services.retail_jobs import (
    _due_for_check,
    _tier_interval_sec,
    _utcnow,
    recheck_offer,
    run_check_restocks,
)
from tests.conftest import insert_setting

NOW = dt.datetime(2026, 6, 18, 9, 0, 0)


# ------------------------------------------------------------- tiers
def test_tier_intervals_ordered():
    hot = RetailOffer(watch_tier="hot")
    nor = RetailOffer(watch_tier="normal")
    cold = RetailOffer(watch_tier="cold")
    h = _tier_interval_sec(hot, hot_sec=45, normal_min=5, cold_min=60)
    n = _tier_interval_sec(nor, hot_sec=45, normal_min=5, cold_min=60)
    c = _tier_interval_sec(cold, hot_sec=45, normal_min=5, cold_min=60)
    assert h == 45 and n == 300 and c == 3600 and h < n < c


def test_due_for_check_respects_interval():
    o = RetailOffer(last_checked_at=NOW - dt.timedelta(seconds=30))
    assert _due_for_check(o, 45, NOW) is False   # 30s < 45s → pas encore
    assert _due_for_check(o, 20, NOW) is True     # 30s > 20s → dû


# ------------------------------------------------------------- endpoint dispo + ETag
def _src(fake):
    return HttpRetailSource(RetailerDC(code="x", name="x", base_url="https://x"), http_get=fake)


def test_fetch_availability_uses_json_endpoint():
    def fake(url, headers):
        assert "/api/avail" in url and headers.get("Accept") == "application/json"
        return 200, '{"availability":"InStock","price":"59.99"}', {"etag": "v1"}
    snap, etag = _src(fake).fetch_availability("https://x/p", template="https://x/api/avail?sku={sku}",
                                               sku="ABC")
    assert snap.source == "json" and snap.stock_state == "in_stock"
    assert snap.price == Decimal("59.99") and etag == "v1"


def test_fetch_availability_304_unchanged():
    snap, etag = _src(lambda u, h: (304, "", {})).fetch_availability(
        "https://x/p", template="https://x/api/avail", etag="v1")
    assert snap is None and etag == "v1"  # inchangé → on saute le parsing


def test_fetch_availability_falls_back_to_page_without_template():
    page = ('<script type="application/ld+json">{"@type":"Product","name":"ETB",'
            '"offers":{"@type":"Offer","price":"50","availability":"InStock"}}</script>')
    snap, etag = _src(lambda u, h: (200, page, {})).fetch_availability("https://x/p")
    assert snap.source == "jsonld" and snap.stock_state == "in_stock"


def test_parse_availability_json_defensive():
    assert parse_availability_json({"available": True, "price": 30}, "u").stock_state == "in_stock"
    assert parse_availability_json({"stock": "rupture"}, "u").stock_state == "out_of_stock"
    assert parse_availability_json({"status": "precommande"}, "u").stock_state == "preorder"
    assert parse_availability_json({"foo": 1}, "u").stock_state == "unknown"


# ------------------------------------------------------------- token bucket (anti-ban)
def test_token_bucket_caps_then_refuses(db_session):
    ok1 = politeness.take_token(db_session, "cultura", NOW, capacity=2, refill_per_sec=0.0)
    ok2 = politeness.take_token(db_session, "cultura", NOW, capacity=2, refill_per_sec=0.0)
    ok3 = politeness.take_token(db_session, "cultura", NOW, capacity=2, refill_per_sec=0.0)
    assert ok1 and ok2 and not ok3  # 2 jetons puis vide (pas de recharge)
    # après recharge (refill), un jeton redevient dispo.
    later = NOW + dt.timedelta(seconds=10)
    assert politeness.take_token(db_session, "cultura", later, capacity=2, refill_per_sec=0.25)


# ------------------------------------------------------------- intégration : dispo JSON + latence
def _enable(db):
    insert_setting(db, "retail_sourcing_enabled", "true", "bool")
    insert_setting(db, "retail_dry_run", "false", "bool")
    insert_setting(db, "retail_cultura_enabled", "true", "bool")


PAGE_OOS = ('<script type="application/ld+json">{"@type":"Product","name":"ETB",'
            '"offers":{"@type":"Offer","price":"50","availability":"OutOfStock"}}</script>')


def test_check_uses_endpoint_and_records_latency(db_session):
    _enable(db_session)
    r = Retailer(code="cultura", name="Cultura", is_active=1,
                 availability_url_template="https://c/api/avail?sku={sku}")
    db_session.add(r)
    db_session.flush()
    db_session.add(RetailOffer(retailer_id=r.id, url="https://c/p/etb.html", title="ETB",
                               retailer_sku="SKU1", current_stock_state="out_of_stock", is_watched=1))
    db_session.commit()

    def fake(url, headers):
        if "/api/avail" in url:
            return 200, '{"availability":"InStock","price":"59.99"}', {"etag": "v9"}
        return 200, PAGE_OOS, {}

    res = run_check_restocks(db_session, http_get=fake)
    assert res["transitions"] == 1 and res["alerts"] == 1
    offer = db_session.scalar(select(RetailOffer))
    assert offer.current_stock_state == "in_stock" and offer.availability_etag == "v9"
    ev = db_session.scalar(select(RetailStockEvent))
    assert ev.detected_to_alert_ms is not None and ev.detected_to_alert_ms >= 0


def test_recheck_offer_immediate(db_session):
    _enable(db_session)
    r = Retailer(code="cultura", name="Cultura", is_active=1)
    db_session.add(r)
    db_session.flush()
    o = RetailOffer(retailer_id=r.id, url="https://c/p/etb.html", title="ETB",
                    current_stock_state="out_of_stock", is_watched=1)
    db_session.add(o)
    db_session.commit()
    page_in = ('<script type="application/ld+json">{"@type":"Product","name":"ETB",'
               '"offers":{"@type":"Offer","price":"50","availability":"InStock"}}</script>')
    res = recheck_offer(db_session, o.id, http_get=lambda u, h: (200, page_in, {}))
    assert res["status"] == "ok" and res["transition"] is True and res["alert"] is True
    assert db_session.scalar(select(Alert).where(Alert.alert_type == "restock")) is not None
