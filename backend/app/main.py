"""Entrypoint FastAPI — Jalon 1 (fondations).

Au démarrage :
  1. vérifie la connexion à la base ;
  2. vérifie la topologie du schéma (14 tables, 4 paliers, registre settings) ;
  3. amorce le hash bcrypt du mot de passe admin.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import api_router
from app.auth.security import ensure_admin_hash
from app.config import get_settings
from app.db import SessionLocal, check_db, engine
from app.logging_config import setup_logging
from app.services.runtime_settings import ensure_runtime_settings

setup_logging()  # logs JSON + redaction des secrets
logger = logging.getLogger("backend")

EXPECTED_TABLES = 14
EXPECTED_TIERS = 4
MIN_SETTINGS = 80


def verify_schema() -> None:
    """Vérifie au boot que le schéma et les seeds sont présents."""
    settings = get_settings()
    with engine.connect() as conn:
        tables = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = :db"
            ),
            {"db": settings.db_name},
        ).scalar_one()
        tiers = conn.execute(text("SELECT COUNT(*) FROM tiers_config")).scalar_one()
        n_settings = conn.execute(text("SELECT COUNT(*) FROM settings")).scalar_one()

    logger.info(
        "Schéma : %s tables, %s paliers, %s settings.", tables, tiers, n_settings
    )
    if tables < EXPECTED_TABLES:
        raise RuntimeError(
            f"Schéma incomplet : {tables} tables (attendu >= {EXPECTED_TABLES})."
        )
    if tiers != EXPECTED_TIERS:
        raise RuntimeError(
            f"Paliers manquants : {tiers} (attendu {EXPECTED_TIERS})."
        )
    if n_settings < MIN_SETTINGS:
        raise RuntimeError(
            f"Registre settings incomplet : {n_settings} (attendu > {MIN_SETTINGS})."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Démarrage backend.")
    check_db()
    verify_schema()
    ensure_admin_hash()
    with SessionLocal() as db:
        ensure_runtime_settings(db)
    logger.info("Backend prêt.")
    yield
    logger.info("Arrêt backend.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Pokémon Arbitrage — Jalon 1", lifespan=lifespan)

    # Le frontend (Vite) ne parle qu'à l'API ; CORS restreint à son origine.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            f"http://localhost:{settings.frontend_port}",
            f"http://127.0.0.1:{settings.frontend_port}",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app


app = create_app()
