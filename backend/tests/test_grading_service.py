"""Tests services Module A : verify_slab, gating, scan, hook cert d'achat."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.models import Alert, GradingOpportunity, PriceSnapshot, Product, PsaCert, SourcingListing, Watchlist
from app.services.grading_service import run_grading_scan, verify_slab
from app.services.buy_evaluation import evaluate_listing
from tests.conftest import insert_setting
from tests.fakes import FakeCertProvider

NOW = dt.datetime(2026, 6, 5, 12, 0, 0)


def _cert_data(is_valid: bool, grade="10"):
    return {"grade": grade, "grade_label": "GEM MT 10", "is_valid": is_valid,
            "pop_data": {"10": 100}, "raw": {"CertNumber": "12345678"}}


def test_verify_slab_invalid_hard_block(db_session):
    provider = FakeCertProvider(_cert_data(False))
    res = verify_slab(db_session, "12345678", provider=provider)
    assert res["decision"] == "hard_block"
    assert res["reason"] == "cert_invalid"
    cert = db_session.scalar(select(PsaCert).where(PsaCert.cert_number == "12345678"))
    assert cert is not None and cert.is_valid == 0


def test_verify_slab_valid_warns(db_session):
    provider = FakeCertProvider(_cert_data(True))
    res = verify_slab(db_session, "12345678", provider=provider)
    assert res["decision"] == "warn"
    assert "inspection" in res["message"].lower()


def test_grading_scan_noop_in_free_mode(db_session):
    insert_setting(db_session, "feature_grading_enabled", "false", "bool")
    res = run_grading_scan(db_session)
    assert res["status"] == "skipped"


def _grading_settings(db):
    insert_setting(db, "feature_grading_enabled", "true", "bool")
    insert_setting(db, "valuation_market", "US", "string")
    insert_setting(db, "valuation_marketplace", "tcgplayer", "string")
    insert_setting(db, "fx_usd_eur", "0.92", "decimal")
    insert_setting(db, "fee_rate_ebay", "12.0", "decimal")
    insert_setting(db, "fee_rate_cardmarket", "5.0", "decimal")
    insert_setting(db, "fee_rate_vinted", "0.0", "decimal")
    insert_setting(db, "graded_route", "ebay", "string")
    insert_setting(db, "grading_psa_fee_eur", "80", "decimal")
    insert_setting(db, "grading_logistics_eur", "40", "decimal")
    insert_setting(db, "grading_min_card_value", "100", "decimal")
    insert_setting(db, "grading_min_uplift_eur", "50", "decimal")
    insert_setting(db, "grading_min_uplift_pct", "50", "decimal")
    insert_setting(db, "grade_prob_source", "default", "string")
    insert_setting(db, "grade_prob_default", '{"10":0.30,"9":0.45,"le8":0.25}', "json")


def _price(db, pid, *, grade_company, grade, condition, avg):
    db.add(PriceSnapshot(product_id=pid, source="poketrace", market="US", marketplace="tcgplayer",
                         grade_company=grade_company, grade=grade, condition_code=condition,
                         currency="USD", price_avg=avg, captured_at=NOW))
    db.commit()


def test_grading_scan_recommends_and_upserts(db_session):
    db = db_session
    _grading_settings(db)
    p = Product(product_type="single", name="Charizard", language="EN", poketrace_id="pt-1")
    db.add(p)
    db.commit()
    db.add(Watchlist(product_id=p.id, tier="S++", is_active=1, priority_coef=1))
    db.commit()
    _price(db, p.id, grade_company="RAW", grade=None, condition="NM", avg=300)
    _price(db, p.id, grade_company="PSA", grade="10", condition=None, avg=3000)
    _price(db, p.id, grade_company="PSA", grade="9", condition=None, avg=900)

    res = run_grading_scan(db, now=NOW)
    assert res["status"] == "ok"
    assert res["recommended"] == 1
    opp = db.scalar(select(GradingOpportunity).where(GradingOpportunity.product_id == p.id))
    assert opp is not None and opp.is_recommended == 1
    assert db.scalar(select(Alert).where(Alert.alert_type == "grading")) is not None


def test_buy_cert_hook_blocks_invalid(db_session):
    db = db_session
    listing = SourcingListing(platform="ebay", url="u", raw_title="Charizard slab PSA 12345678 GEM",
                              asking_price=200, detected_products=[], status="new", detected_at=NOW)
    db.add(listing)
    db.commit()

    result = evaluate_listing(db, listing.id, cert_provider=FakeCertProvider(_cert_data(False)))

    assert result["status"] == "blocked"
    assert result["reason"] == "cert_invalid"
    assert db.get(SourcingListing, listing.id).status == "blocked"
    # cert invalide → aucune alerte d'achat émise.
    assert db.scalar(select(Alert).where(Alert.alert_type == "buy")) is None
