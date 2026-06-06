"""Handlers d'interactions Discord → mutations backend.

Appelés par le bot (adapter) à la réception d'un clic/soumission de modal. Chaque
handler est **idempotent** (rejouer le clic ne refait rien) et **atomique**
(transaction unique). Aucune dépendance discord.py : le bot passe des valeurs
simples (alert_id, prix, frais).
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.config import get_setting
from app.domain import accounting
from app.models import Alert, Lot, Position, SourcingListing, Transaction
from app.services.tier_state import set_current_tier

logger = logging.getLogger("services.interactions")

#: action de vente → drapeau d'étape posé à l'exécution.
_STAGE_FLAG = {
    "capital_secured": "stage_capital_secured",
    "structured": "stage_structured",
    "forced": "stage_forced",
}

#: Statuts d'alerte considérés comme déjà traités (idempotence).
TERMINAL_STATUSES = {"acknowledged", "dismissed"}


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _already(alert: Alert) -> dict:
    return {"status": "already_processed", "alert_status": alert.status}


def handle_buy_purchased(
    db: Session,
    alert_id: int,
    *,
    price_paid: float,
    fees: float = 0.0,
) -> dict:
    """[Acheté] : crée lot + transaction d'achat, listing 'bought', alerte ack."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        return {"status": "not_found"}
    if alert.status in TERMINAL_STATUSES:
        return _already(alert)

    listing = (
        db.get(SourcingListing, alert.sourcing_listing_id)
        if alert.sourcing_listing_id
        else None
    )
    now = _utcnow()

    lot = Lot(
        source_listing_id=listing.id if listing else None,
        total_cost=price_paid,
        currency=listing.currency if listing else "EUR",
        platform=listing.platform if listing else None,
        purchased_at=now,
        status="received",
        label=listing.raw_title[:255] if listing else None,
    )
    db.add(lot)
    db.flush()  # obtient lot.id

    db.add(
        Transaction(
            tx_type="buy",
            lot_id=lot.id,
            quantity=1,
            gross_amount=price_paid,
            platform_fees=fees,
            net_amount=-(price_paid + fees),  # sortie de cash
            currency=lot.currency,
            platform=lot.platform,
            occurred_at=now,
        )
    )

    if listing is not None:
        listing.status = "bought"
    alert.status = "acknowledged"

    db.commit()
    logger.info("Achat enregistré : alert=%s lot=%s coût=%.2f frais=%.2f", alert_id, lot.id, price_paid, fees)
    return {"status": "ok", "lot_id": lot.id, "total_cost": price_paid + fees}


def handle_ignore(db: Session, alert_id: int) -> dict:
    """[Ignorer] : listing 'dismissed', alerte 'dismissed'."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        return {"status": "not_found"}
    if alert.status in TERMINAL_STATUSES:
        return _already(alert)

    if alert.sourcing_listing_id:
        listing = db.get(SourcingListing, alert.sourcing_listing_id)
        if listing is not None:
            listing.status = "dismissed"
    alert.status = "dismissed"
    db.commit()
    return {"status": "ok"}


def handle_sell_executed(
    db: Session,
    alert_id: int,
    *,
    gross_amount: float,
    fees: float = 0.0,
    qty: int,
) -> dict:
    """[Exécutée] : crée la transaction de vente, met à jour la position, pose le
    ``stage_*`` correspondant et applique le 30/70. Atomique + idempotent."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        return {"status": "not_found"}
    if alert.status in TERMINAL_STATUSES:
        return _already(alert)

    position = db.get(Position, alert.position_id) if alert.position_id else None
    if position is None:
        return {"status": "no_position"}

    payload = alert.payload or {}
    qty = min(int(qty), position.quantity)
    avg_cost = float(position.avg_cost)
    cost_basis = avg_cost * qty
    net_amount = gross_amount - fees
    now = _utcnow()

    db.add(
        Transaction(
            tx_type="sell",
            product_id=position.product_id,
            position_id=position.id,
            lot_id=position.lot_id,
            quantity=qty,
            gross_amount=gross_amount,
            platform_fees=fees,
            net_amount=net_amount,  # +(brut − frais)
            cost_basis=cost_basis,
            currency="EUR",
            occurred_at=now,
        )
    )

    position.quantity -= qty
    position.status = "sold" if position.quantity <= 0 else "partially_sold"

    # Pose les drapeaux d'étape — UNIQUEMENT ici, après exécution.
    for stage in payload.get("stages_to_set", []):
        flag = _STAGE_FLAG.get(stage)
        if flag:
            setattr(position, flag, 1)
    if payload.get("action") == "structured_25_50_25" and payload.get("speculative_reserve_qty"):
        position.is_speculative_reserve = 1

    # 30/70 : verrouille une part du bénéfice positif (cash_locked recalculé au ledger).
    profit = net_amount - cost_basis
    locked = accounting.lock_increment(
        profit,
        reinvest_lock_pct=float(get_setting("reinvest_lock_pct", default=30)),
        lock_only_positive=bool(get_setting("lock_only_positive_profit", default=True)),
    )
    if locked > 0:
        db.add(
            Alert(
                alert_type="reinvest",
                severity="info",
                status="pending",
                product_id=position.product_id,
                position_id=position.id,
                title="Verrouillage 30/70",
                payload={"locked": round(locked, 2), "profit": round(profit, 2)},
            )
        )

    alert.status = "acknowledged"
    db.commit()
    logger.info("Vente exécutée : alert=%s qty=%s profit=%.2f locked=%.2f", alert_id, qty, profit, locked)
    return {
        "status": "ok",
        "qty_sold": qty,
        "net_amount": round(net_amount, 2),
        "cost_basis": round(cost_basis, 2),
        "profit": round(profit, 2),
        "locked": round(locked, 2),
        "position_status": position.status,
    }


def handle_palier_confirm(db: Session, alert_id: int) -> dict:
    """[Confirmer] palier : applique la promotion (active le handler J4)."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        return {"status": "not_found"}
    if alert.status in TERMINAL_STATUSES:
        return _already(alert)
    target = (alert.payload or {}).get("target_tier")
    if target is not None:
        set_current_tier(db, int(target))
    alert.status = "acknowledged"
    db.commit()
    logger.info("Palier confirmé : alert=%s → tier %s", alert_id, target)
    return {"status": "ok", "target_tier": target}


def handle_palier_later(db: Session, alert_id: int) -> dict:
    """[Plus tard] : laisse l'alerte en attente (no-op idempotent)."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        return {"status": "not_found"}
    return {"status": "ok", "alert_status": alert.status}
