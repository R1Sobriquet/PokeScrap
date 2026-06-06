"""Tests du matching mots-clés (pur)."""

from __future__ import annotations

from app.services.matching import (
    CONFIDENCE_KEYWORD,
    CONFIDENCE_NAME,
    CONFIDENCE_SET_NUMBER,
    MatchProduct,
    estimate_total_cards,
    match_listing,
)

PRODUCTS = [
    MatchProduct(1, name="Charizard ex", set_name="Obsidian Flames", set_slug="obsidian-flames",
                 card_number="125", keywords="charizard|dracaufeu"),
    MatchProduct(2, name="Umbreon ex", set_name="Prismatic Evolutions", card_number="161",
                 keywords="umbreon|noctali", is_illustration_rare=True),
]


def test_set_and_number_high_confidence():
    detected, _ = match_listing("Charizard ex Obsidian Flames 125 NM", PRODUCTS)
    assert detected[0]["product_id"] == 1
    assert detected[0]["confidence"] == CONFIDENCE_SET_NUMBER


def test_name_medium_confidence():
    detected, _ = match_listing("Belle carte Umbreon ex à vendre", PRODUCTS)
    top = next(d for d in detected if d["product_id"] == 2)
    assert top["confidence"] == CONFIDENCE_NAME
    assert top["is_illustration_rare"] is True


def test_keyword_low_confidence():
    detected, _ = match_listing("gros lot avec un dracaufeu dedans", PRODUCTS)
    assert detected[0]["product_id"] == 1
    assert detected[0]["confidence"] == CONFIDENCE_KEYWORD


def test_no_match():
    detected, _ = match_listing("lot de cartes magic the gathering", PRODUCTS)
    assert detected == []


def test_estimate_total_cards():
    assert estimate_total_cards("Lot de 200 cartes pokemon") == 200
    assert estimate_total_cards("Pokemon x50 cartes") == 50
    assert estimate_total_cards("Charizard ex unitaire") == 1
    assert estimate_total_cards("gros lot pokemon", default_lot=30) == 30


def test_accent_insensitive():
    detected, _ = match_listing("NOCTALI ex prismatic", PRODUCTS)
    assert any(d["product_id"] == 2 for d in detected)
