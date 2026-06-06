"""Module B — intake, segmentation, promotion (couche application = I/O).

Délègue le métier pur à ``domain.liquidation`` (classification, routage, packing
vrac sans doublon). Seul pont B → portefeuille : ``promote_to_position``.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.domain.liquidation import (
    BULK_THEME,
    INDIVIDUAL,
    build_bulk_lots,
    classify_segmentation,
    route_individual,
)
from app.domain.types import LiquidationCard
from app.domain.valuation import net_value
from app.models import Alert, Lot, LotItem, Position, Product, SourcingListing
from app.services.prices import get_latest_price

logger = logging.getLogger("services.liquidation")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _f(v, default=0.0) -> float:
    return float(v) if v is not None else default


def _fee_rates() -> dict:
    return {
        "cardmarket": _f(get_setting("fee_rate_cardmarket", default=5.0)),
        "ebay": _f(get_setting("fee_rate_ebay", default=12.0)),
        "vinted": _f(get_setting("fee_rate_vinted", default=0.0)),
    }


def intake_lot(db: Session, lot_id: int) -> dict:
    """Pré-remplit ``lot_items`` depuis ``detected_products`` du listing source."""
    lot = db.get(Lot, lot_id)
    if lot is None:
        return {"status": "not_found"}

    prefill = bool(get_setting("intake_prefill_from_detection", default=True))
    created = 0
    if prefill and lot.source_listing_id:
        listing = db.get(SourcingListing, lot.source_listing_id)
        existing = bool(db.scalar(select(LotItem.id).where(LotItem.lot_id == lot_id)))
        if listing is not None and not existing:
            for item in listing.detected_products or []:
                db.add(LotItem(
                    lot_id=lot_id,
                    product_id=item.get("product_id"),
                    quantity=int(item.get("qty", 1)),
                    segmentation=INDIVIDUAL,
                    status="pending",
                ))
                created += 1

    lot.status = "processing"
    db.commit()
    logger.info("Intake lot %s : %s items pré-remplis.", lot_id, created)
    return {"status": "ok", "items_prefilled": created}


def _theme_of(product: Product | None) -> str:
    if product is None:
        return "mixte"
    return product.set_slug or product.set_name or "mixte"


def segment_lot(db: Session, lot_id: int) -> dict:
    """Segmente un lot : individuelles routées + lots vrac sans doublon."""
    lot = db.get(Lot, lot_id)
    if lot is None:
        return {"status": "not_found"}

    market = str(get_setting("valuation_market", default="US"))
    fx = _f(get_setting("fx_usd_eur", default=0.92)) if market == "US" else 1.0
    fee_rates = _fee_rates()
    sell_platform = str(get_setting("default_sell_platform", default="cardmarket"))
    individual_threshold = _f(get_setting("individual_threshold", default=5.0))
    individual_ebay_threshold = _f(get_setting("individual_ebay_threshold", default=50.0))

    items = db.scalars(select(LotItem).where(LotItem.lot_id == lot_id)).all()
    identified_bulk: list[LiquidationCard] = []
    individual_count = 0

    for item in items:
        net = None
        if item.product_id is not None:
            snap = get_latest_price(db, item.product_id, market=market)
            if snap is not None and snap.price_avg is not None:
                net = net_value(_f(snap.price_avg) * fx, sell_platform, fee_rates=fee_rates)

        seg = classify_segmentation(item.product_id, net, individual_threshold=individual_threshold)
        if seg == INDIVIDUAL:
            item.segmentation = INDIVIDUAL
            item.estimated_unit_value = round(net, 2)
            item.target_platform = route_individual(
                is_graded=False, net_value=net, individual_ebay_threshold=individual_ebay_threshold
            )
            individual_count += 1
        else:
            item.segmentation = BULK_THEME
            if item.product_id is not None:
                product = db.get(Product, item.product_id)
                identified_bulk.append(
                    LiquidationCard(product_id=item.product_id, qty=item.quantity, theme=_theme_of(product))
                )

    # Cartes non identifiées : items sans product_id + reliquat vs estimated_total_cards.
    unidentified = sum(i.quantity for i in items if i.product_id is None)
    if lot.source_listing_id:
        listing = db.get(SourcingListing, lot.source_listing_id)
        if listing is not None and listing.estimated_total_cards:
            leftover = int(listing.estimated_total_cards) - sum(i.quantity for i in items)
            unidentified += max(0, leftover)

    bins = build_bulk_lots(
        identified_bulk, unidentified,
        strategy=str(get_setting("bulk_theme_strategy", default="set")),
        min_theme=int(_f(get_setting("bulk_min_theme_for_dedicated_lot", default=50))),
        target=int(_f(get_setting("bulk_lot_target_size", default=75))),
        min_size=int(_f(get_setting("bulk_lot_min_size", default=50))),
        max_size=int(_f(get_setting("bulk_lot_max_size", default=100))),
    )

    # Étiquette chaque item vrac identifié avec le 1er bac contenant son produit.
    label_by_product: dict[int, str] = {}
    for b in bins:
        for pid in b.product_ids:
            label_by_product.setdefault(pid, b.label)
    for item in items:
        if item.segmentation == BULK_THEME and item.product_id in label_by_product:
            item.bulk_group_label = label_by_product[item.product_id]

    lot.status = "segmented"
    price_per_card = _f(get_setting("bulk_lot_price_per_card", default=0.10))
    bulk_summary = [
        {"label": b.label, "size": b.size, "suggested_price": round(b.size * price_per_card, 2)}
        for b in bins
    ]
    db.add(Alert(
        alert_type="lot_summary", severity="info", status="pending",
        title=f"Lot {lot_id} segmenté : {individual_count} indiv. + {len(bins)} vrac",
        payload={"lot_id": lot_id, "individuals": individual_count, "bulk_lots": bulk_summary},
    ))
    db.commit()
    logger.info("Segment lot %s : %s indiv, %s lots vrac.", lot_id, individual_count, len(bins))
    return {"status": "ok", "individuals": individual_count, "bulk_lots": len(bins),
            "bulk_summary": bulk_summary}


def promote_to_position(db: Session, lot_item_id: int) -> dict:
    """Promeut un item en position suivie (avg_cost pro-rata) — pont B → portefeuille."""
    item = db.get(LotItem, lot_item_id)
    if item is None:
        return {"status": "not_found"}
    if item.product_id is None:
        return {"status": "no_product"}
    lot = db.get(Lot, item.lot_id)
    if lot is None:
        return {"status": "no_lot"}

    siblings = db.scalars(select(LotItem).where(LotItem.lot_id == item.lot_id)).all()
    total_value = sum(_f(s.estimated_unit_value) for s in siblings)
    if total_value > 0:
        share = _f(item.estimated_unit_value) / total_value
    else:  # pas de valeurs estimées → répartition par quantité
        total_qty = sum(s.quantity for s in siblings) or 1
        share = item.quantity / total_qty

    item_cost = _f(lot.total_cost) * share
    per_unit = item_cost / max(item.quantity, 1)

    position = Position(
        product_id=item.product_id,
        lot_id=lot.id,
        quantity=item.quantity,
        avg_cost=round(per_unit, 2),
        initial_capital_basis=round(item_cost, 2),
        acquired_at=_utcnow(),
        status="held",
    )
    db.add(position)
    db.delete(item)  # retire l'item de la liquidation
    db.commit()
    logger.info("Promotion item %s → position %s (avg_cost=%.2f).", lot_item_id, position.id, per_unit)
    return {"status": "ok", "position_id": position.id, "avg_cost": round(per_unit, 2),
            "quantity": item.quantity}
