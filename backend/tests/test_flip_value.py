"""Tests flip value : acheter au MSRP (restock) vs valeur marché → verdict."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app.models import Alert, MarketPriceSnapshot, Product, Retailer, RetailOffer, Watchlist
from app.services.flip_value import flip_for_offer, flip_verdict, market_value_eur
from app.services.retail_jobs import run_check_restocks
from tests.conftest import insert_setting

DAY = dt.date(2026, 6, 18)


def _product(db, name="Prismatic Evolutions ETB"):
    p = Product(product_type="sealed", name=name, language="EN")
    db.add(p)
    db.flush()
    return p


def _mkt(db, ref, market, price, source="ppt"):
    db.add(MarketPriceSnapshot(product_ref=ref, source=source, market=market,
                               product_type="etb", price=Decimal(str(price)), currency=("USD" if market == "us" else "EUR"),
                               captured_at=dt.datetime(2026, 6, 18), captured_date=DAY))


def test_market_value_prefers_eu_then_us_then_poketrace(db_session):
    p = _product(db_session)
    _mkt(db_session, str(p.id), "eu", 90.0)
    _mkt(db_session, str(p.id), "us", 110.0)
    db_session.commit()
    val, src = market_value_eur(db_session, p.id, fx=0.9, market="US")
    assert val == 90.0 and src.startswith("market:")  # EU prioritaire


def test_market_value_us_times_fx_when_no_eu(db_session):
    p = _product(db_session)
    _mkt(db_session, str(p.id), "us", 100.0)
    db_session.commit()
    val, _src = market_value_eur(db_session, p.id, fx=0.9, market="US")
    assert val == 90.0


def test_flip_verdict_thresholds():
    assert flip_verdict(40)[0] == "STRONG BUY"
    assert flip_verdict(20)[0] == "BUY"
    assert flip_verdict(3)[0] == "FAIR"
    assert flip_verdict(-10)[0] == "PASS"


def test_flip_for_offer_computes_upside(db_session):
    p = _product(db_session)
    _mkt(db_session, str(p.id), "eu", 90.0)
    r = Retailer(code="cultura", name="Cultura", is_active=1)
    db_session.add(r)
    db_session.flush()
    o = RetailOffer(retailer_id=r.id, url="https://c/p/etb.html", title="ETB",
                    current_stock_state="in_stock", current_price=Decimal("50.00"),
                    is_watched=1, product_id=p.id)
    db_session.add(o)
    db_session.commit()
    flip = flip_for_offer(db_session, o, fx=0.9, market="US")
    assert flip["market_value"] == 90.0
    assert flip["upside_pct"] == 80.0  # (90-50)/50
    assert flip["verdict"] == "STRONG BUY"


def test_unmatched_offer_returns_retail_only(db_session):
    r = Retailer(code="cultura", name="Cultura", is_active=1)
    db_session.add(r)
    db_session.flush()
    o = RetailOffer(retailer_id=r.id, url="https://c/p/x.html", title="X",
                    current_stock_state="in_stock", current_price=Decimal("50.00"), is_watched=1)
    db_session.add(o)
    db_session.commit()
    flip = flip_for_offer(db_session, o, fx=0.9, market="US")
    assert flip["verdict"] is None and flip["retail_price"] == 50.0


# ------------------------------------------------------------- enrichissement alerte
_IN = ('<script type="application/ld+json">{"@type":"Product","name":"ETB",'
       '"offers":{"@type":"Offer","price":"50","priceCurrency":"EUR","availability":"InStock"}}</script>')


def _enable(db):
    insert_setting(db, "retail_sourcing_enabled", "true", "bool")
    insert_setting(db, "retail_dry_run", "false", "bool")
    insert_setting(db, "retail_cultura_enabled", "true", "bool")


def _seed_matched_offer(db, market_price):
    p = _product(db)
    _mkt(db, str(p.id), "eu", market_price)
    r = Retailer(code="cultura", name="Cultura", is_active=1)
    db.add(r)
    db.flush()
    o = RetailOffer(retailer_id=r.id, url="https://c/p/etb.html", title="ETB",
                    current_stock_state="out_of_stock", is_watched=1, product_id=p.id)
    db.add(o)
    db.commit()


def test_restock_alert_carries_buy_verdict(db_session):
    _enable(db_session)
    _seed_matched_offer(db_session, market_price=90.0)  # marché 90 > MSRP 50 → BUY
    run_check_restocks(db_session, http_get=lambda u, h: (200, _IN, {}))
    alert = db_session.scalar(select(Alert).where(Alert.alert_type == "restock"))
    assert alert is not None
    assert alert.severity == "warning"  # flip ≥ seuil → instantané
    assert alert.payload["verdict"] == "STRONG BUY"
    assert alert.payload["market_value"] == 90.0


def test_restock_below_market_is_digested(db_session):
    _enable(db_session)
    insert_setting(db_session, "restock_min_flip_pct", "10", "decimal")
    _seed_matched_offer(db_session, market_price=45.0)  # marché 45 < MSRP 50 → PASS
    run_check_restocks(db_session, http_get=lambda u, h: (200, _IN, {}))
    alert = db_session.scalar(select(Alert).where(Alert.alert_type == "restock"))
    assert alert is not None
    assert alert.severity == "info"  # sous le seuil → digest, pas de ping
    assert alert.payload["verdict"] == "PASS"
