"""Tests du parsing (fixtures HTML) + détection de casse — purs."""

from __future__ import annotations

import pathlib

from app.scraping.parser import parse_listings, parse_price

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

VINTED_SEL = {
    "container": "div.feed-grid__item",
    "title": "span.title",
    "price": "span.price",
    "shipping": "span.ship",
    "location": "span.loc",
    "link": "a.item-link",
    "base_url": "https://www.vinted.fr",
}

LBC_SEL = {
    "container": "article.ad",
    "title": "p.t",
    "price": "span.p",
    "location": "span.city",
    "link": "a.ad-link",
    "base_url": "https://www.leboncoin.fr",
}


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_price_formats():
    assert parse_price("40,00 €") == 40.0
    assert parse_price("1 234,56 €") == 1234.56
    assert parse_price("1.234,56") == 1234.56
    assert parse_price("12.50") == 12.5
    assert parse_price("") is None
    assert parse_price("gratuit") is None


def test_vinted_parsing_ok():
    res = parse_listings(_html("vinted_ok.html"), VINTED_SEL, platform="vinted", break_threshold=30)
    assert res.broken is False
    assert len(res.listings) == 2
    first = res.listings[0]
    assert first.raw_title == "Charizard ex Obsidian Flames 125"
    assert first.asking_price == 40.0
    assert first.shipping_cost == 2.5
    assert first.location == "Paris"
    assert first.external_id == "123456789"
    assert first.url == "https://www.vinted.fr/items/123456789-charizard-ex-obsidian"
    assert res.listings[1].shipping_cost == 0.0  # port absent → 0


def test_leboncoin_parsing_ok():
    res = parse_listings(_html("leboncoin_ok.html"), LBC_SEL, platform="leboncoin", break_threshold=30)
    assert res.broken is False
    assert len(res.listings) == 1
    assert res.listings[0].asking_price == 120.0
    assert res.listings[0].external_id == "123123123"


def test_break_detection_missing_fields():
    res = parse_listings(_html("vinted_broken.html"), VINTED_SEL, platform="vinted", break_threshold=30)
    assert res.broken is True
    assert res.listings == []
    assert "sélecteurs" in res.reason


def test_break_detection_no_container():
    res = parse_listings("<html><body></body></html>", VINTED_SEL, platform="vinted", break_threshold=30)
    assert res.broken is True
    assert "0 conteneur" in res.reason
