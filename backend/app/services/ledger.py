"""Ledger, cascade de trésorerie & KPIs (réf. S7).

Lit la base et délègue les calculs purs à ``domain.accounting``. ``cash_locked``
est recalculé depuis l'historique des ventes profitables (somme de parts
positives → monotone par construction, jamais diminué automatiquement).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.domain import accounting
from app.models import Lot, Position, Transaction
from app.services.prices import get_latest_price


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _f(v) -> float:
    return float(v) if v is not None else 0.0


def cash_total(db: Session) -> float:
    return _f(db.scalar(select(func.coalesce(func.sum(Transaction.net_amount), 0))))


def capital_invested(db: Session) -> float:
    positions = db.scalar(
        select(func.coalesce(func.sum(Position.avg_cost * Position.quantity), 0))
    )
    lots = db.scalar(
        select(func.coalesce(func.sum(Lot.total_cost), 0)).where(Lot.status != "liquidated")
    )
    return _f(positions) + _f(lots)


def _sell_pairs(db: Session) -> list[tuple[float, float]]:
    rows = db.execute(
        select(Transaction.net_amount, Transaction.cost_basis).where(Transaction.tx_type == "sell")
    ).all()
    return [(_f(net), _f(cost)) for net, cost in rows]


def computed_cash_locked(db: Session) -> float:
    reinvest_lock_pct = _f(get_setting("reinvest_lock_pct", default=30))
    lock_only_positive = bool(get_setting("lock_only_positive_profit", default=True))
    locked = 0.0
    for net, cost in _sell_pairs(db):
        locked += accounting.lock_increment(
            net - cost, reinvest_lock_pct=reinvest_lock_pct, lock_only_positive=lock_only_positive
        )
    return locked


def _isolated_fees(db: Session) -> float:
    fees = db.scalar(
        select(func.coalesce(func.sum(Transaction.net_amount), 0)).where(Transaction.tx_type == "fee")
    )
    return -_f(fees)  # les frais isolés sont des net_amount négatifs


def _turnover(db: Session) -> float:
    return _f(
        db.scalar(
            select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
                Transaction.tx_type == "sell"
            )
        )
    )


def _market_values(db: Session, *, market: str, fx: float) -> list[float]:
    """Valeur de marché best-effort (positions au prix dernier, sinon coût ; lots au coût)."""
    values: list[float] = []
    for pos in db.scalars(select(Position).where(Position.quantity > 0)).all():
        snap = get_latest_price(db, pos.product_id, market=market)
        unit = _f(snap.price_avg) * fx if (snap and snap.price_avg is not None) else _f(pos.avg_cost)
        values.append(unit * pos.quantity)
    for lot in db.scalars(select(Lot).where(Lot.status != "liquidated")).all():
        values.append(_f(lot.total_cost))
    return values


def compute_kpis(db: Session, *, now: dt.datetime | None = None) -> dict:
    """Calcule la cascade + les 5 KPIs + provision fiscale."""
    now = now or _utcnow()
    market = str(get_setting("valuation_market", default="US"))
    fx = _f(get_setting("fx_usd_eur", default=0.92)) if market == "US" else 1.0
    tax_pct = _f(get_setting("tax_provision_pct", default=12.3))

    ct = cash_total(db)
    invested = capital_invested(db)
    locked = computed_cash_locked(db)
    active = accounting.cash_active(ct, locked)
    op_capital = accounting.operational_capital(active, invested)

    realized = accounting.realized_profit_net(_sell_pairs(db), _isolated_fees(db))
    turnover = _turnover(db)
    tax = accounting.tax_provision(turnover, tax_pct)

    # Rotation mensuelle (base COGS) : Σ cost_basis vendus sur 30 j / capital investi.
    month_ago = now - dt.timedelta(days=30)
    cogs_month = _f(
        db.scalar(
            select(func.coalesce(func.sum(Transaction.cost_basis), 0)).where(
                Transaction.tx_type == "sell", Transaction.occurred_at >= month_ago
            )
        )
    )
    rotation = accounting.capital_rotation_rate(cogs_month, invested)

    pv = accounting.total_portfolio_value(ct, _market_values(db, market=market, fx=fx))

    return {
        "cash_total": round(ct, 2),
        "cash_locked": round(locked, 2),
        "cash_active": round(active, 2),
        "capital_invested": round(invested, 2),
        "operational_capital": round(op_capital, 2),
        "realized_profit_net": round(realized, 2),
        "capital_rotation_rate": round(rotation, 4) if rotation is not None else None,
        "turnover_cumulative": round(turnover, 2),
        "tax_provision": round(tax, 2),
        "total_portfolio_value": round(pv, 2),
    }
