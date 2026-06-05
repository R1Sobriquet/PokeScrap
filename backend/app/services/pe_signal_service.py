"""Job d'accumulation Prismatic Evolutions (réf. S3.5).

Rassemble les signaux (hausse des singles PE auto, flags manuels) et appelle la
fonction pure ``pe_accumulation_signal`` ; si elle se déclenche, écrit une alerte
``buy`` (sous-type ``accumulation_PE``, ``status='pending'``).
"""

from __future__ import annotations

import logging

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.domain.pe_signal import pe_accumulation_signal
from app.models import Alert, Product, Watchlist
from app.services.prices import get_latest_price

logger = logging.getLogger("services.pe_signal")


def _pe_singles_rising(db: Session, market: str, rise_pct: float) -> bool:
    """Vrai si au moins un single PE monte de ≥ ``rise_pct`` (avg_7d vs avg_30d)."""
    stmt = (
        select(Product)
        .join(Watchlist, Watchlist.product_id == Product.id)
        .where(
            Watchlist.is_active == 1,
            Product.product_type == "single",
            or_(
                Product.set_slug.like("%prismatic%"),
                Product.set_name.like("%Prismatic%"),
            ),
        )
    )
    for product in db.scalars(stmt).all():
        snap = get_latest_price(db, product.id, market=market)
        if snap is None or not snap.avg_7d or not snap.avg_30d or snap.avg_30d <= 0:
            continue
        rise = float(snap.avg_7d) / float(snap.avg_30d) - 1
        if rise >= rise_pct / 100.0:
            return True
    return False


def run_pe_accumulation_scan(db: Session) -> dict:
    """Évalue le signal PE et écrit une alerte si déclenché. Idempotence simple :
    on n'ajoute pas de doublon s'il existe déjà une alerte PE pending."""
    market = str(get_setting("valuation_market", default="US"))
    rise_pct = float(get_setting("pe_singles_rise_pct", default=15))
    min_triggers = int(float(get_setting("pe_signal_min_triggers", default=2)))

    result = pe_accumulation_signal(
        singles_rising=_pe_singles_rising(db, market, rise_pct),
        sealed_rising=None,  # scellé non suivi au Jalon 3 (mode prototype)
        reprint_ended=bool(get_setting("pe_reprint_ended", default=False)),
        stock_declining=bool(get_setting("pe_stock_declining", default=False)),
        min_triggers=min_triggers,
    )

    if result.fire:
        existing = db.scalar(
            select(Alert).where(
                Alert.alert_type == "buy",
                Alert.status == "pending",
                Alert.title == "Accumulation Prismatic Evolutions",
            )
        )
        if existing is None:
            db.add(
                Alert(
                    alert_type="buy",
                    severity="info",
                    status="pending",
                    title="Accumulation Prismatic Evolutions",
                    payload={
                        "subtype": "accumulation_PE",
                        "trigger_count": result.trigger_count,
                        "triggers": list(result.triggers),
                    },
                )
            )
            db.commit()
        logger.info("Signal PE déclenché (%s triggers).", result.trigger_count)

    return {
        "fire": result.fire,
        "trigger_count": result.trigger_count,
        "triggers": list(result.triggers),
    }
