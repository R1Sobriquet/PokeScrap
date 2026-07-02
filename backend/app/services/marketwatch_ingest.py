"""Ingestion Market Intelligence : garde-fous + upsert idempotent des snapshots.

AVANT qu'un prix entre dans ``card_price_snapshot`` :
  1. présence + positivité ;
  2. bornes de sanité (EUR, ``sanity_bounds_eur['single']``) ;
  3. outlier vs médiane récente du même (card_id, source, language).
Tout rejet part en ``data_quarantine`` (jamais dans la donnée propre).

Upsert idempotent par ``(card_id, source, language, condition_grade, captured_at)``
→ ré-ingestion le même jour = update, sans doublon.

Orchestrateur ``run_ingest`` : assemble les sources activées (Cardmarket fichier,
PPT, eBay actif), applique les garde-fous, journalise les non-matchés Cardmarket.
Monitoring / aide à la décision uniquement — aucune logique d'achat.
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
from app.marketwatch.domain import CardSnapshot
from app.models import CardPriceSnapshot, DataQuarantine

logger = logging.getLogger("services.marketwatch_ingest")

_OUTLIER_WINDOW_DAYS = 45
_OUTLIER_MIN_POINTS = 3


def _bounds_single() -> tuple[float, float] | None:
    raw = get_setting("sanity_bounds_eur", default={})
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    lo_hi = (raw or {}).get("single") if isinstance(raw, dict) else None
    if isinstance(lo_hi, (list, tuple)) and len(lo_hi) == 2:
        return float(lo_hi[0]), float(lo_hi[1])
    return None


def _recent_median(db: Session, s: CardSnapshot, today: dt.date) -> float | None:
    cutoff = today - dt.timedelta(days=_OUTLIER_WINDOW_DAYS)
    rows = db.scalars(
        select(CardPriceSnapshot.price_eur).where(
            CardPriceSnapshot.card_id == s.card_id,
            CardPriceSnapshot.source == s.source,
            CardPriceSnapshot.language == s.language,
            CardPriceSnapshot.captured_at >= cutoff,
        )
    ).all()
    vals = sorted(float(v) for v in rows if v is not None)
    if len(vals) < _OUTLIER_MIN_POINTS:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2


def validate_snapshot(db: Session, s: CardSnapshot, today: dt.date) -> str | None:
    """Renvoie ``None`` si valide, sinon le motif de rejet."""
    if s.price_eur is None or s.price_eur <= 0:
        return "price_missing_or_nonpositive"
    bounds = _bounds_single()
    if bounds is not None:
        lo, hi = bounds
        if float(s.price_eur) < lo or float(s.price_eur) > hi:
            return f"out_of_sanity_bounds ({float(s.price_eur):.2f}EUR not in [{lo},{hi}])"
    median = _recent_median(db, s, today)
    if median is not None and median > 0:
        ratio = float(s.price_eur) / median
        if ratio > 3.0 or ratio < (1 / 3.0):
            return f"outlier_vs_median (x{ratio:.2f})"
    return None


def _quarantine(db: Session, s: CardSnapshot, reason: str) -> None:
    raw = {k: (str(v) if isinstance(v, Decimal) else v)
           for k, v in asdict(s).items() if k not in ("captured_at", "meta")}
    db.add(DataQuarantine(source=s.source, product_ref=s.card_id, raw=raw, reason=reason))


def ingest_snapshot(db: Session, s: CardSnapshot, *, today: dt.date | None = None) -> str:
    """``stored`` (insert/update idempotent) ou ``quarantined``."""
    today = today or dt.date.today()
    captured_at = s.captured_at or today
    reason = validate_snapshot(db, s, today)
    if reason:
        _quarantine(db, s, reason)
        return "quarantined"

    existing = db.scalar(
        select(CardPriceSnapshot).where(
            CardPriceSnapshot.card_id == s.card_id,
            CardPriceSnapshot.source == s.source,
            CardPriceSnapshot.language == s.language,
            CardPriceSnapshot.condition_grade == s.condition_grade,
            CardPriceSnapshot.captured_at == captured_at,
        )
    )
    if existing is not None:  # idempotent : un seul snapshot/jour, on met à jour
        existing.price_eur = s.price_eur
        existing.price_native = s.price_native
        existing.currency = s.currency
        existing.trend_eur = s.trend_eur
        existing.active_listings = s.active_listings
        existing.watchers = s.watchers
        return "stored"

    db.add(CardPriceSnapshot(
        card_id=s.card_id, source=s.source, language=s.language,
        condition_grade=s.condition_grade, price_eur=s.price_eur,
        price_native=s.price_native, currency=s.currency, trend_eur=s.trend_eur,
        active_listings=s.active_listings, watchers=s.watchers, captured_at=captured_at,
    ))
    return "stored"


def run_ingest(db: Session, *, sources=None, today: dt.date | None = None) -> dict:
    """Exécute l'ingestion pour toutes les sources fournies/activées.

    ``sources`` : liste d'objets ``CardPriceSource`` (injectable pour tests/dry-run).
    Si ``None``, les sources sont assemblées depuis les settings.
    """
    if not bool(get_setting("marketwatch_enabled", default=False)) and sources is None:
        return {"summary": "market intelligence désactivée (marketwatch_enabled=false)"}

    today = today or dt.date.today()
    if sources is None:
        from app.services.marketwatch_sources import build_card_sources
        sources = build_card_sources(db, today=today)

    overall = {"sources": {}, "stored": 0, "quarantined": 0, "unmatched": 0}
    for source in sources:
        st = {"stored": 0, "quarantined": 0}
        try:
            snaps = source.fetch()
        except Exception:  # noqa: BLE001 - une source KO ne casse pas le run
            logger.exception("marketwatch: échec fetch source %s", getattr(source, "code", "?"))
            overall["sources"][getattr(source, "code", "?")] = {"error": True}
            continue
        for snap in snaps:
            st[ingest_snapshot(db, snap, today=today)] += 1
        db.commit()
        unmatched = len(getattr(source, "unmatched", []) or [])
        overall["unmatched"] += unmatched
        overall["stored"] += st["stored"]
        overall["quarantined"] += st["quarantined"]
        st["unmatched"] = unmatched
        overall["sources"][getattr(source, "code", "?")] = st

    parts = [f"{c}:{s.get('stored', 0)}↑" for c, s in overall["sources"].items()]
    overall["summary"] = (f"ingest {' '.join(parts) or '—'} "
                          f"({overall['quarantined']}⌀, {overall['unmatched']} non-matchés)")
    return overall
