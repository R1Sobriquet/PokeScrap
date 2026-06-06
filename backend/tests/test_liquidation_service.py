"""Tests services Module B : intake, segmentation, promotion."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.models import (
    Alert,
    Lot,
    LotItem,
    PriceSnapshot,
    Position,
    Product,
    SourcingListing,
)
from app.services.liquidation_service import intake_lot, promote_to_position, segment_lot
from tests.conftest import insert_setting

NOW = dt.datetime(2026, 6, 5, 12, 0, 0)


def _seg_settings(db):
    insert_setting(db, "valuation_market", "US", "string")
    insert_setting(db, "valuation_marketplace", "tcgplayer", "string")
    insert_setting(db, "fx_usd_eur", "0.92", "decimal")
    insert_setting(db, "default_sell_platform", "cardmarket", "string")
    insert_setting(db, "fee_rate_cardmarket", "5.0", "decimal")
    insert_setting(db, "fee_rate_ebay", "12.0", "decimal")
    insert_setting(db, "fee_rate_vinted", "0.0", "decimal")
    insert_setting(db, "individual_threshold", "5.0", "decimal")
    insert_setting(db, "individual_ebay_threshold", "50.0", "decimal")
    insert_setting(db, "bulk_theme_strategy", "set", "string")
    insert_setting(db, "bulk_min_theme_for_dedicated_lot", "50", "int")
    insert_setting(db, "bulk_lot_target_size", "75", "int")
    insert_setting(db, "bulk_lot_min_size", "50", "int")
    insert_setting(db, "bulk_lot_max_size", "100", "int")
    insert_setting(db, "bulk_lot_price_per_card", "0.10", "decimal")


def _product(db, name, *, avg=None, set_name="Obsidian Flames"):
    p = Product(product_type="single", name=name, set_name=set_name, set_slug="obsidian-flames",
                language="EN", poketrace_id=f"pt-{name}")
    db.add(p)
    db.commit()
    if avg is not None:
        db.add(PriceSnapshot(product_id=p.id, source="poketrace", market="US", marketplace="tcgplayer",
                             grade_company="RAW", condition_code="NM", currency="USD", price_avg=avg,
                             captured_at=NOW))
        db.commit()
    return p


def test_intake_prefills_from_detection(db_session):
    db = db_session
    insert_setting(db, "intake_prefill_from_detection", "true", "bool")
    listing = SourcingListing(platform="vinted", url="u", raw_title="lot", asking_price=50,
                              detected_products=[{"product_id": 1, "confidence": 0.95},
                                                 {"product_id": 2, "confidence": 0.8}],
                              status="bought", detected_at=NOW)
    db.add(listing)
    db.commit()
    lot = Lot(source_listing_id=listing.id, total_cost=50, currency="EUR", purchased_at=NOW, status="received")
    db.add(lot)
    db.commit()

    res = intake_lot(db, lot.id)
    assert res["items_prefilled"] == 2
    assert db.get(Lot, lot.id).status == "processing"
    assert len(db.scalars(select(LotItem).where(LotItem.lot_id == lot.id)).all()) == 2


def test_segment_routes_individual_and_bulk(db_session):
    db = db_session
    _seg_settings(db)
    p_indiv = _product(db, "Charizard", avg=100)  # net ~87€ → individuelle ebay (>=50)
    p_bulk = _product(db, "Common", avg=2)        # net ~1.6€ → vrac
    lot = Lot(total_cost=50, currency="EUR", purchased_at=NOW, status="processing")
    db.add(lot)
    db.commit()
    db.add_all([
        LotItem(lot_id=lot.id, product_id=p_indiv.id, quantity=1, status="pending"),
        LotItem(lot_id=lot.id, product_id=p_bulk.id, quantity=1, status="pending"),
    ])
    db.commit()

    res = segment_lot(db, lot.id)
    assert res["status"] == "ok"
    assert db.get(Lot, lot.id).status == "segmented"
    indiv = db.scalar(select(LotItem).where(LotItem.product_id == p_indiv.id))
    assert indiv.segmentation == "individual"
    assert indiv.target_platform == "ebay"
    assert float(indiv.estimated_unit_value) > 50
    bulk = db.scalar(select(LotItem).where(LotItem.product_id == p_bulk.id))
    assert bulk.segmentation == "bulk_theme"
    assert db.scalar(select(Alert).where(Alert.alert_type == "lot_summary")) is not None


def test_promote_to_position_prorata(db_session):
    db = db_session
    p1 = _product(db, "Charizard")
    p2 = _product(db, "Pikachu")
    lot = Lot(total_cost=100, currency="EUR", purchased_at=NOW, status="segmented")
    db.add(lot)
    db.commit()
    item1 = LotItem(lot_id=lot.id, product_id=p1.id, quantity=1, segmentation="individual",
                    estimated_unit_value=60, status="pending")
    item2 = LotItem(lot_id=lot.id, product_id=p2.id, quantity=1, segmentation="individual",
                    estimated_unit_value=40, status="pending")
    db.add_all([item1, item2])
    db.commit()

    res = promote_to_position(db, item1.id)
    assert res["status"] == "ok"
    assert res["avg_cost"] == 60.0  # 100 × (60 / 100)
    pos = db.scalar(select(Position).where(Position.product_id == p1.id))
    assert pos is not None and float(pos.avg_cost) == 60.0
    assert db.get(LotItem, item1.id) is None  # retiré de la liquidation
