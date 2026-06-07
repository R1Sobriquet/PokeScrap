"""Tests du seeding catalogue : mapping des champs imbriqués PokeTrace."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import Product, Watchlist
from app.services.catalog_seed import seed_catalog, upsert_product
from tests.fakes import FakePriceProvider

# Forme réelle d'une carte PokeTrace : set/refs/image imbriqués.
REAL_CARD = {
    "id": "uuid-charizard",
    "name": "Charizard ex",
    "set": {"name": "Obsidian Flames", "slug": "obsidian-flames"},
    "cardNumber": "125",
    "variant": "holo",
    "rarity": "Double Rare",
    "language": "EN",
    "image": {"small": "s.png", "large": "l.png"},
    "refs": {"tcgplayerId": "517812", "cardmarketId": "700123"},
}


def test_upsert_product_maps_nested_fields(db_session):
    p = upsert_product(db_session, REAL_CARD, {"tier": "S++"})
    db_session.commit()  # ne doit pas lever de TypeError

    assert p.name == "Charizard ex"
    assert p.set_name == "Obsidian Flames"
    assert p.set_slug == "obsidian-flames"
    assert p.card_number == "125"
    assert p.variant == "holo"
    assert p.rarity == "Double Rare"
    assert p.language == "EN"
    assert p.cardmarket_id == "700123"
    assert p.tcgplayer_id == "517812"
    assert p.image_url == "l.png"  # image.large extrait
    # Aucune colonne ne contient un dict brut.
    for value in (p.set_name, p.set_slug, p.card_number, p.cardmarket_id,
                  p.tcgplayer_id, p.image_url, p.name, p.language):
        assert not isinstance(value, dict)


def test_upsert_product_set_as_string(db_session):
    card = {"id": "u2", "name": "Pikachu", "set": "Surging Sparks", "setSlug": "surging-sparks",
            "cardNumber": "238", "refs": {"tcgplayer": "999"}}
    p = upsert_product(db_session, card, {})
    db_session.commit()
    assert p.set_name == "Surging Sparks"
    assert p.set_slug == "surging-sparks"
    assert p.tcgplayer_id == "999"


def test_upsert_product_entry_overrides_win(db_session):
    entry = {"name": "Mon nom", "set": "Mon set", "card_number": "001", "language": "FR"}
    p = upsert_product(db_session, REAL_CARD, entry)
    db_session.commit()
    assert p.name == "Mon nom"
    assert p.set_name == "Mon set"
    assert p.card_number == "001"
    assert p.language == "FR"


def test_seed_catalog_inserts_with_nested_card(db_session):
    provider = FakePriceProvider(search_hits=[REAL_CARD])
    result = seed_catalog(
        db_session, [{"search": "Charizard ex", "tier": "S++", "keywords": "charizard"}],
        provider=provider,
    )
    assert result["products"] == 1 and result["watchlist"] == 1
    assert db_session.scalar(select(func.count()).select_from(Product)) == 1
    watch = db_session.scalar(select(Watchlist))
    assert watch.tier == "S++"
