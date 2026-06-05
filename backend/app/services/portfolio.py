"""État du portefeuille (provisoire Jalon 3) + amorçage du capital.

``portfolio_state`` agrège la base ; le ledger complet (verrouillage 30/70,
réserve spéculative) viendra au Jalon 5. Ici :
  * ``capital_invested`` = Σ ``positions.avg_cost × quantity`` ;
  * ``cash_total``       = Σ ``transactions.net_amount`` ;
  * ``cash_locked = 0``  (pas encore de 30/70) → ``cash_active = cash_total``.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.types import PortfolioState
from app.models import Position, Transaction


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def portfolio_state(db: Session) -> PortfolioState:
    invested = db.scalar(
        select(func.coalesce(func.sum(Position.avg_cost * Position.quantity), 0))
    )
    cash_total = db.scalar(
        select(func.coalesce(func.sum(Transaction.net_amount), 0))
    )
    return PortfolioState(
        cash_active=float(cash_total or 0),
        capital_invested=float(invested or 0),
        cash_locked=0.0,
    )


def record_deposit(
    db: Session,
    amount: float,
    *,
    occurred_at: dt.datetime | None = None,
    notes: str = "Dépôt initial",
) -> Transaction:
    """Insère une transaction d'ajustement pour amorcer le capital cash."""
    tx = Transaction(
        tx_type="adjustment",
        quantity=1,
        gross_amount=amount,
        net_amount=amount,
        currency="EUR",
        occurred_at=occurred_at or _utcnow(),
        notes=notes,
    )
    db.add(tx)
    db.commit()
    return tx
