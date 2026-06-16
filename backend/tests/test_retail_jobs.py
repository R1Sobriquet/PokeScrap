"""Tests jobs PokéStock FR : transition→event+alerte, dédup, dry-run, circuit breaker."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import Alert, RetailOffer, RetailStockEvent, Retailer
from app.retail import politeness
from app.services.retail_jobs import (
    _utcnow,
    run_check_restocks,
    run_detect_new_skus,
)
from tests.conftest import insert_setting

PRODUCT_HTML = {
    "in_stock": '<script type="application/ld+json">{"@type":"Product","name":"ETB Pokémon",'
                '"offers":{"@type":"Offer","price":"59.99","priceCurrency":"EUR",'
                '"availability":"https://schema.org/InStock"}}</script>',
    "out": '<script type="application/ld+json">{"@type":"Product","name":"ETB Pokémon",'
           '"offers":{"@type":"Offer","price":"59.99","availability":"OutOfStock"}}</script>',
}


def _fake_get(page_key="in_stock"):
    def get(url, headers):
        return 200, PRODUCT_HTML[page_key], {}
    return get


def _enable(db, *, dry_run=False):
    insert_setting(db, "retail_sourcing_enabled", "true", "bool")
    insert_setting(db, "retail_dry_run", "true" if dry_run else "false", "bool")
    insert_setting(db, "retail_cultura_enabled", "true", "bool")


def _seed_offer(db, state="out_of_stock", watched=1):
    r = Retailer(code="cultura", name="Cultura", is_active=1,
                 sitemap_url="https://c/sitemap.xml")
    db.add(r)
    db.flush()
    o = RetailOffer(retailer_id=r.id, url="https://c/p/etb-pokemon.html",
                    title="ETB Pokémon", current_stock_state=state, is_watched=watched)
    db.add(o)
    db.commit()
    return r, o


def test_restock_transition_creates_event_and_alert(db_session):
    _enable(db_session, dry_run=False)
    _seed_offer(db_session, state="out_of_stock")

    res = run_check_restocks(db_session, http_get=_fake_get("in_stock"))

    assert res["transitions"] == 1 and res["alerts"] == 1
    ev = db_session.scalar(select(RetailStockEvent))
    assert ev.from_state == "out_of_stock" and ev.to_state == "in_stock"
    alert = db_session.scalar(select(Alert))
    assert alert.alert_type == "restock" and alert.status == "pending"
    assert alert.payload["retailer"] == "Cultura" and alert.payload["price"] == 59.99
    offer = db_session.scalar(select(RetailOffer))
    assert offer.current_stock_state == "in_stock"


def test_no_realert_when_already_in_stock(db_session):
    _enable(db_session, dry_run=False)
    _seed_offer(db_session, state="in_stock")

    res = run_check_restocks(db_session, http_get=_fake_get("in_stock"))

    assert res["transitions"] == 0 and res["alerts"] == 0
    assert db_session.scalar(select(func.count()).select_from(Alert)) == 0


def test_dry_run_records_event_but_no_alert(db_session):
    _enable(db_session, dry_run=True)
    _seed_offer(db_session, state="out_of_stock")

    res = run_check_restocks(db_session, http_get=_fake_get("in_stock"))

    assert res["transitions"] == 1 and res["alerts"] == 0
    assert db_session.scalar(select(func.count()).select_from(RetailStockEvent)) == 1
    assert db_session.scalar(select(func.count()).select_from(Alert)) == 0


def test_sourcing_disabled_noop(db_session):
    insert_setting(db_session, "retail_sourcing_enabled", "false", "bool")
    _seed_offer(db_session, state="out_of_stock")
    res = run_check_restocks(db_session, http_get=_fake_get("in_stock"))
    assert "désactivé" in res["summary"]


def test_block_triggers_circuit_breaker_without_crash(db_session):
    _enable(db_session, dry_run=False)
    r, _ = _seed_offer(db_session, state="out_of_stock")

    def blocked_get(url, headers):
        return 403, "<html>forbidden</html>", {}

    res = run_check_restocks(db_session, http_get=blocked_get)

    assert res["blocked"] == 1 and res["alerts"] == 0
    # Le détaillant est désormais en backoff (circuit ouvert).
    assert politeness.is_retailer_blocked(db_session, "cultura", _utcnow())
    assert politeness.retailer_error_count(db_session, "cultura") == 1


def test_detect_new_skus_inserts_offers(db_session):
    _enable(db_session, dry_run=True)
    Retailer  # noqa: B018
    r = Retailer(code="cultura", name="Cultura", is_active=1,
                 sitemap_url="https://c/sitemap.xml")
    db_session.add(r)
    db_session.commit()

    sitemap = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' \
              "<url><loc>https://c/p/coffret-pokemon-1.html</loc></url>" \
              "<url><loc>https://c/p/coffret-pokemon-2.html</loc></url>" \
              "<url><loc>https://c/aide/faq</loc></url></urlset>"

    def get(url, headers):
        return 200, sitemap, {"etag": "abc"}

    res = run_detect_new_skus(db_session, http_get=get)
    assert res["new_offers"] == 2  # le /aide/ est filtré
    urls = set(db_session.scalars(select(RetailOffer.url)).all())
    assert "https://c/p/coffret-pokemon-1.html" in urls
