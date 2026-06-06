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

from app.models import Alert, Lot, SourcingListing, Transaction

logger = logging.getLogger("services.interactions")

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


def handle_palier_confirm(db: Session, alert_id: int) -> dict:
    """[Confirmer] palier : handler prêt, **inerte** jusqu'au Jalon 5.

    Acquitte l'alerte mais n'applique pas encore la transition (la logique de
    palier sera branchée au snapshot KPI du Jalon 5).
    """
    alert = db.get(Alert, alert_id)
    if alert is None:
        return {"status": "not_found"}
    if alert.status in TERMINAL_STATUSES:
        return _already(alert)
    alert.status = "acknowledged"
    db.commit()
    logger.info("Palier confirmé (inerte J4) : alert=%s", alert_id)
    return {"status": "ok", "note": "tier change applied at Jalon 5"}


def handle_palier_later(db: Session, alert_id: int) -> dict:
    """[Plus tard] : laisse l'alerte en attente (no-op idempotent)."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        return {"status": "not_found"}
    return {"status": "ok", "alert_status": alert.status}
