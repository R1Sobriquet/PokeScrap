"""Tests d'authentification : bcrypt, JWT, /auth/login, /auth/me."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import get_settings
from app.main import app


def _seed_admin(engine, password):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO settings (setting_key, setting_value, value_type) "
                "VALUES ('admin_password_hash', :h, 'string')"
            ),
            {"h": hash_password(password)},
        )


def test_password_roundtrip():
    h = hash_password("s3cret!")
    assert verify_password("s3cret!", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token("erwann")
    assert decode_token(token)["sub"] == "erwann"


def test_login_ok(sqlite_engine):
    s = get_settings()
    _seed_admin(sqlite_engine, s.admin_password)
    client = TestClient(app)
    r = client.post(
        "/auth/login",
        json={"username": s.admin_username, "password": s.admin_password},
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_ko(sqlite_engine):
    s = get_settings()
    _seed_admin(sqlite_engine, s.admin_password)
    client = TestClient(app)
    r = client.post(
        "/auth/login",
        json={"username": s.admin_username, "password": "definitely-wrong"},
    )
    assert r.status_code == 401


def test_me_requires_token(sqlite_engine):
    client = TestClient(app)
    assert client.get("/auth/me").status_code == 401


def test_me_with_token(sqlite_engine):
    s = get_settings()
    _seed_admin(sqlite_engine, s.admin_password)
    client = TestClient(app)
    token = client.post(
        "/auth/login",
        json={"username": s.admin_username, "password": s.admin_password},
    ).json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == s.admin_username
