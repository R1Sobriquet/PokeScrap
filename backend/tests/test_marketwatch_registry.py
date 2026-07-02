"""Tests registre TCGdex (sync multilingue) + source Cardmarket fichier."""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal

from sqlalchemy import func, select

from app.marketwatch.registry import load_registry, sync_registry
from app.marketwatch.sources.cardmarket_file import CardmarketFileSource
from app.models import TcgdexCard

# --- Faux TCGdex : sets + détail par langue -------------------------------
_SETS = {
    "en": [{"id": "sv03.5", "name": "151"}],
    "fr": [{"id": "sv03.5", "name": "151"}],
}
_DETAIL = {
    ("en", "sv03.5"): {"name": "151", "cards": [
        {"id": "sv03.5-161", "localId": "161", "name": "Charizard ex", "rarity": "Double Rare"},
    ]},
    ("fr", "sv03.5"): {"name": "151", "cards": [
        {"id": "sv03.5-161", "localId": "161", "name": "Dracaufeu ex", "rarity": "Double Rare"},
    ]},
}


def _fake_http(url, *, headers=None, params=None):
    parts = url.rstrip("/").split("/")
    lang = parts[-2] if parts[-1] == "sets" else None
    if url.endswith("/sets"):
        lang = parts[-2]
        return 200, _SETS.get(lang, [])
    # .../{lang}/sets/{id}
    lang, sid = parts[-3], parts[-1]
    return 200, _DETAIL.get((lang, sid), {})


def test_sync_registry_merges_multilingual_names(db_session):
    res = sync_registry(db_session, http=_fake_http, langs=("en", "fr"))
    assert res["cards"] == 1
    card = db_session.get(TcgdexCard, "sv03.5-161")
    assert card.name_en == "Charizard ex"
    assert card.name_fr == "Dracaufeu ex"
    assert card.number == "161"
    assert card.pokemon == "Charizard"


def test_sync_registry_is_idempotent(db_session):
    sync_registry(db_session, http=_fake_http, langs=("en", "fr"))
    sync_registry(db_session, http=_fake_http, langs=("en", "fr"))
    assert db_session.scalar(select(func.count()).select_from(TcgdexCard)) == 1


def test_cardmarket_file_source_matches_and_emits(db_session):
    sync_registry(db_session, http=_fake_http, langs=("en", "fr"))
    registry = load_registry(db_session)

    products = {"createdAt": "2026-06-01", "products": [
        {"idProduct": 777, "name": "Charizard ex", "number": "161", "expansionName": "151"},
        {"idProduct": 888, "name": "Cardo Inexistant", "number": "999"},
    ]}
    guide = {"createdAt": "2026-06-01", "priceGuides": [
        {"idProduct": 777, "avg": 40.0, "low": 33.0, "trend": 42.5},
        {"idProduct": 888, "avg": 5.0, "trend": 5.0},
    ]}
    opener = lambda src: products if "products" in src else guide  # noqa: E731

    source = CardmarketFileSource.from_files("products.json", "guide.json", registry,
                                             language="EN", opener=opener)
    snaps = source.fetch()
    assert len(snaps) == 1
    s = snaps[0]
    assert s.card_id == "sv03.5-161"
    assert s.price_eur == Decimal("42.5")   # trend prioritaire sur avg
    assert s.trend_eur == Decimal("42.5")
    assert s.captured_at == dt.date(2026, 6, 1)
    assert len(source.unmatched) == 1       # le produit 888 est non rapproché
