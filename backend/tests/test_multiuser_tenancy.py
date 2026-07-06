"""Tests Phase B : contraintes de tenancy, préférences per-user, backfill admin."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth.security import ensure_admin_user, hash_password
from app.models import (
    AccountSnapshot,
    Product,
    User,
    UserWatchedOffer,
    Watchlist,
)
from app.services.schema_migrations import backfill_multiuser
from app.services.tier_state import get_user_tier, set_user_tier
from app.services.user_settings import clear_user_setting, get_user_setting, set_user_setting
from tests.conftest import insert_setting


def _snap(**kw) -> AccountSnapshot:
    base = dict(total_portfolio_value=0, capital_invested=0, cash_available=0,
                realized_profit_net=0)
    base.update(kw)
    return AccountSnapshot(**base)


def _user(db, name, email=None) -> User:
    u = User(email=email or f"{name}@test.fr", username=name,
             password_hash=hash_password("motdepasse1"), status="active")
    db.add(u)
    db.commit()
    return u


def _product(db) -> Product:
    p = Product(product_type="single", name="Umbreon ex", language="EN")
    db.add(p)
    db.commit()
    return p


# ------------------------------------------------------------- contraintes
def test_two_users_can_watch_same_product(db_session):
    a, b = _user(db_session, "a"), _user(db_session, "b")
    prod = _product(db_session)
    db_session.add(Watchlist(user_id=a.id, product_id=prod.id, tier="B"))
    db_session.add(Watchlist(user_id=b.id, product_id=prod.id, tier="A"))
    db_session.commit()  # l'ancienne UNIQUE(product_id) aurait explosé ici
    assert db_session.query(Watchlist).count() == 2


def test_same_user_cannot_watch_product_twice(db_session):
    a = _user(db_session, "a")
    prod = _product(db_session)
    db_session.add(Watchlist(user_id=a.id, product_id=prod.id, tier="B"))
    db_session.commit()
    db_session.add(Watchlist(user_id=a.id, product_id=prod.id, tier="A"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_two_users_snapshot_same_day(db_session):
    a, b = _user(db_session, "a"), _user(db_session, "b")
    day = dt.date(2026, 7, 1)
    db_session.add(_snap(user_id=a.id, snapshot_date=day))
    db_session.add(_snap(user_id=b.id, snapshot_date=day))
    db_session.commit()  # l'ancienne UNIQUE(snapshot_date) aurait explosé ici
    assert db_session.query(AccountSnapshot).count() == 2


# ------------------------------------------------------ préférences per-user
def test_user_setting_overrides_global_and_falls_back(db_session):
    a, b = _user(db_session, "a"), _user(db_session, "b")
    insert_setting(db_session, "tax_provision_pct", "30", "int")

    # Sans override → défaut global pour tout le monde.
    assert get_user_setting(db_session, a.id, "tax_provision_pct") == 30
    # Override pour A seulement.
    set_user_setting(db_session, a.id, "tax_provision_pct", "17", "int")
    assert get_user_setting(db_session, a.id, "tax_provision_pct") == 17
    assert get_user_setting(db_session, b.id, "tax_provision_pct") == 30
    # Retour au défaut.
    clear_user_setting(db_session, a.id, "tax_provision_pct")
    assert get_user_setting(db_session, a.id, "tax_provision_pct") == 30


def test_user_setting_default_when_key_missing(db_session):
    a = _user(db_session, "a")
    assert get_user_setting(db_session, a.id, "clé_inexistante", default="x") == "x"


# ------------------------------------------------------------ palier per-user
def test_user_tier_roundtrip(db_session):
    a, b = _user(db_session, "a"), _user(db_session, "b")
    assert get_user_tier(db_session, a.id) == 1  # défaut
    set_user_tier(db_session, a.id, 3)
    assert get_user_tier(db_session, a.id) == 3
    assert get_user_tier(db_session, b.id) == 1  # isolé


# ------------------------------------------------------------------ backfill
def test_backfill_multiuser_attaches_orphans_to_admin(db_session):
    insert_setting(db_session, "admin_password_hash", hash_password("change_me"))
    admin = ensure_admin_user(db_session)
    prod = _product(db_session)
    # Lignes « legacy » sans propriétaire (mono-user historique).
    db_session.add(Watchlist(product_id=prod.id, tier="B"))
    db_session.add(_snap(snapshot_date=dt.date(2026, 6, 30)))
    db_session.commit()

    n = backfill_multiuser(db_session)
    assert n == 2
    assert db_session.scalar(select(Watchlist)).user_id == admin.id
    assert db_session.scalar(select(AccountSnapshot)).user_id == admin.id
    # Idempotent : plus rien à rattacher au second passage.
    assert backfill_multiuser(db_session) == 0


def test_backfill_seeds_watch_overlay_from_flags(db_session, sqlite_engine):
    from app.models import RetailOffer, Retailer

    insert_setting(db_session, "admin_password_hash", hash_password("change_me"))
    admin = ensure_admin_user(db_session)
    r = Retailer(code="cultura", name="Cultura")
    db_session.add(r)
    db_session.commit()
    db_session.add(RetailOffer(retailer_id=r.id, url="https://c/x", is_watched=1,
                               watch_tier="hot", current_stock_state="unknown"))
    db_session.add(RetailOffer(retailer_id=r.id, url="https://c/y", is_watched=0,
                               current_stock_state="unknown"))
    db_session.commit()

    backfill_multiuser(db_session)
    rows = db_session.scalars(select(UserWatchedOffer)).all()
    assert len(rows) == 1  # seule l'offre watchée est reprise
    assert rows[0].user_id == admin.id
    assert rows[0].watch_tier == "hot"
    backfill_multiuser(db_session)  # idempotent (NOT EXISTS)
    assert db_session.query(UserWatchedOffer).count() == 1
