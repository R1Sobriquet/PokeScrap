"""Garde-fous d'ingestion + upsert idempotent des snapshots marché.

AVANT qu'un prix entre dans ``market_price_snapshots`` :
  1. présence + positivité ;
  2. cohérence devise/marché (us↔USD, eu↔EUR) ;
  3. bornes de sanité par ``product_type`` (EUR ; USD converti via ``fx_usd_eur``) ;
  4. détection d'outlier vs médiane récente du même (product_ref, source, market).
Tout rejet part en ``data_quarantine`` (jamais dans la donnée propre).

Upsert idempotent par ``(product_ref, source, market, captured_date)`` : re-run le
même jour met à jour sans dupliquer.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import asdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.marketdata.domain import PriceQuote
from app.models import DataQuarantine, MarketPriceSnapshot

logger = logging.getLogger("services.market_ingest")

_MARKET_CCY = {"us": "USD", "eu": "EUR"}
_OUTLIER_WINDOW_DAYS = 21
_OUTLIER_MIN_POINTS = 3


def _fx_usd_eur() -> float:
    try:
        return float(get_setting("fx_usd_eur", default=0.92))
    except (TypeError, ValueError):
        return 0.92


def _bounds() -> dict:
    raw = get_setting("sanity_bounds_eur", default={})
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    return raw if isinstance(raw, dict) else {}


def _to_eur(price: Decimal, market: str) -> float:
    return float(price) * (_fx_usd_eur() if market == "us" else 1.0)


def _recent_median(db: Session, q: PriceQuote, now: dt.datetime) -> float | None:
    cutoff = (now - dt.timedelta(days=_OUTLIER_WINDOW_DAYS)).date()
    rows = db.scalars(
        select(MarketPriceSnapshot.price).where(
            MarketPriceSnapshot.product_ref == q.product_ref,
            MarketPriceSnapshot.source == q.source,
            MarketPriceSnapshot.market == q.market,
            MarketPriceSnapshot.captured_date >= cutoff,
            MarketPriceSnapshot.price.is_not(None),
        )
    ).all()
    vals = sorted(float(v) for v in rows if v is not None)
    if len(vals) < _OUTLIER_MIN_POINTS:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2


def validate_quote(db: Session, q: PriceQuote, now: dt.datetime) -> str | None:
    """Renvoie ``None`` si valide, sinon le motif de rejet."""
    if q.price is None or q.price <= 0:
        return "price_missing_or_nonpositive"
    if _MARKET_CCY.get(q.market) and q.currency.upper() != _MARKET_CCY[q.market]:
        return f"currency_market_mismatch ({q.currency}/{q.market})"

    eur = _to_eur(q.price, q.market)
    ptype = (q.product_type or "autre").lower()
    bounds = _bounds()
    lo_hi = bounds.get(ptype) or bounds.get("autre")
    if isinstance(lo_hi, (list, tuple)) and len(lo_hi) == 2:
        lo, hi = float(lo_hi[0]), float(lo_hi[1])
        if eur < lo or eur > hi:
            return f"out_of_sanity_bounds ({eur:.2f}EUR not in [{lo},{hi}] for {ptype})"

    median = _recent_median(db, q, now)
    if median is not None and median > 0:
        ratio = float(q.price) / median
        if ratio > 3.0 or ratio < (1 / 3.0):
            return f"outlier_vs_median (x{ratio:.2f})"
    return None


def _quarantine(db: Session, q: PriceQuote, reason: str) -> None:
    raw = {k: (str(v) if isinstance(v, Decimal) else v) for k, v in asdict(q).items()}
    raw.pop("captured_at", None)
    db.add(DataQuarantine(source=q.source, product_ref=q.product_ref, raw=raw, reason=reason))


def ingest_quote(db: Session, q: PriceQuote, now: dt.datetime | None = None) -> str:
    """``stored`` (insert/update idempotent) ou ``quarantined``."""
    now = now or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    captured_at = q.captured_at or now
    reason = validate_quote(db, q, now)
    if reason:
        _quarantine(db, q, reason)
        return "quarantined"

    captured_date = captured_at.date()
    existing = db.scalar(
        select(MarketPriceSnapshot).where(
            MarketPriceSnapshot.product_ref == q.product_ref,
            MarketPriceSnapshot.source == q.source,
            MarketPriceSnapshot.market == q.market,
            MarketPriceSnapshot.captured_date == captured_date,
        )
    )
    if existing is not None:  # idempotent : un seul snapshot/jour, on met à jour
        existing.price = q.price
        existing.currency = q.currency
        existing.product_type = q.product_type
        existing.extra = q.extra or None
        existing.captured_at = captured_at
        return "stored"

    db.add(MarketPriceSnapshot(
        product_ref=q.product_ref, source=q.source, market=q.market,
        product_type=q.product_type, price=q.price, currency=q.currency,
        extra=q.extra or None, captured_at=captured_at, captured_date=captured_date,
    ))
    return "stored"
