"""Flip Radar — opportunités d'achat-revente en continu sur le catalogue watché.

Au-delà de l'événement restock : classe à tout instant les offres watchées par
**flip net** (marché vs MSRP, frais déduits). Le job alerte proactivement quand
une offre EN STOCK franchit un seuil de marge — ce que les alertes de transition
restock ne captent pas (ex. le marché monte alors que le produit est déjà en
stock). Dédup par offre + cooldown. Fonctionne sur PokeTrace même sans le moat.
"""

from __future__ import annotations

import datetime as dt
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting, invalidate_setting
from app.models import Alert, Product, Retailer, RetailOffer, Setting
from app.services.flip_value import flip_for_offer

logger = logging.getLogger("services.flip_radar")

_STATE_KEY = "flip_alert_state"
_IN_STOCK = ("in_stock", "preorder")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _params() -> tuple[float, str, float]:
    return (float(get_setting("fx_usd_eur", default=0.92)),
            str(get_setting("valuation_market", default="US")),
            float(get_setting("resale_fee_pct", default=12)))


def scan_opportunities(db: Session, *, in_stock_only: bool = True,
                       min_net_upside: float | None = None) -> list[dict]:
    """Offres watchées matchées, classées par flip net décroissant."""
    fx, market, fee = _params()
    names = {r.id: r.name for r in db.scalars(select(Retailer)).all()}
    prods = {p.id: p for p in db.scalars(select(Product)).all()}

    stmt = select(RetailOffer).where(RetailOffer.is_watched == 1)
    if in_stock_only:
        stmt = stmt.where(RetailOffer.current_stock_state.in_(_IN_STOCK))

    out: list[dict] = []
    for o in db.scalars(stmt).all():
        flip = flip_for_offer(db, o, fx=fx, market=market, fee_pct=fee)
        net = flip["net_upside_pct"]
        if net is None:
            continue
        if min_net_upside is not None and net < min_net_upside:
            continue
        p = prods.get(o.product_id)
        out.append({
            "offer_id": o.id, "title": o.title, "url": o.url, "image_url": o.image_url,
            "retailer": names.get(o.retailer_id), "stock_state": o.current_stock_state,
            "product_id": o.product_id, "product_name": p.name if p else None,
            **flip,
        })
    out.sort(key=lambda x: x["net_upside_pct"], reverse=True)
    return out


def _load(db: Session) -> dict:
    row = db.scalar(select(Setting).where(Setting.setting_key == _STATE_KEY))
    if row is None or not row.setting_value:
        return {}
    try:
        return json.loads(row.setting_value)
    except json.JSONDecodeError:
        return {}


def _save(db: Session, state: dict) -> None:
    row = db.scalar(select(Setting).where(Setting.setting_key == _STATE_KEY))
    value = json.dumps(state)
    if row is None:
        db.add(Setting(setting_key=_STATE_KEY, setting_value=value, value_type="json",
                       description="État de dédup des alertes Flip Radar (auto)"))
    else:
        row.setting_value = value
    db.commit()
    invalidate_setting(_STATE_KEY)


def run_flip_radar(db: Session) -> dict:
    """Scanne les opportunités en stock ≥ seuil et alerte (dédup + cooldown)."""
    threshold = float(get_setting("flip_alert_min_pct", default=25))
    cooldown = int(get_setting("alert_cooldown_min", default=60))
    dry = bool(get_setting("retail_dry_run", default=True))
    now = _utcnow()

    opps = scan_opportunities(db, in_stock_only=True, min_net_upside=threshold)
    state = _load(db)
    changed = False
    alerts = 0

    for o in opps:
        key = str(o["offer_id"])
        last = state.get(key, {}).get("last_at")
        if last:
            try:
                if (now - dt.datetime.fromisoformat(last)).total_seconds() / 60 < cooldown:
                    continue
            except ValueError:
                pass
        if not dry:
            db.add(Alert(
                alert_type="restock", severity="warning", status="pending",
                title=o["title"] or o["url"],
                payload={"subtype": "FLIP", "retailer": o["retailer"],
                         "stock_state": o["stock_state"], "price": o["retail_price"],
                         "currency": "EUR", "url": o["url"], "offer_id": o["offer_id"],
                         "market_value": o["market_value"], "upside_pct": o["upside_pct"],
                         "net_upside_pct": o["net_upside_pct"], "est_profit": o["est_profit"],
                         "verdict": o["verdict"], "verdict_tone": o["verdict_tone"],
                         "message": f"Opportunité flip chez {o['retailer']} "
                                    f"(+{o['net_upside_pct']}% net, ~{o['est_profit']}€)."},
            ))
            alerts += 1
        state[key] = {"last_at": now.isoformat(), "net": o["net_upside_pct"]}
        changed = True

    if changed:
        _save(db, state)
    else:
        db.commit()
    mode = " [dry-run]" if dry else ""
    return {"opportunities": len(opps), "alerts": alerts,
            "summary": f"{len(opps)} opportunités ≥{threshold}% net / {alerts} alertes{mode}"}
