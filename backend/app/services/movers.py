"""Service top movers : lit les price_snapshots et classe par momentum + volume."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.domain.movers import momentum_rise, mover_score
from app.models import Product, Watchlist
from app.services.prices import get_latest_price

logger = logging.getLogger("services.movers")


def _f(v):
    return float(v) if v is not None else None


def compute_top_movers(db: Session, *, set_slug: str | None = None, limit: int | None = None) -> list[dict]:
    """Top movers (hausse confirmée par le volume) sur la watchlist active."""
    market = str(get_setting("valuation_market", default="US"))
    min_volume = int(float(get_setting("movers_min_volume", default=5)))
    top_n = limit or int(float(get_setting("movers_top_n", default=10)))

    stmt = select(Watchlist, Product).join(Product, Watchlist.product_id == Product.id).where(
        Watchlist.is_active == 1
    )
    if set_slug:
        stmt = stmt.where(Product.set_slug == set_slug)

    rows = []
    for _watch, product in db.execute(stmt).all():
        snap = get_latest_price(db, product.id, market=market)
        if snap is None:
            continue
        score = mover_score(_f(snap.avg_7d), _f(snap.avg_30d), snap.sale_count, min_volume=min_volume)
        if score is None:
            continue
        rise = momentum_rise(_f(snap.avg_7d), _f(snap.avg_30d))
        rows.append({
            "product_id": product.id,
            "name": product.name,
            "set_slug": product.set_slug,
            "rise_pct": round(rise * 100, 2) if rise is not None else None,
            "volume": snap.sale_count,
            "price": _f(snap.price_avg),
            "score": round(score, 4),
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:top_n]
