"""Fixtures de test.

Les tests du Jalon 1 tournent **sans MySQL** : on substitue à ``app.db.engine``
un moteur SQLite en mémoire (``StaticPool`` → une seule connexion persistante),
muni d'une table ``settings`` minimale. Cela exerce la vraie logique de
``get_setting`` / ``authenticate`` / ``check_db`` sans dépendre d'un conteneur.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

import app.db as db_module
from app.config import invalidate_setting


@pytest.fixture()
def sqlite_engine(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE settings (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_key   TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL,
                    value_type    TEXT NOT NULL DEFAULT 'string',
                    description   TEXT
                )
                """
            )
        )
    monkeypatch.setattr(db_module, "engine", engine)
    invalidate_setting()  # cache propre entre les tests
    yield engine
    invalidate_setting()
