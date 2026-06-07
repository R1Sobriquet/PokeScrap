"""Tests des endpoints dashboard (auth, lecture, actions = services existants)."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.security import hash_password
from app.config import get_setting, get_settings
from app.main import app
from app.models import Alert, Lot, LotItem, Product, Setting, SourcingListing, TierConfig, Transaction
from app.services.tier_state import get_current_tier_number
from tests.conftest import insert_setting

NOW = dt.datetime(2026, 6, 5, 12, 0, 0)


@pytest.fixture()
def client(sqlite_engine, db_session):
    s = get_settings()
    db_session.add(Setting(setting_key="admin_password_hash",
                           setting_value=hash_password(s.admin_password), value_type="string"))
    db_session.commit()
    c = TestClient(app)
    token = c.post("/auth/login", json={"username": s.admin_username,
                                        "password": s.admin_password}).json()["access_token"]
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


def test_protected_without_token_401(sqlite_engine):
    assert TestClient(app).get("/cockpit").status_code == 401


def test_cockpit_returns_kpis(client, db_session):
    insert_setting(db_session, "valuation_market", "US", "string")
    insert_setting(db_session, "fx_usd_eur", "0.92", "decimal")
    insert_setting(db_session, "tax_provision_pct", "12.3", "decimal")
    insert_setting(db_session, "reinvest_lock_pct", "30", "decimal")
    insert_setting(db_session, "lock_only_positive_profit", "true", "bool")
    db_session.add(TierConfig(tier_number=1, name="T1", capital_min=150, capital_max=300, cash_min_pct=10))
    db_session.add(Transaction(tx_type="adjustment", quantity=1, gross_amount=200, net_amount=200,
                               currency="EUR", occurred_at=NOW))
    db_session.commit()

    body = client.get("/cockpit").json()
    assert body["kpis"]["cash_total"] == 200.0
    assert body["tier"]["current"] == 1
    assert "pending_alerts" in body


def test_settings_put_invalidates_cache(client, db_session):
    insert_setting(db_session, "fifty_rule_threshold_pct", "50", "decimal")
    assert get_setting("fifty_rule_threshold_pct") == 50

    r = client.put("/settings/fifty_rule_threshold_pct", json={"value": "40"})
    assert r.status_code == 200
    # cache invalidé → nouvelle lecture reflète la valeur mise à jour
    assert get_setting("fifty_rule_threshold_pct") == 40


def test_deposit_creates_transaction(client, db_session):
    r = client.post("/deposit", json={"amount": 150})
    assert r.status_code == 200
    assert db_session.scalar(select(Transaction).where(Transaction.tx_type == "adjustment")) is not None


def test_intake_segment_reuse_services(client, db_session):
    for k, v, t in [("valuation_market", "US", "string"), ("valuation_marketplace", "tcgplayer", "string"),
                    ("fx_usd_eur", "0.92", "decimal"), ("default_sell_platform", "cardmarket", "string"),
                    ("fee_rate_cardmarket", "5.0", "decimal"), ("fee_rate_ebay", "12.0", "decimal"),
                    ("fee_rate_vinted", "0.0", "decimal"), ("individual_threshold", "5.0", "decimal"),
                    ("individual_ebay_threshold", "50.0", "decimal"), ("intake_prefill_from_detection", "true", "bool"),
                    ("bulk_theme_strategy", "set", "string"), ("bulk_min_theme_for_dedicated_lot", "50", "int"),
                    ("bulk_lot_target_size", "75", "int"), ("bulk_lot_min_size", "50", "int"),
                    ("bulk_lot_max_size", "100", "int"), ("bulk_lot_price_per_card", "0.10", "decimal")]:
        insert_setting(db_session, k, v, t)
    p = Product(product_type="single", name="Charizard", set_name="OF", set_slug="of",
                language="EN", poketrace_id="pt-1")
    db_session.add(p)
    db_session.commit()
    listing = SourcingListing(platform="vinted", url="u", raw_title="lot", asking_price=50,
                              detected_products=[{"product_id": p.id, "confidence": 0.95}],
                              status="bought", detected_at=NOW)
    db_session.add(listing)
    db_session.commit()
    lot = Lot(source_listing_id=listing.id, total_cost=50, currency="EUR", purchased_at=NOW, status="received")
    db_session.add(lot)
    db_session.commit()

    assert client.post("/intake", json={"lot_id": lot.id}).json()["items_prefilled"] == 1
    seg = client.post(f"/lots/{lot.id}/segment").json()
    assert seg["status"] == "ok"
    item = db_session.scalar(select(LotItem).where(LotItem.lot_id == lot.id))
    promo = client.post(f"/lot-items/{item.id}/promote").json()
    assert promo["status"] == "ok"


def test_confirm_palier_reuses_service(client, db_session):
    db_session.add(Alert(alert_type="palier_up", severity="warning", status="pending",
                         title="promo", payload={"target_tier": 3}, created_at=NOW))
    db_session.commit()
    alert_id = db_session.scalar(select(Alert.id))
    r = client.post(f"/alerts/{alert_id}/confirm")
    assert r.json()["status"] == "ok"
    assert get_current_tier_number(db_session) == 3


def test_switch_pro_atomic(client, db_session):
    insert_setting(db_session, "valuation_market", "US", "string")
    insert_setting(db_session, "feature_grading_enabled", "false", "bool")
    insert_setting(db_session, "poketrace_plan", "free", "string")

    r = client.post("/settings/switch-pro", json={"to_pro": True})
    assert r.status_code == 200
    assert get_setting("valuation_market") == "EU"
    assert get_setting("feature_grading_enabled") is True
    assert get_setting("poketrace_plan") == "pro"


def test_export_csv(client, db_session):
    db_session.add(Transaction(tx_type="sell", quantity=1, gross_amount=100, platform_fees=5,
                               net_amount=95, cost_basis=40, currency="EUR", occurred_at=NOW))
    db_session.commit()
    r = client.get("/ledger/export.csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "tx_type" in r.text and "sell" in r.text
