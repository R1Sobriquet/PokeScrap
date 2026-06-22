"""Job ``retail-check-store-stock`` — dispo en magasin (PokéStock FR Phase B).

Pour chaque ``(offre watchée × magasin watché)`` d'une enseigne ayant un endpoint
de dispo magasin : fetch → diff → transition vers ``in_store``/``limited`` → écrit
``retail_stock_events`` (avec ``store_id``) + alerte **mentionnant le magasin**
(Discord + Telegram). Dédup/cooldown par ``(offre, magasin)``. Volume capé
(watched×watched, plafond/run, token bucket, circuit breaker). Plus lent que le
hot online. Tout derrière ``retail_sourcing_enabled`` + ``retail_store_stock_enabled``
+ dry-run.
"""

from __future__ import annotations

import datetime as dt
import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.models import (
    Alert,
    OfferStoreAvailability,
    Retailer,
    RetailOffer,
    RetailStockEvent,
    StoreLocation,
)
from app.retail import politeness
from app.retail.domain import Retailer as RetailerDC
from app.retail.fetch import HttpRetailSource, RetailBlocked, httpx_get

logger = logging.getLogger("services.retail_store_jobs")

_STORE_IN = ("in_store", "limited")          # états « dispo en magasin »
_STORE_FROM = ("out_of_store", "unknown")    # transition depuis


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _to_dc(r: Retailer) -> RetailerDC:
    return RetailerDC(code=r.code, name=r.name, base_url=r.base_url,
                      sitemap_url=r.sitemap_url, is_active=bool(r.is_active))


def _due(osa: OfferStoreAvailability | None, interval_min: int, now: dt.datetime) -> bool:
    if osa is None or osa.last_checked_at is None:
        return True
    return osa.last_checked_at <= now - dt.timedelta(minutes=interval_min)


def _recent_store_restock(db: Session, offer_id: int, store_id: int,
                          cooldown_min: int, now: dt.datetime) -> bool:
    cutoff = now - dt.timedelta(minutes=cooldown_min)
    return db.scalar(select(RetailStockEvent.id).where(
        RetailStockEvent.offer_id == offer_id, RetailStockEvent.store_id == store_id,
        RetailStockEvent.to_state.in_(_STORE_IN), RetailStockEvent.detected_at >= cutoff,
    )) is not None


def _create_store_alert(db: Session, *, offer: RetailOffer, retailer_name: str,
                        store: StoreLocation, state: str, price, severity: str) -> None:
    loc = f"{store.name}" + (f" ({store.city})" if store.city else "")
    db.add(Alert(
        alert_type="restock", severity=severity, status="pending",
        title=offer.title or offer.url,
        payload={"subtype": "STORE", "retailer": retailer_name,
                 "store": loc, "store_city": store.city,
                 "stock_state": state, "price": float(price) if price is not None else None,
                 "currency": offer.currency, "url": offer.url, "offer_id": offer.id,
                 "store_id": store.id,
                 "message": f"Dispo en magasin chez {retailer_name} — {loc}."},
    ))


