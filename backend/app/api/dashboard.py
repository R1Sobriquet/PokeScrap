"""Endpoints de lecture du dashboard (protégés JWT).

Aucune logique métier : on lit la base et on réutilise les services existants
(``ledger.compute_kpis``, ``get_latest_price``). Les mutations sont dans
``api/admin.py``.
"""

from __future__ import annotations

import csv
import datetime as dt
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import get_current_user
from app.config import get_setting
from app.db import get_db
from app.models import (
    AccountSnapshot,
    Alert,
    GradingOpportunity,
    Lot,
    LotItem,
    Position,
    Product,
    SourcingListing,
    TierConfig,
    Transaction,
)
from app.services.ledger import compute_kpis
from app.services.prices import get_latest_price
from app.services.tier_state import get_current_tier_number

router = APIRouter(tags=["dashboard"], dependencies=[Depends(get_current_user)])


def _f(v, default=None):
    return float(v) if v is not None else default


def _market_fx() -> tuple[str, float]:
    market = str(get_setting("valuation_market", default="US"))
    fx = _f(get_setting("fx_usd_eur", default=0.92), 0.92) if market == "US" else 1.0
    return market, fx


# --------------------------------------------------------------- cockpit
@router.get("/cockpit")
def cockpit(db: Session = Depends(get_db)) -> dict:
    kpis = compute_kpis(db)
    bands = {t.tier_number: t for t in db.scalars(select(TierConfig)).all()}
    current_num = get_current_tier_number(db, default=1)
    current = bands.get(current_num)
    nxt = bands.get(current_num + 1)

    op = kpis["operational_capital"]
    progress = None
    if current and current.capital_max is not None:
        lo, hi = float(current.capital_min), float(current.capital_max)
        if hi > lo:
            progress = max(0.0, min(1.0, (op - lo) / (hi - lo)))

    alloc = None
    if op > 0:
        alloc = {
            "stock_pct": round(kpis["capital_invested"] / op * 100, 1),
            "cash_pct": round(kpis["cash_active"] / op * 100, 1),
            "target_stock_pct": _f(current.alloc_stock_pct) if current else None,
            "target_cash_pct": _f(current.alloc_cash_pct) if current else None,
        }

    history_days = int(_f(get_setting("chart_history_days", default=90), 90))
    cutoff = dt.date.today() - dt.timedelta(days=history_days)
    history = [
        {"date": s.snapshot_date.isoformat(), "total_portfolio_value": _f(s.total_portfolio_value)}
        for s in db.scalars(
            select(AccountSnapshot).where(AccountSnapshot.snapshot_date >= cutoff)
            .order_by(AccountSnapshot.snapshot_date)
        ).all()
    ]
    pending = db.scalar(select(Alert).where(Alert.status == "pending"))
    pending_count = len(db.scalars(select(Alert.id).where(Alert.status == "pending")).all())

    return {
        "kpis": kpis,
        "tier": {
            "current": current_num,
            "current_name": current.name if current else None,
            "next": (current_num + 1) if nxt else None,
            "capital_min": _f(current.capital_min) if current else None,
            "capital_max": _f(current.capital_max) if current else None,
            "progress": progress,
        },
        "allocation": alloc,
        "pending_alerts": pending_count,
        "history": history,
    }


# --------------------------------------------------------------- snapshots
def _snapshot_dict(s: AccountSnapshot) -> dict:
    return {
        "snapshot_date": s.snapshot_date.isoformat(),
        "total_portfolio_value": _f(s.total_portfolio_value),
        "capital_invested": _f(s.capital_invested),
        "cash_available": _f(s.cash_available),
        "cash_locked": _f(s.cash_locked),
        "cash_active": _f(s.cash_active),
        "realized_profit_net": _f(s.realized_profit_net),
        "capital_rotation_rate": _f(s.capital_rotation_rate),
        "turnover_cumulative": _f(s.turnover_cumulative),
        "tax_provision": _f(s.tax_provision),
        "current_tier_id": s.current_tier_id,
    }


