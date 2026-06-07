"""Routes REST. J1 : /health + /auth. J2 : catalogue/prix. J8 : dashboard."""

from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.listings import router as listings_router
from app.api.products import router as products_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(products_router)
api_router.include_router(listings_router)
api_router.include_router(dashboard_router)
api_router.include_router(admin_router)

__all__ = ["api_router"]
