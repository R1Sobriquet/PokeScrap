"""Routes de lecture seule (protégées JWT) pour vérifier l'ingestion.

Aucune logique de décision : on expose le catalogue, la watchlist et le dernier
prix d'un produit.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import get_current_user
from app.db import get_db
from app.models import PriceSnapshot, Product, Watchlist
from app.services.prices import get_latest_price

router = APIRouter(tags=["catalog"], dependencies=[Depends(get_current_user)])


def _product_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "product_type": p.product_type,
        "name": p.name,
        "set_name": p.set_name,
        "set_slug": p.set_slug,
        "card_number": p.card_number,
        "language": p.language,
        "poketrace_id": p.poketrace_id,
        "cardmarket_id": p.cardmarket_id,
        "tcgplayer_id": p.tcgplayer_id,
        "is_active": bool(p.is_active),
    }


def _snapshot_dict(s: PriceSnapshot) -> dict:
    return {
        "product_id": s.product_id,
        "source": s.source,
        "market": s.market,
        "grade_company": s.grade_company,
        "grade": s.grade,
        "condition_code": s.condition_code,
        "currency": s.currency,
        "price_avg": float(s.price_avg) if s.price_avg is not None else None,
        "price_low": float(s.price_low) if s.price_low is not None else None,
        "price_high": float(s.price_high) if s.price_high is not None else None,
        "avg_1d": float(s.avg_1d) if s.avg_1d is not None else None,
        "avg_7d": float(s.avg_7d) if s.avg_7d is not None else None,
        "avg_30d": float(s.avg_30d) if s.avg_30d is not None else None,
        "sale_count": s.sale_count,
        "approx_sale_count": bool(s.approx_sale_count),
        "captured_at": s.captured_at.isoformat() if s.captured_at else None,
    }


@router.get("/products")
def list_products(
    db: Session = Depends(get_db),
    active_only: bool = Query(default=False),
    limit: int = Query(default=200, le=1000),
) -> list[dict]:
    stmt = select(Product).order_by(Product.id)
    if active_only:
        stmt = stmt.where(Product.is_active == 1)
    stmt = stmt.limit(limit)
    return [_product_dict(p) for p in db.scalars(stmt).all()]


@router.get("/watchlist")
def list_watchlist(
    db: Session = Depends(get_db),
    active_only: bool = Query(default=True),
) -> list[dict]:
    stmt = select(Watchlist, Product).join(Product, Watchlist.product_id == Product.id)
    if active_only:
        stmt = stmt.where(Watchlist.is_active == 1)
    stmt = stmt.order_by(Watchlist.tier, Product.name)
    rows = db.execute(stmt).all()
    return [
        {
            "product_id": w.product_id,
            "tier": w.tier,
            "is_trinity": bool(w.is_trinity),
            "is_illustration_rare": bool(w.is_illustration_rare),
            "min_discount_pct": float(w.min_discount_pct) if w.min_discount_pct is not None else None,
            "keywords": w.keywords,
            "is_active": bool(w.is_active),
            "product": _product_dict(p),
        }
        for w, p in rows
    ]


@router.get("/products/{product_id}/prices/latest")
def latest_price(
    product_id: int,
    db: Session = Depends(get_db),
    grade_company: str = Query(default="RAW"),
    grade: str | None = Query(default=None),
    condition: str = Query(default="NM"),
    market: str | None = Query(default=None),
) -> dict:
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    snapshot = get_latest_price(
        db,
        product_id,
        grade_company=grade_company,
        grade=grade,
        condition=condition,
        market=market,
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Aucun prix pour ce tier")
    return _snapshot_dict(snapshot)
