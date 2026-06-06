"""Émission des alertes de vente (job) — orchestration, pas de décision.

Pour chaque position détenue, calcule le multiple via ``get_latest_price`` puis
appelle le moteur pur ``sell_engine``. Émet une alerte ``sell_*`` (pending) sans
**jamais** poser les ``stage_*`` (posés uniquement à l'exécution du modal).
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.domain.selling import (
    ACTION_ALERT_TYPE,
    NO_ACTION,
    discipline_reminder,
    sell_engine,
    speculation_signal,
)
from app.domain.types import SellPosition
from app.models import Alert, Position
from app.services.prices import get_latest_price

logger = logging.getLogger("services.selling")


def _f(v) -> float:
    return float(v) if v is not None else 0.0


def _has_pending(db: Session, position_id: int, alert_type: str) -> bool:
    return db.scalar(
        select(Alert.id).where(
            Alert.position_id == position_id,
            Alert.alert_type == alert_type,
            Alert.status == "pending",
        )
    ) is not None


def evaluate_position_sales(db: Session, *, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    market = str(get_setting("valuation_market", default="US"))
    fx = _f(get_setting("fx_usd_eur", default=0.92)) if market == "US" else 1.0

    thresholds = dict(
        parabolic_multiple=_f(get_setting("parabolic_multiple", default=4.0)),
        double_multiple=_f(get_setting("double_multiple", default=2.0)),
        explosion_multiple=_f(get_setting("explosion_multiple", default=3.0)),
        forced_sell_pct=_f(get_setting("forced_sell_pct", default=50)),
        partial_sell_pct=_f(get_setting("partial_sell_pct", default=25)),
        speculative_reserve_pct=_f(get_setting("speculative_reserve_pct", default=25)),
    )
    spec_flag = bool(get_setting("speculation_flag", default=False))
    spec_spike = _f(get_setting("speculation_volume_spike_pct", default=200))
    default_profit_target = _f(get_setting("default_profit_target", default=1.5))

    emitted = {"sell": 0, "reminder": 0}
    positions = db.scalars(
        select(Position).where(
            Position.status.in_(("held", "listed", "partially_sold")),
            Position.quantity > 0,
        )
    ).all()

    for pos in positions:
        snap = get_latest_price(db, pos.product_id, market=market)
        if snap is None or snap.price_avg is None or _f(pos.avg_cost) <= 0:
            continue
        mv_unit = _f(snap.price_avg) * fx
        m = mv_unit / _f(pos.avg_cost)

        spec = speculation_signal(
            speculation_flag=spec_flag,
            volume_spike_pct=0.0,  # proxy de volume non disponible au Jalon 5
            speculation_volume_spike_pct=spec_spike,
            m=m,
            parabolic_multiple=thresholds["parabolic_multiple"],
        )
        sp = SellPosition(
            quantity=pos.quantity,
            avg_cost=_f(pos.avg_cost),
            stage_capital_secured=bool(pos.stage_capital_secured),
            stage_structured=bool(pos.stage_structured),
            stage_forced=bool(pos.stage_forced),
        )
        decision = sell_engine(sp, m, spec, **thresholds)

        if decision.action != NO_ACTION:
            alert_type = ACTION_ALERT_TYPE[decision.action]
            if _has_pending(db, pos.id, alert_type):
                continue
            db.add(
                Alert(
                    alert_type=alert_type,
                    severity=decision.severity,
                    status="pending",
                    product_id=pos.product_id,
                    position_id=pos.id,
                    title=f"Vente {decision.action} ×{round(m, 2)}",
                    payload={
                        "action": decision.action,
                        "stages_to_set": list(decision.stages_to_set),
                        "qty_suggested": decision.qty_to_sell,
                        "speculative_reserve_qty": decision.speculative_reserve_qty,
                        "multiple": round(m, 2),
                        "mv_unit": round(mv_unit, 2),
                        "keeps_wick": decision.keeps_wick,
                    },
                )
            )
            emitted["sell"] += 1
            continue

        # Rappel de discipline doux (supprimé si un stage dur est actif).
        stage_active = bool(pos.stage_capital_secured or pos.stage_structured or pos.stage_forced)
        if discipline_reminder(
            mv_unit=mv_unit,
            avg_cost=_f(pos.avg_cost),
            target_sell_price=_f(pos.target_sell_price) if pos.target_sell_price else None,
            default_profit_target=default_profit_target,
            stage_active=stage_active,
        ) and not _has_pending(db, pos.id, "sell_reminder"):
            db.add(
                Alert(
                    alert_type="sell_reminder",
                    severity="info",
                    status="pending",
                    product_id=pos.product_id,
                    position_id=pos.id,
                    title=f"Objectif atteint ×{round(m, 2)}",
                    payload={"multiple": round(m, 2), "mv_unit": round(mv_unit, 2)},
                )
            )
            emitted["reminder"] += 1

    db.commit()
    logger.info("Évaluation ventes : %s alertes, %s rappels.", emitted["sell"], emitted["reminder"])
    return emitted
