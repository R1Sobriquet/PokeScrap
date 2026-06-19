"""Construction du jeu d'entraînement depuis l'historique réel ``price_snapshots``.

Cibles dérivées de signaux RÉELS (un snapshot par produit, le plus récent) :
  * ``roi``        — momentum prix : (avg_1d − avg_30d) / avg_30d  (appréciation %).
  * ``popularity`` — ``sale_count`` (volume de ventes).
  * ``hype``       — volatilité : (price_high − price_low) / price_avg  (amplitude %).

Aucune cible fabriquée : un produit sans snapshot exploitable est ignoré.
"""

from __future__ import annotations

import statistics

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.features import extract_features
from app.models import MarketPriceSnapshot, PriceSnapshot, Product

TARGETS = ("roi", "popularity", "hype")
#: série marché min par produit pour qu'un signal compte (anti séries trop courtes).
_MARKET_MIN_POINTS = 4


def _f(v) -> float | None:
    return float(v) if v is not None else None


def market_features(db: Session, product_ref: str) -> dict | None:
    """Features marché dérivées de ``market_price_snapshots`` (spread EU/US,
    volatilité, momentum). ``None`` si la série est trop courte (garde-fou)."""
    rows = db.scalars(
        select(MarketPriceSnapshot).where(
            MarketPriceSnapshot.product_ref == product_ref,
            MarketPriceSnapshot.price.is_not(None),
        ).order_by(MarketPriceSnapshot.captured_date.asc())
    ).all()
    if len(rows) < _MARKET_MIN_POINTS:
        return None
    eu = [float(r.price) for r in rows if r.market == "eu"]
    us = [float(r.price) for r in rows if r.market == "us"]
    series = eu or us
    if len(series) < _MARKET_MIN_POINTS:
        return None
    mean = statistics.fmean(series)
    vol = (statistics.pstdev(series) / mean * 100.0) if mean else 0.0
    momentum = ((series[-1] - series[0]) / series[0] * 100.0) if series[0] else 0.0
    spread = 0.0
    if eu and us and eu[-1]:
        spread = (us[-1] - eu[-1]) / eu[-1] * 100.0
    return {"spread": spread, "volatility": vol, "momentum": momentum}


def _latest_snapshot(db: Session, product_id: int) -> PriceSnapshot | None:
    return db.scalar(
        select(PriceSnapshot)
        .where(PriceSnapshot.product_id == product_id, PriceSnapshot.grade_company == "RAW")
        .order_by(PriceSnapshot.captured_at.desc())
        .limit(1)
    )


def build_training_rows(db: Session) -> tuple[list[list[float]], dict[str, list[float]]]:
    """Renvoie ``(X, {roi, popularity, hype})`` depuis les produits avec prix."""
    X: list[list[float]] = []
    y: dict[str, list[float]] = {t: [] for t in TARGETS}

    for product in db.scalars(select(Product)).all():
        snap = _latest_snapshot(db, product.id)
        if snap is None:
            continue
        base = _f(snap.avg_30d) or _f(snap.price_avg)
        recent = _f(snap.avg_1d) or _f(snap.avg_7d) or _f(snap.price_avg)
        if not base or base <= 0 or recent is None:
            continue

        roi = (recent - base) / base * 100.0
        popularity = _f(snap.sale_count) or 0.0
        hi, lo = _f(snap.price_high), _f(snap.price_low)
        vol_base = _f(snap.price_avg) or recent
        hype = ((hi - lo) / vol_base * 100.0) if (hi is not None and lo is not None and vol_base) else abs(roi)

        mkt = market_features(db, str(product.id))
        X.append(extract_features(product_type=product.product_type, name=product.name,
                                  language=product.language, market=mkt))
        y["roi"].append(roi)
        y["popularity"].append(popularity)
        y["hype"].append(hype)

    return X, y
