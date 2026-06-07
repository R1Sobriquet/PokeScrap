"""Tests d'intégration du sourcing : dédup, pipeline, rétention, dégradation."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from app.adapters.ports import SourcingProvider
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
from app.scraping.models import RawListing, ScraperBlocked
from app.services import scrape_state
from app.services.sourcing import build_queries, purge_old_sourcing, scrape_sourcing

NOW = dt.datetime(2026, 6, 5, 12, 0, 0)

SETTINGS = {
    "valuation_market": ("US", "string"), "valuation_marketplace": ("tcgplayer", "string"),
    "fx_usd_eur": ("0.92", "decimal"), "fifty_rule_threshold_pct": ("50", "decimal"),
    "ir_min_discount_pct": ("30", "decimal"), "min_match_confidence": ("0.70", "decimal"),
    "default_sell_platform": ("cardmarket", "string"), "bulk_value_per_card": ("0.05", "decimal"),
    "fee_rate_cardmarket": ("5.0", "decimal"), "fee_rate_ebay": ("12.0", "decimal"),
    "fee_rate_vinted": ("0.0", "decimal"), "lot_confidence_haircut": ("0.85", "decimal"),
    "ir_lot_value_share": ("50", "decimal"), "pump_rise_pct": ("40", "decimal"),
    "min_sale_count": ("5", "int"), "illiquid_approx_multiplier": ("2", "int"),
    "fomo_freeze": ("false", "bool"), "fomo_scope": ("global", "string"),
    "fomo_trends_enabled": ("false", "bool"), "cash_min_below_150_pct": ("15", "decimal"),
    "w_margin": ("0.5", "decimal"), "w_liquidity": ("0.3", "decimal"), "w_tier": ("0.2", "decimal"),
    "scrape_max_listings_per_run": ("40", "int"), "scrape_blocked_cooldown_min": ("120", "int"),
    "bulk_lot_target_size": ("30", "int"), "sourcing_retention_days": ("90", "int"),
    "saved_queries": ('["lot pokemon"]', "json"),
    "sourcing_scraping_enabled": ("true", "bool"),  # tests pipeline : on active explicitement
    "scrape_max_queries_per_run": ("5", "int"),
}

TIERS = [(1, "T1", 150, 300, 10), (2, "T2", 300, 1000, 10),
         (3, "T3", 1000, 2500, 5), (4, "T4", 2500, 5000, 5)]


class FakeScraper(SourcingProvider):
    platform = "vinted"

    def __init__(self, listings=None, exc=None):
        self._listings = listings or []
        self._exc = exc
        self.calls = 0

    def scrape(self, query: str):
        self.calls += 1
        if self._exc:
            raise self._exc
        return list(self._listings)


def _seed(db):
    for key, (val, vt) in SETTINGS.items():
        db.add(Setting(setting_key=key, setting_value=val, value_type=vt))
    for num, name, cmin, cmax, cash in TIERS:
        db.add(TierConfig(tier_number=num, name=name, capital_min=cmin, capital_max=cmax, cash_min_pct=cash))
    db.add(Transaction(tx_type="adjustment", quantity=1, gross_amount=500, net_amount=500,
                       currency="EUR", occurred_at=NOW))
    p = Product(product_type="single", name="Charizard ex", set_name="Obsidian Flames",
                set_slug="obsidian-flames", card_number="125", language="EN", poketrace_id="pt-1")
    db.add(p)
    db.commit()
    db.add(PriceSnapshot(product_id=p.id, source="poketrace", market="US", marketplace="tcgplayer",
                         grade_company="RAW", condition_code="NM", currency="USD", price_avg=100,
                         avg_7d=160, avg_30d=155, sale_count=89, approx_sale_count=0, captured_at=NOW))
    db.add(Watchlist(product_id=p.id, tier="S++", keywords="charizard|dracaufeu", priority_coef=1, is_active=1))
    db.commit()
    invalidate_setting()
    return p


def _listing(price=30.0):
    return RawListing(platform="vinted", external_id="111", url="https://v.test/items/111",
                      raw_title="Charizard ex Obsidian Flames 125", asking_price=price,
                      shipping_cost=2.0, location="Paris")


def test_pipeline_inserts_matches_and_evaluates(db_session):
    db = db_session
    _seed(db)
    provider = FakeScraper([_listing()])

    stats = scrape_sourcing(db, [provider], now=NOW)

    assert stats["new"] == 1
    listing = db.scalar(select(SourcingListing))
    assert listing.status == "flagged"
    assert listing.detected_products  # matching a renseigné des produits
    assert listing.detected_products[0]["confidence"] == 0.95
    assert db.scalar(select(Alert).where(Alert.alert_type == "buy")) is not None


def test_dedup_no_double_insert_or_reeval(db_session):
    db = db_session
    _seed(db)
    provider = FakeScraper([_listing()])

    scrape_sourcing(db, [provider], now=NOW)
    stats2 = scrape_sourcing(db, [provider], now=NOW)  # même annonce

    assert stats2["new"] == 0
    assert stats2["duplicates"] >= 1
    assert db.scalar(select(func.count()).select_from(SourcingListing)) == 1
    assert db.scalar(select(func.count()).select_from(Alert).where(Alert.alert_type == "buy")) == 1


def test_degradation_provider_exception_isolated(db_session):
    db = db_session
    _seed(db)
    provider = FakeScraper(exc=RuntimeError("boom"))

    # Ne doit pas lever : la panne est isolée + tech_error émis.
    stats = scrape_sourcing(db, [provider], now=NOW)
    assert stats["errors"] >= 1
    assert db.scalar(select(Alert).where(Alert.alert_type == "tech_error")) is not None
    assert db.scalar(select(func.count()).select_from(SourcingListing)) == 0


def test_block_records_backoff_and_alerts(db_session):
    db = db_session
    _seed(db)
    provider = FakeScraper(exc=ScraperBlocked("datadome"))

    stats = scrape_sourcing(db, [provider], now=NOW)
    assert "vinted" in stats["blocked"]
    assert scrape_state.is_blocked(db, "vinted", NOW) is True
    assert db.scalar(select(Alert).where(Alert.alert_type == "tech_error")) is not None


def test_retention_purges_old_dismissed(db_session):
    db = db_session
    _seed(db)
    old = SourcingListing(platform="vinted", external_id="old", url="u", raw_title="vieux",
                          asking_price=1, status="dismissed", detected_at=NOW - dt.timedelta(days=200))
    recent = SourcingListing(platform="vinted", external_id="recent", url="u", raw_title="récent",
                             asking_price=1, status="dismissed", detected_at=NOW - dt.timedelta(days=10))
    db.add_all([old, recent])
    db.commit()

    purged = purge_old_sourcing(db, now=NOW)
    assert purged == 1
    remaining = db.scalars(select(SourcingListing.external_id)).all()
    assert "recent" in remaining and "old" not in remaining


def test_build_queries_from_saved_and_watchlist(db_session):
    db = db_session
    _seed(db)
    queries = build_queries(db)
    assert "lot pokemon" in queries
    assert any("Charizard ex" in q for q in queries)


def test_scraping_disabled_by_default(db_session):
    # Sans sourcing_scraping_enabled (défaut false) : le run est ignoré proprement,
    # le provider n'est jamais appelé. Le sourcing manuel reste géré ailleurs.
    db = db_session
    provider = FakeScraper([_listing()])
    stats = scrape_sourcing(db, [provider], now=NOW)
    assert stats["status"] == "disabled"
    assert provider.calls == 0
    assert db.scalar(select(func.count()).select_from(SourcingListing)) == 0
