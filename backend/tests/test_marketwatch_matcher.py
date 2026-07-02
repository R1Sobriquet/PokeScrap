"""Tests du matcher Cardmarket idProduct → card_id TCGdex (fonctions pures)."""

from __future__ import annotations

from app.marketwatch.domain import CardmarketProduct, RegistryCard
from app.marketwatch.matcher import (
    match_cardmarket,
    normalize_name,
    normalize_number,
)

REGISTRY = [
    RegistryCard(card_id="sv03.5-161", set_id="sv03.5", set_name="151", number="161",
                 name_en="Charizard ex", name_fr="Dracaufeu ex", name_jp="リザードンex"),
    RegistryCard(card_id="sv03.5-215", set_id="sv03.5", set_name="151", number="215",
                 name_en="Mewtwo", name_fr="Mewtwo"),
    RegistryCard(card_id="swsh7-215", set_id="swsh7", set_name="Evolving Skies", number="215",
                 name_en="Umbreon VMAX", name_fr="Noctali VMAX"),
]


def test_normalize_number_strips_slash_and_zeros():
    assert normalize_number("215/203") == "215"
    assert normalize_number("012") == "12"
    assert normalize_number("TG20/TG30") == "tg20"
    assert normalize_number(None) == ""


def test_normalize_name_drops_accents_and_parentheses():
    assert normalize_name("Dracaufeu ex (Reverse Holo)") == "dracaufeu ex"
    assert normalize_name("Noctali-VMAX!") == "noctali vmax"


def test_match_on_set_number_and_name():
    prod = CardmarketProduct(id_product="777", name="Charizard ex", number="161")
    m = match_cardmarket(prod, REGISTRY)
    assert m is not None
    assert m.card_id == "sv03.5-161"
    assert m.method == "set_number"
    assert m.confidence >= 0.80


def test_match_uses_french_names():
    # Nom FR + numéro → doit retrouver la carte via les noms multilingues.
    prod = CardmarketProduct(id_product="778", name="Noctali VMAX", number="215")
    m = match_cardmarket(prod, REGISTRY)
    assert m is not None and m.card_id == "swsh7-215"


def test_number_disambiguates_same_name_number_collision():
    # Numéro 215 existe dans deux sets ; le nom tranche.
    prod = CardmarketProduct(id_product="779", name="Mewtwo", number="215")
    m = match_cardmarket(prod, REGISTRY)
    assert m is not None and m.card_id == "sv03.5-215"


def test_variant_noise_does_not_break_match():
    prod = CardmarketProduct(id_product="780", name="Charizard ex (Reverse Holo)", number="161")
    m = match_cardmarket(prod, REGISTRY)
    assert m is not None and m.card_id == "sv03.5-161"


def test_unmatched_returns_none():
    prod = CardmarketProduct(id_product="781", name="Pikachu Illustrator", number="999")
    assert match_cardmarket(prod, REGISTRY) is None
