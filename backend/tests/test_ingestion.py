"""Tests d'ingestion : mode-aware, cache TTL, écriture price_snapshots."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from app.models import PriceSnapshot, Product
from app.services.ingestion import ingest_prices
from tests.conftest import insert_setting
from tests.fakes import FakePriceProvider


def _seed_free_mode(db):
    insert_setting(db, "valuation_market", "US", "string")
    insert_setting(db, "feature_grading_enabled", "false", "bool")
    insert_setting(db, "price_cache_ttl_min", "360", "int")


def _make_product(db, poketrace_id="uuid-charizard") -> int:
    p = Product(
        product_type="single", name="Charizard ex", language="EN", poketrace_id=poketrace_id
    )
    db.add(p)
    db.commit()
    return p.id


def test_free_mode_writes_raw_only(db_session):
    _seed_free_mode(db_session)
    pid = _make_product(db_session)
    provider = FakePriceProvider()

    written = ingest_prices(db_session, [pid], provider=provider)

    # Tiers bruts seulement, ventilés par marketplace : tcgplayer{NM,LP} + ebay{NM}.
    assert written == 3
    rows = db_session.scalars(select(PriceSnapshot)).all()
    assert len(rows) == 3
    assert {r.condition_code for r in rows} == {"NM", "LP"}
    assert {r.marketplace for r in rows} == {"tcgplayer", "ebay"}
    assert all(r.grade_company == "RAW" for r in rows)
    assert all(r.market == "US" and r.currency == "USD" for r in rows)
    assert all(r.source == "poketrace" for r in rows)
    # Aucun appel gradé/EU/history en mode Free.
    assert provider.get_card_calls == [("uuid-charizard", "US")]
    assert provider.history_calls == []


def test_field_mapping(db_session):
    _seed_free_mode(db_session)
    pid = _make_product(db_session)
    ingest_prices(db_session, [pid], provider=FakePriceProvider())

    nm = db_session.scalar(
        select(PriceSnapshot).where(
            PriceSnapshot.condition_code == "NM",
            PriceSnapshot.marketplace == "tcgplayer",
        )
    )
    assert float(nm.price_avg) == 165
    assert float(nm.price_low) == 140
    assert float(nm.price_high) == 195
    assert float(nm.avg_1d) == 162
    assert float(nm.avg_7d) == 160
    assert float(nm.avg_30d) == 155
    assert nm.sale_count == 89
    assert nm.approx_sale_count == 0

    lp = db_session.scalar(
        select(PriceSnapshot).where(PriceSnapshot.condition_code == "LP")
    )
    assert lp.approx_sale_count == 1  # approxSaleCount True (tcgplayer LP)


def test_grading_enabled_includes_graded(db_session):
    insert_setting(db_session, "valuation_market", "US", "string")
    insert_setting(db_session, "feature_grading_enabled", "true", "bool")
    insert_setting(db_session, "price_cache_ttl_min", "360", "int")
    pid = _make_product(db_session)

    written = ingest_prices(db_session, [pid], provider=FakePriceProvider())

    # tcgplayer{NM,LP,PSA_10} + ebay{NM,PSA_10} = 5 lignes.
    assert written == 5
    psa = db_session.scalar(
        select(PriceSnapshot).where(
            PriceSnapshot.grade_company == "PSA",
            PriceSnapshot.marketplace == "tcgplayer",
        )
    )
    assert psa.grade == "10"
    assert psa.condition_code is None


def test_cache_ttl_skips_recent(db_session):
    _seed_free_mode(db_session)
    pid = _make_product(db_session)
    now = dt.datetime(2026, 6, 5, 12, 0, 0)

    # Snapshot frais (il y a 1h) → l'ingestion doit servir le cache.
    db_session.add(
        PriceSnapshot(
            product_id=pid, source="poketrace", market="US", grade_company="RAW",
            condition_code="NM", currency="USD",
            captured_at=now - dt.timedelta(hours=1),
        )
    )
    db_session.commit()

    provider = FakePriceProvider()
    written = ingest_prices(db_session, [pid], provider=provider, now=now)

    assert written == 0
    assert provider.get_card_calls == []  # aucun appel : cache respecté


def test_cache_ttl_refetches_when_stale(db_session):
    _seed_free_mode(db_session)
    pid = _make_product(db_session)
    now = dt.datetime(2026, 6, 5, 12, 0, 0)

    # Snapshot vieux de 7h > TTL 6h → on re-requête.
    db_session.add(
        PriceSnapshot(
            product_id=pid, source="poketrace", market="US", grade_company="RAW",
            condition_code="NM", currency="USD",
            captured_at=now - dt.timedelta(hours=7),
        )
    )
    db_session.commit()

    provider = FakePriceProvider()
    written = ingest_prices(db_session, [pid], provider=provider, now=now)

    assert written == 3
    assert provider.get_card_calls == [("uuid-charizard", "US")]
