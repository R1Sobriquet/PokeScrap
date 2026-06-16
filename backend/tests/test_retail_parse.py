"""Tests parsing PokéStock FR : JSON-LD prioritaire, fallback DOM, sitemap, politesse."""

from __future__ import annotations

from decimal import Decimal

from app.retail.domain import IN_STOCK, OUT_OF_STOCK, PREORDER, UNKNOWN
from app.retail.parse import parse_dom_offer, parse_jsonld_offer, parse_offer
from app.retail.politeness import RequestBudget, jittered_delay_s, robots_allows
from app.retail.sitemap import filter_product_skus, looks_like_product, parse_sitemap

JSONLD_IN_STOCK = """<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Coffret Dresseur Pokémon","sku":"ETB-1",
 "offers":{"@type":"Offer","price":"59,99","priceCurrency":"EUR","availability":"https://schema.org/InStock"}}
</script></head><body>x</body></html>"""

JSONLD_GRAPH_OOS = """<script type="application/ld+json">
{"@graph":[{"@type":"BreadcrumbList"},
{"@type":["Product"],"name":"Display EV08","offers":[{"@type":"Offer","price":129.9,"availability":"OutOfStock"}]}]}
</script>"""


def test_jsonld_in_stock_priority():
    o = parse_offer(JSONLD_IN_STOCK, "http://x/p")
    assert o.source == "jsonld"
    assert o.stock_state == IN_STOCK
    assert o.price == Decimal("59.99")
    assert o.currency == "EUR"
    assert o.retailer_sku == "ETB-1"


def test_jsonld_graph_out_of_stock():
    o = parse_jsonld_offer(JSONLD_GRAPH_OOS, "http://x/d")
    assert o is not None and o.stock_state == OUT_OF_STOCK and o.price == Decimal("129.9")


def test_dom_fallback_when_no_jsonld():
    html = '<html><head><meta itemprop="price" content="24.50"><title>Booster</title></head>' \
           "<body>Produit en rupture de stock</body></html>"
    o = parse_offer(html, "http://x/b")
    assert o.source == "dom"
    assert o.stock_state == OUT_OF_STOCK
    assert o.price == Decimal("24.50")
    assert o.title == "Booster"


def test_dom_preorder_detection():
    assert parse_dom_offer("<html><body>Disponible en précommande</body></html>", "u").stock_state == PREORDER


def test_jsonld_absent_returns_none():
    assert parse_jsonld_offer("<html><body>no ld</body></html>", "u") is None


def test_sitemap_urlset_filters_products():
    xml = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.cultura.com/p/coffret-pokemon-ev08.html</loc><lastmod>2026-06-01</lastmod></url>
    <url><loc>https://www.cultura.com/aide/contact</loc></url>
    <url><loc>https://www.cultura.com/p/livre-cuisine.html</loc></url></urlset>"""
    kind, entries = parse_sitemap(xml)
    assert kind == "urlset" and len(entries) == 3
    prod = filter_product_skus(entries)
    assert len(prod) == 1 and "pokemon" in prod[0].url and prod[0].lastmod == "2026-06-01"


def test_sitemapindex_parsed():
    xml = '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' \
          "<sitemap><loc>https://x/sitemap-pokemon.xml</loc></sitemap></sitemapindex>"
    kind, entries = parse_sitemap(xml)
    assert kind == "sitemapindex" and entries[0].url.endswith("sitemap-pokemon.xml")


def test_looks_like_product_excludes_categories():
    assert looks_like_product("https://x/p/etb-pokemon.html")
    assert not looks_like_product("https://x/category/pokemon")


def test_robots_and_budget():
    assert robots_allows("User-agent: *\nDisallow: /private/", "https://x/p/item") is True
    assert robots_allows("User-agent: *\nDisallow: /", "https://x/p/item") is False
    assert robots_allows(None, "https://x/p") is True
    b = RequestBudget(2)
    assert b.allow() and b.allow() and not b.allow()
    assert jittered_delay_s(0) == 0.0
    assert 3.0 <= jittered_delay_s(3000) <= 3000  # min + jitter
