"""Couche d'accès base — pool de connexions MySQL (SQLAlchemy 2.x)."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import BigInteger, Integer, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

#: Clé primaire : ``BIGINT`` en production (MySQL, comme ``schema.sql``), mais
#: ``INTEGER`` sous SQLite pour bénéficier de l'auto-increment natif en test.
BigIntPK = BigInteger().with_variant(Integer, "sqlite")

_settings = get_settings()

# `pool_pre_ping` recycle silencieusement les connexions mortes (MySQL coupe les
# connexions inactives) ; `pool_recycle` borne leur durée de vie.
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base déclarative commune aux modèles ORM."""


def get_db() -> Iterator[Session]:
    """Dépendance FastAPI : fournit une session, la ferme en fin de requête."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db() -> bool:
    """Renvoie ``True`` si la base répond à un simple ``SELECT 1``."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
