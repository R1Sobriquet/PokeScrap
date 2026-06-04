"""Routes REST. Jalon 1 : /health + /auth."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)

__all__ = ["api_router"]
