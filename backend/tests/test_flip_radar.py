"""Tests Flip Radar : classement des opportunités + alerte proactive dédupée."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select

from app.models import Alert, MarketPriceSnapshot, Product, Retailer, RetailOffer
from app.services.flip_radar import run_flip_radar, scan_opportunities
from tests.conftest import insert_setting

DAY = dt.date(2026, 6, 18)


def _matched_offer(db, *, retail, market_price, state="in_stock", name="ETB"):
    p = Product(product_type="sealed", name=name, language="EN")
    db.add(p)
    db.flush()
    db.add(MarketPriceSnapshot(product_ref=str(p.id), source="ppt", market="eu",
                               product_type="etb", price=Decimal(str(market_price)), currency="EUR",
                               captured_at=dt.datetime(2026, 6, 18), captured_date=DAY))
    r = db.scalar(select(Retailer).where(Retailer.code == "cultura"))
    if r is None:
        r = Retailer(code="cultura", name="Cultura", is_active=1)
        db.add(r)
        db.flush()
    o = RetailOffer(retailer_id=r.id, url=f"https://c/{name}", title=name,
                    current_stock_state=state, current_price=Decimal(str(retail)),
                    is_watched=1, product_id=p.id)
    db.add(o)
    db.commit()
    return o


def test_scan_ranks_by_net_upside(db_session):
    _matched_offer(db_session, retail=50, market_price=120, name="Big flip")   # gros flip
    _matched_offer(db_session, retail=50, market_price=60, name="Small flip")  # petit flip
    opps = scan_opportunities(db_session, in_stock_only=True)
    assert [o["title"] for o in opps] == ["Big flip", "Small flip"]  # classé décroissant
    assert opps[0]["net_upside_pct"] > opps[1]["net_upside_pct"]
    assert opps[0]["est_profit"] is not None


def test_scan_excludes_out_of_stock_and_unmatched(db_session):
    _matched_offer(db_session, retail=50, market_price=120, state="out_of_stock", name="OOS")
    r = db_session.scalar(select(Retailer).where(Retailer.code == "cultura")) or \
        Retailer(code="cultura", name="Cultura", is_active=1)
    db_session.add(r)
    db_session.flush()
    db_session.add(RetailOffer(retailer_id=r.id, url="https://c/u", title="Unmatched",
                               current_stock_state="in_stock", current_price=Decimal("50"), is_watched=1))
    db_session.commit()
    assert scan_opportunities(db_session, in_stock_only=True) == []


def test_flip_radar_alerts_then_dedups(db_session):
    insert_setting(db_session, "retail_dry_run", "false", "bool")
    insert_setting(db_session, "flip_alert_min_pct", "25", "decimal")
    _matched_offer(db_session, retail=50, market_price=120, name="Big flip")  # ~111% net > 25%

    res = run_flip_radar(db_session)
    assert res["opportunities"] == 1 and res["alerts"] == 1
    alert = db_session.scalar(select(Alert).where(Alert.alert_type == "restock"))
    assert alert.payload["subtype"] == "FLIP" and alert.payload["verdict"] == "STRONG BUY"

    # 2e run immédiat → dédup (cooldown), pas de nouvelle alerte.
    res2 = run_flip_radar(db_session)
    assert res2["alerts"] == 0
    assert db_session.scalar(select(func.count()).select_from(Alert)) == 1


def test_flip_radar_dry_run_no_alert(db_session):
    insert_setting(db_session, "retail_dry_run", "true", "bool")
    insert_setting(db_session, "flip_alert_min_pct", "25", "decimal")
    _matched_offer(db_session, retail=50, market_price=120, name="Big flip")
    res = run_flip_radar(db_session)
    assert res["opportunities"] == 1 and res["alerts"] == 0
    assert db_session.scalar(select(func.count()).select_from(Alert)) == 0
