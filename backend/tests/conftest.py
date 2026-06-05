"""Fixtures de test.

Les tests tournent **sans MySQL** : on substitue à ``app.db.engine`` /
``app.db.SessionLocal`` un moteur SQLite en mémoire (``StaticPool`` → une seule
connexion persistante) muni de toutes les tables mappées par l'ORM. Cela exerce
la vraie logique (ingestion, lecture, auth, get_setting) sans conteneur.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db as db_module
import app.models  # noqa: F401 — enregistre les tables sur Base.metadata
from app.config import invalidate_setting
from app.db import Base
from app.models import Setting


@pytest.fixture()
def sqlite_engine(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False, future=True
    )
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "SessionLocal", TestSession)
    invalidate_setting()  # cache propre entre les tests
    yield engine
    invalidate_setting()


@pytest.fixture()
def db_session(sqlite_engine):
    from app.db import SessionLocal  # version patchée

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def insert_setting(db, key: str, value: str, value_type: str = "string") -> None:
    """Helper : insère un réglage métier et invalide le cache."""
    db.add(Setting(setting_key=key, setting_value=value, value_type=value_type))
    db.commit()
    invalidate_setting(key)
