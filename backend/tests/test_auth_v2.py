"""Tests auth v2 : inscription, vérification, refresh rotatif, reset, rôles, 429."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.security import (
    create_access_token,
    ensure_admin_user,
    hash_password,
    issue_refresh,
    rotate_refresh,
)
from app.models import AuthSession, User
from app.main import app
from tests.conftest import insert_setting


def _make_user(db, username="sacha", email="sacha@kanto.fr", status="active") -> User:
    u = User(email=email, username=username, password_hash=hash_password("pikachu123"),
             status=status)
    db.add(u)
    db.commit()
    return u


def _extract_token(fake_sent: list) -> str:
    # le lien contient ?token=<raw>
    body = fake_sent[-1][2]
    return body.split("token=")[1].split()[0]


@pytest.fixture()
def client(sqlite_engine):
    return TestClient(app)


@pytest.fixture()
def fake_email(monkeypatch):
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr("app.api.auth.send_email",
                        lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


# ------------------------------------------------------------ inscription
def test_register_closed_by_default(client, db_session):
    r = client.post("/auth/register", json={
        "email": "a@b.fr", "username": "misty", "password": "starmie123"})
    assert r.status_code == 403  # signup_enabled=false par défaut


def test_register_verify_login_flow(client, db_session, fake_email):
    insert_setting(db_session, "signup_enabled", "true", "bool")
    r = client.post("/auth/register", json={
        "email": "Misty@Cerulean.fr", "username": "misty", "password": "starmie123"})
    assert r.status_code == 201
    user = db_session.scalar(select(User).where(User.username == "misty"))
    assert user.status == "pending"
    assert user.email == "misty@cerulean.fr"  # normalisé en minuscules

    # Login avant vérification → 403.
    r = client.post("/auth/login", json={"username": "misty", "password": "starmie123"})
    assert r.status_code == 403

    # Vérification par le jeton reçu « par email ».
    token = _extract_token(fake_email)
    assert client.post("/auth/verify", json={"token": token}).status_code == 200
    db_session.expire_all()
    assert db_session.scalar(select(User).where(User.username == "misty")).status == "active"

    # Login OK : access renvoyé + cookie refresh posé.
    r = client.post("/auth/login", json={"username": "misty", "password": "starmie123"})
    assert r.status_code == 200
    assert r.json()["access_token"]
    assert "pa_refresh" in r.cookies

    # Le jeton de vérification est à usage unique.
    assert client.post("/auth/verify", json={"token": token}).status_code == 400


def test_register_rejects_duplicates_and_bad_input(client, db_session):
    insert_setting(db_session, "signup_enabled", "true", "bool")
    _make_user(db_session)
    dup = client.post("/auth/register", json={
        "email": "sacha@kanto.fr", "username": "red", "password": "dracaufeu1"})
    assert dup.status_code == 409
    bad = client.post("/auth/register", json={
        "email": "pas-un-email", "username": "ok_name", "password": "12345678"})
    assert bad.status_code == 422


# ------------------------------------------------------- refresh rotatif
def test_refresh_rotation_and_reuse_detection(client, db_session):
    user = _make_user(db_session)
    raw1 = issue_refresh(db_session, user)

    client.cookies.set("pa_refresh", raw1)
    r = client.post("/auth/refresh")
    assert r.status_code == 200 and r.json()["access_token"]
    raw2 = r.cookies.get("pa_refresh")
    assert raw2 and raw2 != raw1  # rotation

    # Réutiliser raw1 (déjà tourné) = vol probable → toutes les sessions tombent.
    client.cookies.set("pa_refresh", raw1)
    assert client.post("/auth/refresh").status_code == 401
    client.cookies.set("pa_refresh", raw2)
    assert client.post("/auth/refresh").status_code == 401  # famille révoquée


def test_logout_revokes_session(client, db_session):
    user = _make_user(db_session)
    raw = issue_refresh(db_session, user)
    client.cookies.set("pa_refresh", raw)
    assert client.post("/auth/logout").status_code == 200
    assert rotate_refresh(db_session, raw) is None


# ------------------------------------------------------------- mot de passe
def test_forgot_and_reset_flow(client, db_session, fake_email):
    user = _make_user(db_session)
    issue_refresh(db_session, user)  # session active à révoquer

    # Anti-énumération : toujours 200, email envoyé seulement si le compte existe.
    assert client.post("/auth/forgot", json={"email": "inconnu@x.fr"}).status_code == 200
    assert len(fake_email) == 0
    assert client.post("/auth/forgot", json={"email": "sacha@kanto.fr"}).status_code == 200
    token = _extract_token(fake_email)

    r = client.post("/auth/reset", json={"token": token, "password": "nouveaumdp1"})
    assert r.status_code == 200
    # Nouveau mot de passe actif + anciennes sessions révoquées.
    assert client.post("/auth/login", json={
        "username": "sacha", "password": "nouveaumdp1"}).status_code == 200
    open_sessions = db_session.scalars(select(AuthSession).where(
        AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))).all()
    assert len(open_sessions) == 1  # seulement celle du login ci-dessus


# ------------------------------------------------------------------ rôles
def test_require_admin_forbids_regular_user(client, db_session):
    user = _make_user(db_session)
    headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
    assert client.get("/admin/jobs/recent", headers=headers).status_code == 403
    # L'admin passe (créé à la volée depuis .env + hash seedé).
    insert_setting(db_session, "admin_password_hash", hash_password("change_me"))
    admin = ensure_admin_user(db_session)
    headers = {"Authorization": f"Bearer {create_access_token(str(admin.id))}"}
    assert client.get("/admin/jobs/recent", headers=headers).status_code == 200


def test_me_returns_role_and_plan(client, db_session):
    user = _make_user(db_session)
    headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
    body = client.get("/auth/me", headers=headers).json()
    assert body["username"] == "sacha"
    assert body["role"] == "user"
    assert body["plan"] == "free"


def test_ensure_admin_user_idempotent(db_session):
    insert_setting(db_session, "admin_password_hash", hash_password("change_me"))
    a1 = ensure_admin_user(db_session)
    a2 = ensure_admin_user(db_session)
    assert a1.id == a2.id
    assert a1.role == "admin" and a1.status == "active"
    assert db_session.query(User).count() == 1


# ----------------------------------------------------------- rate limiting
def test_rate_limit_429(client, db_session, monkeypatch):
    from app.services import rate_limit as rl

    class _S:  # settings factice : limiter actif pour CE test
        rate_limit_enabled = True

    monkeypatch.setattr(rl, "get_settings", lambda: _S())
    rl.reset_rate_limits()
    for _ in range(5):
        client.post("/auth/login", json={"username": "x", "password": "y"})
    r = client.post("/auth/login", json={"username": "x", "password": "y"})
    assert r.status_code == 429
    rl.reset_rate_limits()
