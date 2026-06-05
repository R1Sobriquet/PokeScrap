"""Entrée manuelle d'annonces (le scraper viendra au Jalon 6).

``POST /listings`` insère une ``sourcing_listing`` puis déclenche
``evaluate_listing`` et renvoie le verdict (statut + ratio + flags).
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.security import get_current_user
from app.db import get_db
from app.models import SourcingListing
from app.services.buy_evaluation import evaluate_listing

router = APIRouter(tags=["listings"], dependencies=[Depends(get_current_user)])


class DetectedProductIn(BaseModel):
    product_id: int
    qty: int = 1
    confidence: float = 1.0
    is_illustration_rare: bool | None = None


class ListingIn(BaseModel):
    platform: str = "vinted"
    url: str
    raw_title: str
    asking_price: float
    shipping_cost: float = 0.0
    protection_cost: float = 0.0
    currency: str = "EUR"
    location: str | None = None
    estimated_total_cards: int = 0
    detected_products: list[DetectedProductIn] = Field(default_factory=list)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


@router.post("/listings")
def create_listing(payload: ListingIn, db: Session = Depends(get_db)) -> dict:
    listing = SourcingListing(
        platform=payload.platform,
        url=payload.url,
        raw_title=payload.raw_title,
        asking_price=payload.asking_price,
        shipping_cost=payload.shipping_cost,
        protection_cost=payload.protection_cost,
        currency=payload.currency,
        location=payload.location,
        estimated_total_cards=payload.estimated_total_cards,
        detected_products=[p.model_dump() for p in payload.detected_products],
        status="new",
        detected_at=_utcnow(),
    )
    db.add(listing)
    db.commit()
    return evaluate_listing(db, listing.id)