def run_check_store_stock(db: Session, *, http_get=None) -> dict:
    if not bool(get_setting("retail_sourcing_enabled", default=False)):
        return {"summary": "sourcing désactivé (retail_sourcing_enabled=false)"}
    if not bool(get_setting("retail_store_stock_enabled", default=False)):
        return {"summary": "veille magasin désactivée (retail_store_stock_enabled=false)"}

    dry = bool(get_setting("retail_dry_run", default=True))
    cap = int(get_setting("retail_store_request_cap_per_run", default=30))
    interval = int(get_setting("retail_store_check_interval_min", default=60))
    cooldown = int(get_setting("retail_restock_cooldown_min", default=360))
    max_err = int(get_setting("retail_circuit_max_errors", default=5))
    cooldown_cap = int(get_setting("scrape_blocked_cooldown_min", default=120))
    min_delay = int(get_setting("retail_min_delay_ms", default=3000))
    bucket_cap = int(get_setting("retail_bucket_capacity", default=12))
    bucket_refill = float(get_setting("retail_bucket_refill_per_sec", default=0.25))

    budget = politeness.RequestBudget(cap)
    now = _utcnow()
    stats = {"checked": 0, "transitions": 0, "alerts": 0, "blocked": 0, "skipped": 0}

    retailers = [r for r in db.scalars(select(Retailer).where(Retailer.is_active == 1)).all()
                 if r.store_availability_url_template
                 and bool(get_setting(f"retail_{r.code}_enabled", default=False))]

    for retailer in retailers:
        if politeness.circuit_open(db, retailer.code, now, max_err):
            stats["blocked"] += 1
            continue
        source = HttpRetailSource(_to_dc(retailer), http_get=http_get or httpx_get)
        stores = db.scalars(select(StoreLocation).where(
            StoreLocation.retailer_id == retailer.id, StoreLocation.is_watched == 1)).all()
        offers = db.scalars(select(RetailOffer).where(
            RetailOffer.retailer_id == retailer.id, RetailOffer.is_watched == 1)).all()
        if not stores or not offers:
            continue

        for offer in offers:
            blocked = False
            for store in stores:
                osa = db.scalar(select(OfferStoreAvailability).where(
                    OfferStoreAvailability.offer_id == offer.id,
                    OfferStoreAvailability.store_id == store.id))
                if not _due(osa, interval, now):
                    continue
                if not budget.allow():
                    logger.info("store: plafond de requêtes atteint (%s).", cap)
                    blocked = True
                    break
                if not politeness.take_token(db, retailer.code, now,
                                             capacity=bucket_cap, refill_per_sec=bucket_refill):
                    blocked = True
                    break
                try:
                    result, _etag = source.fetch_store_availability(
                        offer.url, template=retailer.store_availability_url_template,
                        sku=offer.retailer_sku, store_code=store.store_code)
                except RetailBlocked as exc:
                    politeness.record_retailer_error(db, retailer.code, now, cooldown_cap_min=cooldown_cap)
                    logger.warning("store: %s bloqué (%s) — circuit breaker.", retailer.code, exc.reason)
                    stats["blocked"] += 1
                    blocked = True
                    break
                except Exception:  # noqa: BLE001
                    logger.exception("store: échec fetch %s @ %s", offer.url, store.store_code)
                    stats["skipped"] += 1
                    continue

                politeness.clear_retailer_errors(db, retailer.code)
                if result is None:  # 304 inchangé
                    if osa is not None:
                        osa.last_checked_at = now
                    db.commit()
                    continue
                state, price = result
                stats["checked"] += 1

                if osa is None:
                    osa = OfferStoreAvailability(offer_id=offer.id, store_id=store.id,
                                                 availability_state="unknown")
                    db.add(osa)
                prev = osa.availability_state
                osa.availability_state = state
                if price is not None:
                    osa.price = price
                osa.last_checked_at = now

                if prev in _STORE_FROM and state in _STORE_IN:
                    stats["transitions"] += 1
                    osa.last_changed_at = now
                    db.add(RetailStockEvent(offer_id=offer.id, store_id=store.id,
                                            from_state=prev, to_state=state, price=price,
                                            detected_at=now))
                    if not dry and not _recent_store_restock(db, offer.id, store.id, cooldown, now):
                        _create_store_alert(db, offer=offer, retailer_name=retailer.name,
                                             store=store, state=state, price=price, severity="warning")
                        stats["alerts"] += 1
                db.commit()
                delay = politeness.jittered_delay_s(min_delay)
                if delay:
                    time.sleep(delay)
            if blocked:
                break

    mode = " [dry-run]" if dry else ""
    stats["summary"] = (f"{stats['checked']} checks magasin / {stats['transitions']} transitions "
                        f"/ {stats['alerts']} alertes / {stats['blocked']} bloqués{mode}")
    return stats
