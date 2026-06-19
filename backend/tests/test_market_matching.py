"""Tests auto-matching produits + auto-calendrier."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from app.marketdata.domain import SetRelease
from app.marketdata.ports import MarketDataPort
from app.models import MatchReview, Product, Release, Retailer, RetailOffer
from app.services.calendar_sync import run_calendar_sync
from app.services.product_matching import normalize, run_match_products, similarity
from tests.conftest import insert_setting


def test_normalize_and_similarity():
    assert normalize("Pokémon — ÉVOLUTIONS Prismatiques!") == "evolutions prismatiques"
    assert similarity("ETB Prismatic Evolutions", "Prismatic Evolutions ETB") > 0.9


def _offer(db, title, retailer_id):
    o = RetailOffer(retailer_id=retailer_id, url=f"https://c/{title}".replace(" ", "-"),
                    title=title, current_stock_state="in_stock", is_watched=1)
    db.add(o)
    db.flush()
    return o


def test_match_auto_accepts_and_queues_review(db_session):
    insert_setting(db_session, "match_confidence_threshold", "0.82", "decimal")
    r = Retailer(code="cultura", name="Cultura", is_active=1)
    db_session.add(r)
    db_session.flush()
    # produit interne
    db_session.add(Product(product_type="sealed", name="Prismatic Evolutions ETB", language="EN"))
    db_session.add(Product(product_type="sealed", name="Crown Zenith ETB", language="EN"))
    db_session.commit()

    _offer(db_session, "Prismatic Evolutions ETB", r.id)   # match net → auto
    _offer(db_session, "Mystère Display 2030", r.id)        # rien de proche → no_candidate/review
    db_session.commit()

    res = run_match_products(db_session)
    assert res["auto"] >= 1
    linked = db_session.scalar(select(RetailOffer).where(RetailOffer.title == "Prismatic Evolutions ETB"))
    assert linked.product_id is not None


class _RelSource(MarketDataPort):
    code = "tcgdex"
    capabilities = frozenset({"releases"})

    def list_releases(self):
        return [SetRelease("sv08", "Évolutions Prismatiques", dt.date(2025, 1, 17))]


def test_calendar_sync_upserts_idempotent(db_session):
    insert_setting(db_session, "marketdata_enabled", "true", "bool")
    res = run_calendar_sync(db_session, sources={"tcgdex": _RelSource()})
    assert res["inserted"] == 1
    row = db_session.scalar(select(Release).where(Release.set_name == "Évolutions Prismatiques"))
    assert row is not None and str(row.release_date) == "2025-01-17"
    assert row.source_note.startswith("auto:")
    # re-run → pas de doublon (update).
    res2 = run_calendar_sync(db_session, sources={"tcgdex": _RelSource()})
    assert res2["updated"] == 1
    assert db_session.scalar(select(func.count()).select_from(Release)) == 1
