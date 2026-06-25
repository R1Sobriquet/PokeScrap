"""Tests PokéStock FR Phase B : dispo en magasin (endpoint, alerte nommée, garde-fous)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select

from app.models import Alert, OfferStoreAvailability, Retailer, RetailOffer, RetailStockEvent, StoreLocation
from app.retail.domain import Retailer as RetailerDC
from app.retail.fetch import HttpRetailSource
from app.retail.parse import parse_store_availability_json
from app.services.retail_store_jobs import run_check_store_stock
from tests.conftest import insert_setting

TEMPLATE = "https://m/api/store-avail?sku={sku}&store={store_code}"


def test_parse_store_availability_states():
    assert parse_store_availability_json({"availability": "InStock", "price": 60})[0] == "in_store"
    assert parse_store_availability_json({"stock": "rupture"})[0] == "out_of_store"
    assert parse_store_availability_json({"stockLevel": "low_stock"})[0] == "limited"
    assert parse_store_availability_json({"foo": 1})[0] == "unknown"
    state, price = parse_store_availability_json({"available": True, "price": "59.90"})
    assert state == "in_store" and price == Decimal("59.90")


def test_fetch_store_availability_endpoint_and_304():
    def fake(url, headers):
        assert "store=AGEN" in url and "sku=SKU1" in url
        return 200, '{"availability":"InStore","price":"59.90"}', {"etag": "s1"}
    src = HttpRetailSource(RetailerDC(code="m", name="M", base_url="https://m"), http_get=fake)
    (state, price), etag = src.fetch_store_availability("https://m/p", template=TEMPLATE,
                                                        sku="SKU1", store_code="AGEN")
    assert state == "in_store" and price == Decimal("59.90") and etag == "s1"
    res, etag2 = HttpRetailSource(RetailerDC(code="m", name="M", base_url="https://m"),
                                  http_get=lambda u, h: (304, "", {})).fetch_store_availability(
        "https://m/p", template=TEMPLATE, etag="s1")
    assert res is None and etag2 == "s1"


def _enable(db):
    insert_setting(db, "retail_sourcing_enabled", "true", "bool")
    insert_setting(db, "retail_store_stock_enabled", "true", "bool")
    insert_setting(db, "retail_dry_run", "false", "bool")
    insert_setting(db, "retail_micromania_enabled", "true", "bool")


def _seed(db):
    r = Retailer(code="micromania", name="Micromania", is_active=1,
                 store_availability_url_template=TEMPLATE)
    db.add(r)
    db.flush()
    o = RetailOffer(retailer_id=r.id, url="https://m/p/etb.html", title="ETB",
                    retailer_sku="SKU1", current_stock_state="out_of_stock", is_watched=1)
    s = StoreLocation(retailer_id=r.id, store_code="AGEN", name="Micromania Agen/Boé",
                      city="Boé", is_watched=1)
    db.add_all([o, s])
    db.commit()
    return r, o, s


def test_store_alert_mentions_store_name(db_session):
    _enable(db_session)
    _seed(db_session)

    def fake(url, headers):
        return 200, '{"availability":"InStore","price":"59.90"}', {}

    res = run_check_store_stock(db_session, http_get=fake)
    assert res["transitions"] == 1 and res["alerts"] == 1
    osa = db_session.scalar(select(OfferStoreAvailability))
    assert osa.availability_state == "in_store"
    ev = db_session.scalar(select(RetailStockEvent))
    assert ev.store_id == osa.store_id and ev.to_state == "in_store"
    alert = db_session.scalar(select(Alert).where(Alert.alert_type == "restock"))
    assert alert.payload["subtype"] == "STORE"
    assert "Micromania Agen/Boé" in alert.payload["store"] and alert.payload["store_city"] == "Boé"


def test_store_stock_disabled_noop(db_session):
    insert_setting(db_session, "retail_sourcing_enabled", "true", "bool")
    _seed(db_session)
    res = run_check_store_stock(db_session, http_get=lambda u, h: (200, "{}", {}))
    assert "magasin désactivée" in res["summary"]


def test_store_block_triggers_circuit_breaker(db_session):
    _enable(db_session)
    _seed(db_session)
    res = run_check_store_stock(db_session, http_get=lambda u, h: (403, "<html>forbidden</html>", {}))
    assert res["blocked"] == 1 and res["alerts"] == 0
    assert db_session.scalar(select(func.count()).select_from(Alert)) == 0
