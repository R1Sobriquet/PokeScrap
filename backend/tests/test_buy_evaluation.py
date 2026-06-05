"""Tests d'orchestration : evaluate_listing → statut + alertes (avec DB SQLite)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import func, select

from app.config import invalidate_setting
from app.models import (
    Alert,
    PriceSnapshot,
    Product,
    Setting,
    SourcingListing,
    TierConfig,
    Transaction,
    Watchlist,
)
from app.services.buy_evaluation import evaluate_listing

NOW = dt.datetime(2026, 6, 5, 12, 0, 0)

SETTINGS = {
    "valuation_market": ("US", "string"),
    "valuation_marketplace": ("tcgplayer", "string"),
    "fx_usd_eur": ("0.92", "decimal"),
    "fifty_rule_threshold_pct": ("50", "decimal"),
    "ir_min_discount_pct": ("30", "decimal"),
    "min_match_confidence": ("0.70", "decimal"),
    "default_sell_platform": ("cardmarket", "string"),
    "bulk_value_per_card": ("0.05", "decimal"),
    "fee_rate_cardmarket": ("5.0", "decimal"),
    "fee_rate_ebay": ("12.0", "decimal"),
    "fee_rate_vinted": ("0.0", "decimal"),
    "lot_confidence_haircut": ("0.85", "decimal"),
    "ir_lot_value_share": ("50", "decimal"),
    "pump_rise_pct": ("40", "decimal"),
    "min_sale_count": ("5", "int"),
    "illiquid_approx_multiplier": ("2", "int"),
    "fomo_freeze": ("false", "bool"),
    "fomo_scope": ("global", "string"),
    "fomo_trends_enabled": ("false", "bool"),
    "cash_min_below_150_pct": ("15", "decimal"),
    "w_margin": ("0.5", "decimal"),
    "w_liquidity": ("0.3", "decimal"),
    "w_tier": ("0.2", "decimal"),
}

TIERS = [
    (1, "Étape 1", 150, 300, 10),
    (2, "Étape 2", 300, 1000, 10),
    (3, "Étape 3", 1000, 2500, 5),
    (4, "Étape 4", 2500, 5000, 5),
]


@pytest.fixture()
def engine_ready(db_session):
    for key, (value, vtype) in SETTINGS.items():
        db_session.add(Setting(setting_key=key, setting_value=value, value_type=vtype))
    for num, name, cmin, cmax, cash in TIERS:
        db_session.add(
            TierConfig(tier_number=num, name=name, capital_min=cmin, capital_max=cmax, cash_min_pct=cash)
        )
    # Capital amorcé : 500€ → palier 2, plancher cash 10% = 50€.
    db_session.add(
        Transaction(tx_type="adjustment", quantity=1, gross_amount=500, net_amount=500,
                    currency="EUR", occurred_at=NOW)
    )
    db_session.commit()
    invalidate_setting()
    return db_session


def _product(db, name, *, avg, avg7d, avg30d, sale_count, approx, is_ir=False,
             tier="B", is_trinity=False):
    p = Product(product_type="single", name=name, language="EN",
                set_name="Test Set", poketrace_id=f"pt-{name}")
    db.add(p)
    db.commit()
    db.add(
        PriceSnapshot(
            product_id=p.id, source="poketrace", market="US", marketplace="tcgplayer",
            grade_company="RAW", condition_code="NM", currency="USD",
            price_avg=avg, avg_7d=avg7d, avg_30d=avg30d,
            sale_count=sale_count, approx_sale_count=1 if approx else 0, captured_at=NOW,
        )
    )
    db.add(
        Watchlist(product_id=p.id, tier=tier, is_illustration_rare=1 if is_ir else 0,
                  is_trinity=1 if is_trinity else 0, priority_coef=1)
    )
    db.commit()
    return p.id


def _listing(db, *, asking, detected, total_cards=1, ship=0, prot=0):
    listing = SourcingListing(
        platform="vinted", url="https://example.test/x", raw_title="Test listing",
        asking_price=asking, shipping_cost=ship, protection_cost=prot, currency="EUR",
        estimated_total_cards=total_cards, detected_products=detected, status="new",
        detected_at=NOW,
    )
    db.add(listing)
    db.commit()
    return listing.id


def _alert_count(db) -> int:
    return db.scalar(select(func.count()).select_from(Alert).where(Alert.alert_type == "buy"))


def test_listing_flagged_creates_pending_alert(engine_ready):
    db = engine_ready
    pid = _product(db, "Charizard", avg=100, avg7d=160, avg30d=155, sale_count=89,
                   approx=False, tier="S++", is_trinity=True)
    lid = _listing(db, asking=30, ship=2, prot=1,
                   detected=[{"product_id": pid, "qty": 1, "confidence": 0.95}])

    result = evaluate_listing(db, lid)

    assert result["status"] == "flagged"
    listing = db.get(SourcingListing, lid)
    assert listing.status == "flagged"
    assert listing.passes_50_rule == 1
    assert listing.ratio_pct is not None
    alerts = db.scalars(select(Alert).where(Alert.alert_type == "buy")).all()
    assert len(alerts) == 1
    assert alerts[0].status == "pending"
    assert alerts[0].payload["is_trinity"] is True
    assert alerts[0].sourcing_listing_id == lid


def test_listing_blocked_by_ratio_no_alert(engine_ready):
    db = engine_ready
    pid = _product(db, "Charizard", avg=100, avg7d=160, avg30d=155, sale_count=89, approx=False)
    lid = _listing(db, asking=150, ship=5, prot=2,
                   detected=[{"product_id": pid, "qty": 1, "confidence": 0.95}])

    result = evaluate_listing(db, lid)

    assert result["status"] == "blocked"
    assert db.get(SourcingListing, lid).status == "blocked"
    assert db.get(SourcingListing, lid).passes_50_rule == 0
    assert _alert_count(db) == 0


def test_listing_blocked_by_filter_sets_flags_no_alert(engine_ready):
    db = engine_ready
    # sale_count=2 < min_sale_count=5 → illiquide ; prix d'achat bas (ratio OK).
    pid = _product(db, "Illiquid", avg=100, avg7d=160, avg30d=155, sale_count=2, approx=False)
    lid = _listing(db, asking=20, ship=1, prot=0,
                   detected=[{"product_id": pid, "qty": 1, "confidence": 0.95}])

    result = evaluate_listing(db, lid)

    assert result["status"] == "blocked"
    listing = db.get(SourcingListing, lid)
    assert listing.filter_flags["illiquid"] is True
    assert _alert_count(db) == 0


def test_ir_lot_hard_block_no_alert(engine_ready):
    db = engine_ready
    pid = _product(db, "Umbreon", avg=100, avg7d=160, avg30d=155, sale_count=89,
                   approx=False, is_ir=True, tier="S++")
    # ratio > 70 % sur un lot IR → garde-fou absolu.
    lid = _listing(db, asking=60, ship=2, prot=1,
                   detected=[{"product_id": pid, "qty": 1, "confidence": 0.95}])

    result = evaluate_listing(db, lid)

    assert result["status"] == "blocked"
    assert db.get(SourcingListing, lid).filter_flags["buy_reason"] == "ir_absolute_floor"
    assert _alert_count(db) == 0


def test_blocked_by_cash_floor_no_alert(db_session):
    # Capital quasi nul → le plancher cash bloque même une bonne affaire.
    db = db_session
    for key, (value, vtype) in SETTINGS.items():
        db.add(Setting(setting_key=key, setting_value=value, value_type=vtype))
    for num, name, cmin, cmax, cash in TIERS:
        db.add(TierConfig(tier_number=num, name=name, capital_min=cmin, capital_max=cmax, cash_min_pct=cash))
    db.add(Transaction(tx_type="adjustment", quantity=1, gross_amount=20, net_amount=20,
                       currency="EUR", occurred_at=NOW))  # 20€ seulement
    db.commit()
    invalidate_setting()

    pid = _product(db, "Charizard", avg=100, avg7d=160, avg30d=155, sale_count=89, approx=False)
    lid = _listing(db, asking=30, ship=2, prot=1,
                   detected=[{"product_id": pid, "qty": 1, "confidence": 0.95}])

    result = evaluate_listing(db, lid)

    assert result["status"] == "blocked"
    assert result["filter_flags"]["cash_block"] is True
    assert _alert_count(db) == 0
