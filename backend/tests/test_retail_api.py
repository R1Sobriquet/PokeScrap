"""Tests API PokéStock FR : retailers, offres (add-by-URL, toggle), releases."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth.security import hash_password
from app.config import get_settings
from app.main import app
from app.models import Release, RetailOffer, Retailer, Setting


@pytest.fixture()
def client(sqlite_engine, db_session):
    s = get_settings()
    db_session.add(Setting(setting_key="admin_password_hash",
                           setting_value=hash_password(s.admin_password), value_type="string"))
    db_session.add(Retailer(code="cultura", name="Cultura", is_active=1,
                            base_url="https://www.cultura.com",
                            sitemap_url="https://www.cultura.com/sitemap.xml"))
    db_session.commit()
    c = TestClient(app)
    tok = c.post("/auth/login", json={"username": s.admin_username,
                                      "password": s.admin_password}).json()["access_token"]
    c.headers.update({"Authorization": f"Bearer {tok}"})
    return c


def test_requires_auth():
    c = TestClient(app)
    assert c.get("/retail/retailers").status_code == 401


def test_list_retailers_exposes_circuit_state(client):
    r = client.get("/retail/retailers")
    assert r.status_code == 200
    row = r.json()[0]
    assert row["code"] == "cultura" and row["error_count"] == 0 and row["circuit_open"] is False


def test_add_offer_by_url_and_toggle(client, db_session):
    # URL Cultura → détaillant déduit par le host ; fetch immédiat échoue proprement (offline).
    r = client.post("/retail/offers", json={"url": "https://www.cultura.com/p/etb-pokemon.html"})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    offer = db_session.scalar(select(RetailOffer))
    assert offer.is_watched == 1

    r2 = client.put(f"/retail/offers/{offer.id}", json={"is_watched": False})
    assert r2.status_code == 200 and r2.json()["is_watched"] is False


def test_add_offer_unknown_retailer(client):
    r = client.post("/retail/offers", json={"url": "https://www.unknown-shop.com/p/x"})
    assert r.status_code == 400


def test_releases_crud(client, db_session):
    r = client.post("/releases", json={"product_name": "ETB Prismatic", "set_name": "PE",
                                       "release_date": "2026-09-01"})
    assert r.status_code == 200
    rid = r.json()["id"]
    assert client.get("/releases").json()[0]["product_name"] == "ETB Prismatic"
    assert client.put(f"/releases/{rid}", json={"product_name": "ETB Prismatic v2"}).status_code == 200
    assert client.delete(f"/releases/{rid}").status_code == 200
    assert db_session.scalar(select(func.count()).select_from(Release)) == 0


def test_release_bad_date(client):
    assert client.post("/releases", json={"product_name": "x", "release_date": "nope"}).status_code == 400
