"""Endpoint de santé — prouve que le backend est branché à la base."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.db import check_db

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> JSONResponse:
    """Renvoie 200 si la connexion DB répond, 503 sinon."""
    try:
        check_db()
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "db": "error"},
        )
    return JSONResponse(status_code=200, content={"status": "ok", "db": "ok"})
