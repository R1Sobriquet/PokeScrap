"""Rétention des price_snapshots (bornage de la croissance).

Au-delà de ``price_snapshot_detail_days``, on ne garde **qu'un snapshot par jour
par tier** (on élague les intraday). On préserve donc l'historique nécessaire à
l'anti-pump (≥ 1/jour/tier). Désactivable (``price_snapshot_pruning_enabled``).
Ne touche **jamais** au ledger.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.models import PriceSnapshot

logger = logging.getLogger("services.retention")

# Tier = combinaison qui identifie une série de prix comparable.
_TIER_COLS = (
    PriceSnapshot.product_id,
    PriceSnapshot.source,
    PriceSnapshot.market,
    PriceSnapshot.marketplace,
    PriceSnapshot.grade_company,
    PriceSnapshot.grade,
    PriceSnapshot.condition_code,
)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def prune_price_snapshots(db: Session, *, now: dt.datetime | None = None) -> dict:
    """Garde 1 snapshot/jour/tier au-delà de la fenêtre détaillée. No-op si désactivé."""
    if not bool(get_setting("price_snapshot_pruning_enabled", default=False)):
        return {"status": "disabled", "deleted": 0}

    now = now or _utcnow()
    detail_days = int(float(get_setting("price_snapshot_detail_days", default=60)))
    cutoff = now - dt.timedelta(days=detail_days)

    # Pour chaque (tier, jour) avant la fenêtre, on garde le snapshot le plus récent.
    keep = select(func.max(PriceSnapshot.id)).where(PriceSnapshot.captured_at < cutoff).group_by(
        *_TIER_COLS, func.date(PriceSnapshot.captured_at)
    )
    keep_ids = set(db.scalars(keep).all())

    to_delete = db.scalars(
        select(PriceSnapshot.id).where(
            PriceSnapshot.captured_at < cutoff, PriceSnapshot.id.notin_(keep_ids)
        )
    ).all()
    if to_delete:
        db.execute(delete(PriceSnapshot).where(PriceSnapshot.id.in_(to_delete)))
        db.commit()
    logger.info("Pruning price_snapshots : %s lignes intraday supprimées (< %s).",
                len(to_delete), cutoff.date())
    return {"status": "ok", "deleted": len(to_delete), "kept_per_day_per_tier": len(keep_ids)}