@router.get("/snapshots/latest")
def snapshot_latest(db: Session = Depends(get_db)) -> dict:
    snap = db.scalar(select(AccountSnapshot).order_by(AccountSnapshot.snapshot_date.desc()))
    if snap is None:
        raise HTTPException(status_code=404, detail="Aucun snapshot")
    return _snapshot_dict(snap)


@router.get("/snapshots")
def snapshots(
    db: Session = Depends(get_db),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
) -> list[dict]:
    stmt = select(AccountSnapshot).order_by(AccountSnapshot.snapshot_date)
    if date_from:
        stmt = stmt.where(AccountSnapshot.snapshot_date >= dt.date.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(AccountSnapshot.snapshot_date <= dt.date.fromisoformat(date_to))
    return [_snapshot_dict(s) for s in db.scalars(stmt).all()]


# --------------------------------------------------------------- positions
@router.get("/positions")
def positions(db: Session = Depends(get_db)) -> list[dict]:
    market, fx = _market_fx()
    rows = db.execute(
        select(Position, Product).join(Product, Position.product_id == Product.id)
        .where(Position.quantity > 0).order_by(Position.id)
    ).all()
    out = []
    for pos, product in rows:
        snap = get_latest_price(db, pos.product_id, market=market)
        avg_cost = _f(pos.avg_cost, 0.0)
        mv_unit = _f(snap.price_avg, 0.0) * fx if (snap and snap.price_avg is not None) else None
        multiple = (mv_unit / avg_cost) if (mv_unit and avg_cost) else None
        latent = ((mv_unit - avg_cost) * pos.quantity) if mv_unit is not None else None
        out.append({
            "id": pos.id,
            "product_id": pos.product_id,
            "product_name": product.name,
            "quantity": pos.quantity,
            "avg_cost": avg_cost,
            "market_value_unit": round(mv_unit, 2) if mv_unit is not None else None,
            "market_value_total": round(mv_unit * pos.quantity, 2) if mv_unit is not None else None,
            "multiple": round(multiple, 2) if multiple else None,
            "latent_pnl": round(latent, 2) if latent is not None else None,
            "target_sell_price": _f(pos.target_sell_price),
            "stages": {
                "capital_secured": bool(pos.stage_capital_secured),
                "structured": bool(pos.stage_structured),
                "forced": bool(pos.stage_forced),
            },
            "is_speculative_reserve": bool(pos.is_speculative_reserve),
            "status": pos.status,
        })
    return out


# --------------------------------------------------------------- lots
@router.get("/lots")
def lots(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "id": lot.id, "label": lot.label, "total_cost": _f(lot.total_cost),
            "currency": lot.currency, "platform": lot.platform, "status": lot.status,
            "source_listing_id": lot.source_listing_id,
            "purchased_at": lot.purchased_at.isoformat() if lot.purchased_at else None,
        }
        for lot in db.scalars(select(Lot).order_by(Lot.id.desc())).all()
    ]


@router.get("/lots/{lot_id}/items")
def lot_items(lot_id: int, db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "id": it.id, "product_id": it.product_id, "quantity": it.quantity,
            "segmentation": it.segmentation,
            "estimated_unit_value": _f(it.estimated_unit_value),
            "bulk_group_label": it.bulk_group_label,
            "target_platform": it.target_platform, "status": it.status,
        }
        for it in db.scalars(select(LotItem).where(LotItem.lot_id == lot_id).order_by(LotItem.id)).all()
    ]


# --------------------------------------------------------------- opportunities
@router.get("/opportunities")
def opportunities(
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
) -> list[dict]:
    stmt = select(SourcingListing).order_by(SourcingListing.detected_at.desc())
    if status:
        stmt = stmt.where(SourcingListing.status == status)
    return [
        {
            "id": l.id, "platform": l.platform, "url": l.url, "raw_title": l.raw_title,
            "acquisition_cost_total": _f(l.acquisition_cost_total) or (
                _f(l.asking_price, 0.0) + _f(l.shipping_cost, 0.0) + _f(l.protection_cost, 0.0)
            ),
            "estimated_resale_value": _f(l.estimated_resale_value),
            "ratio_pct": _f(l.ratio_pct), "passes_50_rule": (
                None if l.passes_50_rule is None else bool(l.passes_50_rule)
            ),
            "status": l.status, "filter_flags": l.filter_flags,
            "location": l.location,
            "detected_at": l.detected_at.isoformat() if l.detected_at else None,
        }
        for l in db.scalars(stmt).all()
    ]


