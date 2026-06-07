"""Tests : diagnostic de blocage + parsing Vinted avec les sélecteurs réels."""

from __future__ import annotations

import pathlib

from app.scraping.antibot import classify_block
from app.scraping.parser import parse_listings
from app.scraping.selectors import load_selectors

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SELECTORS_YAML = pathlib.Path(__file__).resolve().parents[2] / "scraper" / "selectors.yaml"


def test_classify_block_http_403():
    assert classify_block(403, "<html>ok</html>") == "http_403"


def test_classify_block_http_429():
    assert classify_block(429, "") == "http_429"


def test_classify_block_datadome():
    html = "<html><body>geo.captcha-delivery.com DataDome</body></html>"
    assert classify_block(200, html) == "datadome"


def test_classify_block_captcha():
    html = "<html><body><div class='g-recaptcha'></div>Are you a human</body></html>"
    assert classify_block(200, html) == "captcha"


def test_classify_block_clean_page():
    assert classify_block(200, "<html><body>résultats normaux</body></html>") is None


def test_vinted_results_parsed_with_real_selectors():
    """Les sélecteurs versionnés (selectors.yaml) extraient bien une page Vinted."""
    sel = load_selectors(str(SELECTORS_YAML))["vinted"]
    html = (FIXTURES / "vinted_results.html").read_text(encoding="utf-8")

    res = parse_listings(html, sel, platform="vinted", break_threshold=30)

    assert res.broken is False
    assert len(res.listings) == 2
    first = res.listings[0]
    assert first.raw_title == "Charizard ex Obsidian Flames 125"
    assert first.asking_price == 40.0
    assert first.external_id == "812345678"
    assert first.url == "https://www.vinted.fr/items/812345678-charizard-ex-obsidian"
    assert first.location == "France"
    assert res.listings[1].external_id == "912345678"
    assert res.listings[1].asking_price == 25.0
