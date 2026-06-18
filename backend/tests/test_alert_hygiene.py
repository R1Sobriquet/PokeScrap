"""Tests hygiène d'alertes : anti-flapping restock + digest quotidien unique."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from app.models import Alert, DataQuarantine, MatchReview, Product, Retailer, RetailOffer, RetailStockEvent, Watchlist
from app.services.retail_jobs import _utcnow, run_check_restocks
from app.services.source_health import emit_daily_digest
from tests.conftest import insert_setting

NOW = dt.datetime(2026, 6, 18, 9, 0, 0)


def _enable_retail(db):
    insert_setting(db, "retail_sourcing_enabled", "true", "bool")
    insert_setting(db, "retail_dry_run", "false", "bool")
    insert_setting(db, "retail_cultura_enabled", "true", "bool")


def _seed_offer(db, state="out_of_stock"):
    r = Retailer(code="cultura", name="Cultura", is_active=1)
    db.add(r)
    db.flush()
    o = RetailOffer(retailer_id=r.id, url="https://c/p/etb.html", title="ETB",
                    current_stock_state=state, is_watched=1)
    db.add(o)
    db.commit()
    return r, o


_IN = ('<script type="application/ld+json">{"@type":"Product","name":"ETB",'
       '"offers":{"@type":"Offer","price":"50","availability":"InStock"}}</script>')


def test_flapping_offer_does_not_spam(db_session):
    _enable_retail(db_session)
    insert_setting(db_session, "restock_debounce_min", "60", "int")
    _r, o = _seed_offer(db_session, state="out_of_stock")
    # historique d'oscillation récente (relatif à l'horloge réelle du job).
    now = _utcnow()
    for mins in (40, 20):
        db_session.add(RetailStockEvent(offer_id=o.id, from_state="in_stock",
                                        to_state="out_of_stock",
                                        detected_at=now - dt.timedelta(minutes=mins)))
    db_session.commit()

    res = run_check_restocks(db_session, http_get=lambda u, h: (200, _IN, {}))
    # transition détectée mais alerte SUPPRIMÉE (anti-flapping).
    assert res["transitions"] == 1
    assert db_session.scalar(select(func.count()).select_from(Alert)) == 0


def test_daily_digest_single_summary(db_session):
    insert_setting(db_session, "alert_digest_enabled", "true", "bool")
    db_session.add(DataQuarantine(source="ppt", reason="outlier", created_at=NOW))
    db_session.add(MatchReview(product_ref="offer:1", status="pending"))
    db_session.commit()

    assert emit_daily_digest(db_session, now=NOW) is True
    # une seule alerte digest INFO.
    alerts = db_session.scalars(select(Alert).where(Alert.alert_type == "health")).all()
    assert len(alerts) == 1 and alerts[0].severity == "info"
    assert alerts[0].payload["quarantined_24h"] == 1
    assert alerts[0].payload["match_review_pending"] == 1
    # ré-appel le même jour → pas de second digest.
    assert emit_daily_digest(db_session, now=NOW) is False
    assert db_session.scalar(select(func.count()).select_from(Alert)) == 1