# --------------------------------------------------------------- transactions
@router.get("/transactions")
def transactions(
    db: Session = Depends(get_db),
    tx_type: str | None = Query(default=None),
    limit: int = Query(default=500, le=5000),
) -> list[dict]:
    stmt = select(Transaction).order_by(Transaction.occurred_at.desc())
    if tx_type:
        stmt = stmt.where(Transaction.tx_type == tx_type)
    stmt = stmt.limit(limit)
    return [_tx_dict(t) for t in db.scalars(stmt).all()]


def _tx_dict(t: Transaction) -> dict:
    return {
        "id": t.id, "tx_type": t.tx_type, "product_id": t.product_id,
        "position_id": t.position_id, "lot_id": t.lot_id, "quantity": t.quantity,
        "gross_amount": _f(t.gross_amount), "platform_fees": _f(t.platform_fees),
        "net_amount": _f(t.net_amount), "cost_basis": _f(t.cost_basis),
        "currency": t.currency, "platform": t.platform,
        "occurred_at": t.occurred_at.isoformat() if t.occurred_at else None,
    }


@router.get("/ledger/export.csv")
def export_ledger(db: Session = Depends(get_db)) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "tx_type", "occurred_at", "product_id", "lot_id", "quantity",
                     "gross_amount", "platform_fees", "net_amount", "cost_basis", "currency"])
    for t in db.scalars(select(Transaction).order_by(Transaction.occurred_at)).all():
        writer.writerow([t.id, t.tx_type, t.occurred_at.isoformat() if t.occurred_at else "",
                         t.product_id or "", t.lot_id or "", t.quantity,
                         _f(t.gross_amount, 0), _f(t.platform_fees, 0), _f(t.net_amount, 0),
                         _f(t.cost_basis) if t.cost_basis is not None else "", t.currency])
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ledger.csv"},
    )


# --------------------------------------------------------------- grading / alerts / tiers
@router.get("/grading-opportunities")
def grading_opportunities(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(GradingOpportunity, Product).join(Product, GradingOpportunity.product_id == Product.id)
        .order_by(GradingOpportunity.is_recommended.desc(), GradingOpportunity.id.desc())
    ).all()
    return [
        {
            "id": o.id, "product_id": o.product_id, "product_name": p.name,
            "raw_value": _f(o.raw_value), "expected_net_weighted": _f(o.expected_net_weighted),
            "grading_cost": _f(o.grading_cost), "grade_probability": o.grade_probability,
            "is_recommended": bool(o.is_recommended),
            "computed_at": o.computed_at.isoformat() if o.computed_at else None,
        }
        for o, p in rows
    ]


@router.get("/alerts")
def alerts(
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    limit: int = Query(default=200, le=2000),
) -> list[dict]:
    stmt = select(Alert).order_by(Alert.created_at.desc())
    if status:
        stmt = stmt.where(Alert.status == status)
    stmt = stmt.limit(limit)
    return [
        {
            "id": a.id, "alert_type": a.alert_type, "severity": a.severity, "status": a.status,
            "title": a.title, "payload": a.payload,
            "product_id": a.product_id, "sourcing_listing_id": a.sourcing_listing_id,
            "position_id": a.position_id,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in db.scalars(stmt).all()
    ]


@router.get("/tiers")
def tiers(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "tier_number": t.tier_number, "name": t.name,
            "capital_min": _f(t.capital_min), "capital_max": _f(t.capital_max),
            "cash_min_pct": _f(t.cash_min_pct),
            "alloc_stock_pct": _f(t.alloc_stock_pct), "alloc_cash_pct": _f(t.alloc_cash_pct),
        }
        for t in db.scalars(select(TierConfig).order_by(TierConfig.tier_number)).all()
    ]
