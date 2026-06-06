"""Job de snapshot KPI quotidien (réf. S7) + transitions de palier.

Écrit une ligne ``account_snapshots`` puis :
  * évalue la transition de palier sur la série des derniers snapshots →
    ``palier_up`` (pending, confirmation — active le handler J4) ou ``palier_down``
    appliqué automatiquement (hystérésis) ;
  * rollup mensuel → alerte ``tax_provision`` (info, digest).
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.domain.tiers import PRE_TIER, evaluate_tier_transition, resolve_current_tier
from app.domain.types import TierBand
from app.models import AccountSnapshot, Alert, TierConfig
from app.services.ledger import compute_kpis
from app.services.tier_state import get_current_tier_number, set_current_tier, tier_config_id

logger = logging.getLogger("services.kpi_snapshot")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _bands(db: Session) -> list[TierBand]:
    return [
        TierBand(
            tier_number=t.tier_number,
            capital_min=float(t.capital_min),
            capital_max=float(t.capital_max) if t.capital_max is not None else None,
            cash_min_pct=float(t.cash_min_pct),
        )
        for t in db.scalars(select(TierConfig)).all()
    ]


def _initial_tier(op_capital: float, bands: list[TierBand]) -> int:
    resolved = resolve_current_tier(op_capital, bands)
    if isinstance(resolved, TierBand):
        return resolved.tier_number
    return 1 if resolved == PRE_TIER else (max(b.tier_number for b in bands) if bands else 1)


def _has_pending(db: Session, alert_type: str) -> bool:
    return db.scalar(
        select(Alert.id).where(Alert.alert_type == alert_type, Alert.status == "pending")
    ) is not None


def run_kpi_snapshot(db: Session, *, now: dt.datetime | None = None) -> dict:
    now = now or _utcnow()
    today = now.date()
    kpis = compute_kpis(db, now=now)
    bands = _bands(db)

    current_tier = get_current_tier_number(db, default=_initial_tier(kpis["operational_capital"], bands))

    # Upsert du snapshot du jour.
    snap = db.scalar(select(AccountSnapshot).where(AccountSnapshot.snapshot_date == today))
    if snap is None:
        snap = AccountSnapshot(snapshot_date=today)
        db.add(snap)
    snap.total_portfolio_value = kpis["total_portfolio_value"]
    snap.capital_invested = kpis["capital_invested"]
    snap.cash_available = kpis["cash_total"]
    snap.cash_locked = kpis["cash_locked"]
    snap.cash_active = kpis["cash_active"]
    snap.realized_profit_net = kpis["realized_profit_net"]
    snap.capital_rotation_rate = kpis["capital_rotation_rate"]
    snap.turnover_cumulative = kpis["turnover_cumulative"]
    snap.tax_provision = kpis["tax_provision"]
    snap.current_tier_id = tier_config_id(db, current_tier)
    db.commit()

    # Série operational_capital sur les derniers snapshots (du plus ancien au récent).
    sustain = int(float(get_setting("tier_sustain_snapshots", default=3)))
    hysteresis = float(get_setting("tier_hysteresis_pct", default=10))
    recent = db.scalars(
        select(AccountSnapshot).order_by(AccountSnapshot.snapshot_date.desc()).limit(sustain)
    ).all()
    series = [float(s.cash_active or 0) + float(s.capital_invested or 0) for s in reversed(recent)]

    transition = evaluate_tier_transition(
        current_tier, series, bands, sustain_snapshots=sustain, hysteresis_pct=hysteresis
    )

    result = {"snapshot_date": str(today), "transition": None, **{k: kpis[k] for k in ("operational_capital",)}}

    if transition is not None and transition.direction == "up":
        if not _has_pending(db, "palier_up"):
            db.add(
                Alert(
                    alert_type="palier_up",
                    severity="warning",
                    status="pending",
                    title=f"Promotion palier {current_tier} → {transition.target_tier}",
                    payload={"target_tier": transition.target_tier, "from_tier": current_tier,
                             "message": "Promotion soutenue — confirmation requise."},
                )
            )
            db.commit()
        result["transition"] = {"direction": "up", "target": transition.target_tier, "requires_confirm": True}
    elif transition is not None and transition.direction == "down":
        set_current_tier(db, transition.target_tier)
        snap.current_tier_id = tier_config_id(db, transition.target_tier)
        db.add(
            Alert(
                alert_type="palier_down",
                severity="warning",
                status="pending",
                title=f"Rétrogradation palier {current_tier} → {transition.target_tier}",
                payload={"target_tier": transition.target_tier, "from_tier": current_tier,
                         "message": "Rétrogradation automatique (hystérésis)."},
            )
        )
        db.commit()
        result["transition"] = {"direction": "down", "target": transition.target_tier, "auto": True}

    # Rollup mensuel : provision fiscale (info, digest) le 1er du mois.
    if today.day == 1 and kpis["turnover_cumulative"] > 0 and not _has_pending(db, "tax_provision"):
        db.add(
            Alert(
                alert_type="tax_provision",
                severity="info",
                status="pending",
                title="Provision fiscale (mensuel)",
                payload={
                    "subtype": "tax_provision",
                    "turnover_cumulative": kpis["turnover_cumulative"],
                    "tax_provision": kpis["tax_provision"],
                },
            )
        )
        db.commit()

    logger.info("Snapshot KPI %s écrit ; transition=%s", today, result["transition"])
    return result
