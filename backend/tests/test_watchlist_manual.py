"""Tests : création de set (API), ajout manuel watchlist (survit au sync auto)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app.services.catalog_seed as catalog_seed
from app.auth.security import hash_password
from app.config import get_settings
from app.main import app
from app.models import Product, Setting, TrackedSet, Watchlist
from app.services.catalog_seed import add_manual_watchlist
from app.services.tracked_sets import sync_tracked_sets
from tests.fakes import FakePriceProvider

CARD = {
    "id": "u-umbreon", "name": "Umbreon ex", "productType": "single", "productFamily": "card",
    "set": {"slug": "sv-prismatic-evolutions", "name": "Prismatic Evolutions"},
    "cardNumber": "161",
    "prices": {"tcgplayer": {"NEAR_MINT": {"avg": 1400}}},
}


class _PagedFake:
    def search_page(self, query, *, market, limit=50, cursor=None):
        return {"items": [CARD], "next_cursor": None}


@pytest.fixture()
def client(sqlite_engine, db_session):
    s = get_settings()
    db_session.add(Setting(setting_key="admin_password_hash",
                           setting_value=hash_password(s.admin_password), value_type="string"))
    db_session.commit()
    c = TestClient(app)
    token = c.post("/auth/login", json={"username": s.admin_username,
                                        "password": s.admin_password}).json()["access_token"]
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


# --------------------------------------------------------------- tracked-sets
def test_create_tracked_set_via_api(client, db_session):
    r = client.post("/tracked-sets", json={"set_slug": "151", "name": "Pokémon 151",
                                           "min_value_eur": 5, "include_single": True,
                                           "include_sealed": True})
    assert r.status_code == 200
    assert db_session.scalar(select(TrackedSet).where(TrackedSet.set_slug == "151")) is not None


def test_create_tracked_set_validation(client):
    assert client.post("/tracked-sets", json={"set_slug": "  ", "name": "x"}).status_code == 400
    assert client.post("/tracked-sets", json={"set_slug": "a", "name": "x",
                                              "min_value_eur": -1}).status_code == 400


def test_delete_tracked_set(client, db_session):
    db_session.add(TrackedSet(set_slug="151", name="151", is_active=1, min_value_eur=5,
                              include_single=1, include_sealed=1))
    db_session.commit()
    ts_id = db_session.scalar(select(TrackedSet.id))
    assert client.delete(f"/tracked-sets/{ts_id}").status_code == 200
    assert db_session.scalar(select(func.count()).select_from(TrackedSet)) == 0


# --------------------------------------------------------- manual watchlist add
def test_manual_add_sets_source_manual(db_session):
    res = add_manual_watchlist(db_session, search="Umbreon",
                               provider=FakePriceProvider(search_hits=[CARD]), tier="S++")
    assert res["status"] == "ok"
    watch = db_session.scalar(select(Watchlist))
    assert watch.source == "manual"
    assert watch.tier == "S++"


def test_manual_add_survives_sync(db_session):
    # Ajout manuel...
    add_manual_watchlist(db_session, search="Umbreon",
                         provider=FakePriceProvider(search_hits=[CARD]), tier="S++",
                         is_trinity=True, keywords="moonbreon")
    # ...puis un sync auto du même set ne doit PAS l'écraser.
    db_session.add(TrackedSet(set_slug="prismatic-evolutions", name="Prismatic Evolutions",
                              is_active=1, min_value_eur=5, include_single=1, include_sealed=1))
    db_session.commit()
    sync_tracked_sets(db_session, provider=_PagedFake())

    watch = db_session.scalar(select(Watchlist))
    assert watch.source == "manual"          # inchangé
    assert watch.tier == "S++"               # non écrasé par 'auto'
    assert watch.keywords == "moonbreon"
    assert db_session.scalar(select(func.count()).select_from(Watchlist)) == 1


def test_manual_add_no_result_creates_nothing(db_session):
    res = add_manual_watchlist(db_session, search="Inexistant",
                               provider=FakePriceProvider(search_hits=[]))
    assert res["status"] == "not_found"
    assert "Aucun produit" in res["message"]
    assert db_session.scalar(select(func.count()).select_from(Product)) == 0


def test_manual_add_empty_string(db_session):
    res = add_manual_watchlist(db_session, search="   ")
    assert res["status"] == "empty_search"
    assert db_session.scalar(select(func.count()).select_from(Product)) == 0


# ------------------------------------------------------------- endpoint manual
def test_watchlist_add_endpoint_ok(client, db_session, monkeypatch):
    monkeypatch.setattr(catalog_seed, "PokeTracePriceProvider",
                        lambda: FakePriceProvider(search_hits=[CARD]))
    r = client.post("/watchlist", json={"search": "Umbreon", "tier": "S++"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert db_session.scalar(select(Watchlist)).source == "manual"


def test_watchlist_add_endpoint_no_result(client, db_session, monkeypatch):
    monkeypatch.setattr(catalog_seed, "PokeTracePriceProvider",
                        lambda: FakePriceProvider(search_hits=[]))
    r = client.post("/watchlist", json={"search": "Inexistant"})
    assert r.status_code == 404
    assert "Aucun produit" in r.json()["detail"]
    assert db_session.scalar(select(func.count()).select_from(Product)) == 0
