"""Tests des adapters marché (HTTP injecté, zéro réseau)."""

from __future__ import annotations

from decimal import Decimal

from app.marketdata.domain import WatchItem
from app.marketdata.sources.ebay import EbayBrowseAdapter
from app.marketdata.sources.ppt import PokemonPriceTrackerAdapter
from app.marketdata.sources.tcgdex import TCGdexAdapter

ITEM = WatchItem(product_ref="42", name="Prismatic Evolutions ETB", product_type="etb",
                 set_name="Prismatic Evolutions")


def test_ppt_parses_usd_and_eur():
    def fake(url, *, headers=None, params=None):
        if url.endswith("/prices"):
            return 200, {"data": {"prices": {"tcgplayer": {"market": 92.5},
                                             "cardmarket": {"market": 84.0}}}}
        return 404, None
    q = PokemonPriceTrackerAdapter(api_key="k", http=fake).fetch_quotes([ITEM])
    by = {(x.market, x.currency): x.price for x in q}
    assert by[("us", "USD")] == Decimal("92.5")
    assert by[("eu", "EUR")] == Decimal("84.0")
    assert all(x.source == "ppt" and x.product_ref == "42" for x in q)


def test_ppt_releases():
    def fake(url, *, headers=None, params=None):
        return 200, {"data": [{"id": "sv8pt5", "name": "Prismatic Evolutions",
                               "releaseDate": "2025-01-17"}]}
    rels = PokemonPriceTrackerAdapter(api_key="k", http=fake).list_releases()
    assert rels and rels[0].set_id == "sv8pt5" and str(rels[0].release_date) == "2025-01-17"


def test_tcgdex_releases_and_catalog():
    sets = [{"id": "sv08", "name": "Évolutions Prismatiques", "releaseDate": "2025-01-17"},
            {"id": "bad"}]  # sans nom → ignoré

    def fake(url, *, headers=None, params=None):
        return 200, sets
    a = TCGdexAdapter(http=fake)
    rels = a.list_releases()
    assert len(rels) == 1 and rels[0].set_name == "Évolutions Prismatiques"
    cat = a.list_catalog()
    assert len(cat) == 1 and cat[0].canonical_id == "sv08" and cat[0].language == "fr"


def test_ebay_aggregates_only():
    def fake(url, *, headers=None, params=None):
        return 200, {"itemSummaries": [
            {"price": {"value": "70.00", "currency": "EUR"}},
            {"price": {"value": "80.00", "currency": "EUR"}},
            {"price": {"value": "90.00", "currency": "EUR"}},
        ]}
    a = EbayBrowseAdapter(client_id="c", client_secret="s", http=fake,
                          token_getter=lambda c, s: "tok")
    q = a.fetch_quotes([ITEM])
    assert len(q) == 1
    quote = q[0]
    assert quote.source == "ebay" and quote.market == "eu"
    assert quote.price == Decimal("80.0")  # médiane
    assert quote.extra == {"count": 3, "min": 70.0, "median": 80.0}  # agrégats seulement


def test_ebay_no_token_no_quotes():
    a = EbayBrowseAdapter(client_id="c", client_secret="s",
                          http=lambda *a, **k: (200, {}), token_getter=lambda c, s: None)
    assert a.fetch_quotes([ITEM]) == []
