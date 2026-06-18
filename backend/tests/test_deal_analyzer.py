"""Tests Deal Analyzer : verdict prix annoncé vs marché PokeTrace."""

from __future__ import annotations

from app.retail.domain import Retailer as RetailerDC
from app.retail.fetch import HttpRetailSource
from app.services.deal_analyzer import analyze_listing
from tests.fakes import FakePriceProvider

# Carte scellée : valeur marché via UNOPENED (card_value privilégie ce tier).
SEALED_CARD = {"name": "Evolving Skies Booster Box",
               "prices": {"tcgplayer": {"UNOPENED": {"avg": 100.0}}}}

PAGE = """<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Evolving Skies Booster Box",
 "offers":{"@type":"Offer","price":"%s","priceCurrency":"EUR","availability":"https://schema.org/InStock"}}
</script></head><body>x</body></html>"""


def _source(price: str):
    def fake_get(url, headers):
        return 200, PAGE % price, {}
    return HttpRetailSource(RetailerDC(code="x", name="x", base_url="https://x"), http_get=fake_get)


def _market_eur():
    # valuation_market défaut US → fx 0.92 ; UNOPENED 100 USD → 92 EUR.
    return 92.0


def test_strong_buy_when_well_below_market(db_session):
    # Annoncé 60 € vs marché 92 € → ~35% sous le marché → STRONG BUY.
    res = analyze_listing(db_session, "https://x/p/es-bb", provider=FakePriceProvider(search_hits=[SEALED_CARD]), source=_source("60"))
    assert res["status"] == "ok"
    assert res["listed_price"] == 60.0
    assert res["market_value_eur"] == _market_eur()
    assert res["discount_pct"] > 25
    assert res["verdict"] == "STRONG BUY"
    assert res["verdict_tone"] == "buy"


def test_overpriced_when_above_market(db_session):
    # Annoncé 140 € vs marché 92 € → bien au-dessus → OVERPRICED.
    res = analyze_listing(db_session, "https://x/p/es-bb", provider=FakePriceProvider(search_hits=[SEALED_CARD]), source=_source("140"))
    assert res["discount_pct"] < -25
    assert res["verdict"] == "OVERPRICED"
    assert res["verdict_tone"] == "pass"


def test_no_comp_when_no_market_match(db_session):
    res = analyze_listing(db_session, "https://x/p/es-bb", provider=FakePriceProvider(search_hits=[]), source=_source("60"))
    assert res["status"] == "ok"
    assert res["market_value_eur"] is None
    assert res["verdict"] == "NO COMP"


def test_invalid_url(db_session):
    assert analyze_listing(db_session, "not-a-url")["status"] == "invalid_url"


def test_no_price_on_page(db_session):
    page = "<html><body>aucune offre ici</body></html>"
    src = HttpRetailSource(RetailerDC(code="x", name="x", base_url="https://x"),
                           http_get=lambda u, h: (200, page, {}))
    res = analyze_listing(db_session, "https://x/p/none", provider=FakePriceProvider(search_hits=[SEALED_CARD]), source=src)
    assert res["status"] == "no_price"
