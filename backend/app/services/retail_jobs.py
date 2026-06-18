"""Jobs PokéStock FR : check-restocks / detect-new-skus / refresh-prices.

Branchés sur le registre ``JOBS`` (verrou ``job_runs``) et le scheduler. La
notification réutilise le pipeline existant : on crée une ligne ``alerts``
(type ``restock``/``new_sku``) que le dispatcher du bot pousse vers Discord +
Telegram. La dédup restock est portée ICI (transition réelle + cooldown), pas
dans le dispatcher.

Politesse OBLIGATOIRE : robots.txt, UA réaliste, délai + jitter, plafond de
requêtes/run, backoff + circuit breaker (réutilise ``scrape_state``). Tout est
derrière ``retail_sourcing_enabled`` + flag par détaillant + ``retail_dry_run``.
"""

from __future__ import annotations

import datetime as dt
import logging
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.models import Alert, RetailOffer, RetailStockEvent, Retailer
from app.retail import politeness
from app.retail import sitemap as sm
from app.retail.domain import RESTOCK_FROM, RESTOCK_TO, Retailer as RetailerDC
from app.retail.fetch import HttpGet, HttpRetailSource, RetailBlocked, httpx_get
from app.scraping.antibot import classify_block

logger = logging.getLogger("services.retail_jobs")

#: Détaillants exclus du radar catalogue (sitemap) : checks watchlist-only.
CATALOG_SCAN_EXCLUDE = {"fnac"}  # WAF agressif → jamais tout le catalogue
_NEW_SKU_ALERT_CAP = 15  # anti-flood sur la 1re découverte de catalogue


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _to_dc(r: Retailer) -> RetailerDC:
    return RetailerDC(code=r.code, name=r.name, base_url=r.base_url,
                      sitemap_url=r.sitemap_url, is_active=bool(r.is_active))


def _active_retailers(db: Session) -> list[Retailer]:
    """Détaillants ``is_active`` ET activés par leur flag settings."""
    rows = db.scalars(select(Retailer).where(Retailer.is_active == 1)).all()
    return [r for r in rows if bool(get_setting(f"retail_{r.code}_enabled", default=False))]


def _sourcing_off() -> bool:
    return not bool(get_setting("retail_sourcing_enabled", default=False))


def create_retail_alert(db: Session, *, kind: str, offer: RetailOffer, retailer_name: str,
                        severity: str = "warning") -> Alert:
    """Crée une alerte pending (type ``restock``/``new_sku``) pour le dispatcher."""
    alert_type = "restock" if kind == "RESTOCK" else "new_sku"
    price = float(offer.current_price) if offer.current_price is not None else None
    label = "De retour en stock" if kind == "RESTOCK" else "Nouveau produit détecté"
    payload = {
        "subtype": kind,
        "retailer": retailer_name,
        "stock_state": offer.current_stock_state,
        "price": price,
        "currency": offer.currency,
        "url": offer.url,
        "offer_id": offer.id,
        "message": f"{label} chez {retailer_name}.",
    }
    # severity décidée par l'appelant AVANT tout flush (un get_setting ici, après
    # un flush, romprait la transaction sur StaticPool en test). Restock = urgent.
    alert = Alert(
        alert_type=alert_type,
        severity=severity,
        status="pending",
        title=offer.title or offer.url,
        payload=payload,
    )
    db.add(alert)
    return alert


def _recent_restock(db: Session, offer_id: int, cooldown_min: int, now: dt.datetime) -> bool:
    """Vrai si une transition restock a déjà été enregistrée récemment (cooldown)."""
    cutoff = now - dt.timedelta(minutes=cooldown_min)
    stmt = select(RetailStockEvent.id).where(
        RetailStockEvent.offer_id == offer_id,
        RetailStockEvent.to_state.in_(tuple(RESTOCK_TO)),
        RetailStockEvent.detected_at >= cutoff,
    )
    return db.scalar(stmt) is not None


def _is_flapping(db: Session, offer_id: int, debounce_min: int, now: dt.datetime) -> bool:
    """Anti-flapping : ≥2 transitions d'état dans la fenêtre debounce = oscillation."""
    if debounce_min <= 0:
        return False
    cutoff = now - dt.timedelta(minutes=debounce_min)
    n = db.scalar(select(func.count()).select_from(RetailStockEvent).where(
        RetailStockEvent.offer_id == offer_id,
        RetailStockEvent.detected_at >= cutoff,
    )) or 0
    return int(n) >= 2


def _due_for_check(offer: RetailOffer, interval_min: int, now: dt.datetime) -> bool:
    """Respecte l'intervalle min entre deux checks d'une même offre (économie requêtes)."""
    if offer.last_checked_at is None:
        return True
    return offer.last_checked_at <= now - dt.timedelta(minutes=interval_min)


def _scan_watched(db: Session, *, alert: bool, http_get: HttpGet | None = None) -> dict:
    """Cœur partagé check-restocks / refresh-prices : fetch des offres watchées."""
    if _sourcing_off():
        return {"summary": "sourcing désactivé (retail_sourcing_enabled=false)"}

    dry = bool(get_setting("retail_dry_run", default=True))
    cap = int(get_setting("retail_request_cap_per_run", default=40))
    min_delay = int(get_setting("retail_min_delay_ms", default=3000))
    interval = int(get_setting("retail_check_interval_min", default=60))
    cooldown = int(get_setting("retail_restock_cooldown_min", default=360))
    debounce = int(get_setting("restock_debounce_min", default=30))
    max_err = int(get_setting("retail_circuit_max_errors", default=5))
    cooldown_cap = int(get_setting("scrape_blocked_cooldown_min", default=120))

    budget = politeness.RequestBudget(cap)
    now = _utcnow()
    stats = {"checked": 0, "transitions": 0, "alerts": 0, "blocked": 0, "skipped": 0}

    for retailer in _active_retailers(db):
        if politeness.circuit_open(db, retailer.code, now, max_err):
            logger.info("retail: circuit ouvert pour %s — détaillant ignoré.", retailer.code)
            stats["blocked"] += 1
            continue
        source = HttpRetailSource(_to_dc(retailer), http_get=http_get or httpx_get)
        offers = db.scalars(
            select(RetailOffer).where(
                RetailOffer.retailer_id == retailer.id, RetailOffer.is_watched == 1
            )
        ).all()
        for offer in offers:
            if not _due_for_check(offer, interval, now):
                continue
            if not budget.allow():
                logger.info("retail: plafond de requêtes atteint (%s).", cap)
                break
            try:
                snap = source.fetch_offer(offer.url)
            except RetailBlocked as exc:
                mins = politeness.record_retailer_error(
                    db, retailer.code, now, cooldown_cap_min=cooldown_cap
                )
                logger.warning(
                    "retail: %s bloqué (%s) — backoff %s min, circuit breaker.",
                    retailer.code, exc.reason, mins,
                )
                stats["blocked"] += 1
                break  # on arrête ce détaillant pour ce run
            except Exception:  # noqa: BLE001 - une page KO ne casse pas le run
                logger.exception("retail: échec fetch %s", offer.url)
                stats["skipped"] += 1
                continue

            politeness.clear_retailer_errors(db, retailer.code)
            stats["checked"] += 1
            prev_state = offer.current_stock_state
            transitioned = _apply_snapshot(offer, snap, now)

            is_restock = (
                prev_state in RESTOCK_FROM and offer.current_stock_state in RESTOCK_TO
            )
            if is_restock:
                stats["transitions"] += 1
                db.add(RetailStockEvent(
                    offer_id=offer.id, from_state=prev_state,
                    to_state=offer.current_stock_state, price=offer.current_price,
                    detected_at=now,
                ))
                offer.last_changed_at = now
                if (alert and not dry and not _recent_restock(db, offer.id, cooldown, now)
                        and not _is_flapping(db, offer.id, debounce, now)):
                    db.flush()  # garantit offer.id pour le payload
                    create_retail_alert(db, kind="RESTOCK", offer=offer, retailer_name=retailer.name)
                    stats["alerts"] += 1
            elif transitioned:
                db.add(RetailStockEvent(
                    offer_id=offer.id, from_state=prev_state,
                    to_state=offer.current_stock_state, price=offer.current_price,
                    detected_at=now,
                ))
                offer.last_changed_at = now

            db.commit()
            delay = politeness.jittered_delay_s(min_delay)
            if delay:
                time.sleep(delay)

    mode = " [dry-run]" if dry else ""
    stats["summary"] = (
        f"{stats['checked']} vérifiées / {stats['transitions']} transitions / "
        f"{stats['alerts']} alertes / {stats['blocked']} bloqués{mode}"
    )
    return stats


def _apply_snapshot(offer: RetailOffer, snap, now: dt.datetime) -> bool:
    """Met à jour l'offre depuis un snapshot ; renvoie True si l'état a changé."""
    changed = snap.stock_state != offer.current_stock_state
    offer.current_stock_state = snap.stock_state
    if snap.price is not None:
        offer.current_price = snap.price
    if snap.currency:
        offer.currency = snap.currency
    if snap.title and not offer.title:
        offer.title = snap.title[:255]
    if snap.image and not offer.image_url:
        offer.image_url = snap.image[:512]
    offer.last_checked_at = now
    return changed


# ------------------------------------------------------------------ runners
def run_check_restocks(db: Session, *, http_get: HttpGet | None = None) -> dict:
    return _scan_watched(db, alert=True, http_get=http_get)


def run_refresh_prices(db: Session, *, http_get: HttpGet | None = None) -> dict:
    return _scan_watched(db, alert=False, http_get=http_get)


def run_backfill_images(db: Session, *, http_get: HttpGet | None = None) -> dict:
    """Backfill ponctuel : récupère l'image des offres sans ``image_url``.

    Réutilise la politesse complète (cap requêtes/run, délai+jitter, circuit
    breaker). Aucune alerte : insensible au dry-run, mais gardé par
    ``retail_sourcing_enabled`` + flag par détaillant (comme tout fetch).
    """
    if _sourcing_off():
        return {"summary": "sourcing désactivé (retail_sourcing_enabled=false)"}

    cap = int(get_setting("retail_request_cap_per_run", default=40))
    min_delay = int(get_setting("retail_min_delay_ms", default=3000))
    max_err = int(get_setting("retail_circuit_max_errors", default=5))
    cooldown_cap = int(get_setting("scrape_blocked_cooldown_min", default=120))

    budget = politeness.RequestBudget(cap)
    now = _utcnow()
    stats = {"scanned": 0, "images": 0, "blocked": 0, "skipped": 0}

    for retailer in _active_retailers(db):
        if politeness.circuit_open(db, retailer.code, now, max_err):
            stats["blocked"] += 1
            continue
        source = HttpRetailSource(_to_dc(retailer), http_get=http_get or httpx_get)
        offers = db.scalars(
            select(RetailOffer).where(
                RetailOffer.retailer_id == retailer.id, RetailOffer.image_url.is_(None)
            )
        ).all()
        for offer in offers:
            if not budget.allow():
                logger.info("retail backfill: plafond de requêtes atteint (%s).", cap)
                break
            try:
                snap = source.fetch_offer(offer.url)
            except RetailBlocked as exc:
                mins = politeness.record_retailer_error(
                    db, retailer.code, now, cooldown_cap_min=cooldown_cap
                )
                logger.warning("retail backfill: %s bloqué (%s) — backoff %s min.",
                               retailer.code, exc.reason, mins)
                stats["blocked"] += 1
                break
            except Exception:  # noqa: BLE001 - une page KO ne casse pas le run
                logger.exception("retail backfill: échec fetch %s", offer.url)
                stats["skipped"] += 1
                continue

            politeness.clear_retailer_errors(db, retailer.code)
            stats["scanned"] += 1
            if snap.image:
                offer.image_url = snap.image[:512]
                if snap.title and not offer.title:
                    offer.title = snap.title[:255]
                offer.last_checked_at = now
                stats["images"] += 1
            db.commit()
            delay = politeness.jittered_delay_s(min_delay)
            if delay:
                time.sleep(delay)

    stats["summary"] = (
        f"{stats['scanned']} vérifiées / {stats['images']} images / {stats['blocked']} bloqués"
    )
    return stats


def _list_skus_cached(db: Session, retailer: Retailer, http_get: HttpGet,
                      budget: politeness.RequestBudget) -> tuple[list, bool]:
    """Lit le sitemap (conditionnel ETag/Last-Modified) → (skus produits, modifié?)."""
    if not retailer.sitemap_url or not budget.allow():
        return [], False
    cache = sm.load_cache(db)
    headers = {**politeness.default_headers(), **sm.conditional_headers(cache, retailer.code)}
    status, text, resp_headers = http_get(retailer.sitemap_url, headers)
    if status == 304:
        logger.info("retail: sitemap %s inchangé (304).", retailer.code)
        return [], False
    if classify_block(status, text) or status >= 400:
        raise RetailBlocked(f"http_{status}", status)
    sm.save_cache(db, retailer.code, etag=resp_headers.get("etag"),
                  last_modified=resp_headers.get("last-modified"))
    kind, entries = sm.parse_sitemap(text)
    if kind == "sitemapindex":
        children = sm.filter_product_skus(entries) or list(entries)
        collected: list = []
        for child in children[:3]:
            if not budget.allow():
                break
            st, tx, _ = http_get(child.url, politeness.default_headers())
            if classify_block(st, tx) or st >= 400:
                continue
            _, sub = sm.parse_sitemap(tx)
            collected.extend(sub)
        entries = collected
    return sm.filter_product_skus(entries), True


def run_detect_new_skus(db: Session, *, http_get: HttpGet | None = None) -> dict:
    """Radar nouveaux SKU : diff sitemap vs offres connues → crée + alerte."""
    if _sourcing_off():
        return {"summary": "sourcing désactivé (retail_sourcing_enabled=false)"}

    dry = bool(get_setting("retail_dry_run", default=True))
    cap = int(get_setting("retail_request_cap_per_run", default=40))
    max_err = int(get_setting("retail_circuit_max_errors", default=5))
    cooldown_cap = int(get_setting("scrape_blocked_cooldown_min", default=120))
    # Nouveau SKU = non urgent → digesté (severity info) si le digest est activé.
    sku_severity = "info" if bool(get_setting("alert_digest_enabled", default=False)) else "warning"
    getter = http_get or httpx_get
    budget = politeness.RequestBudget(cap)
    now = _utcnow()
    stats = {"new_offers": 0, "alerts": 0, "blocked": 0, "skipped": 0}

    for retailer in _active_retailers(db):
        if retailer.code in CATALOG_SCAN_EXCLUDE:
            continue  # watchlist-only (Fnac) : pas de crawl catalogue
        if politeness.circuit_open(db, retailer.code, now, max_err):
            stats["blocked"] += 1
            continue
        try:
            skus, modified = _list_skus_cached(db, retailer, getter, budget)
        except RetailBlocked as exc:
            mins = politeness.record_retailer_error(
                db, retailer.code, now, cooldown_cap_min=cooldown_cap
            )
            logger.warning("retail: sitemap %s bloqué (%s) — backoff %s min.",
                           retailer.code, exc.reason, mins)
            stats["blocked"] += 1
            continue
        except Exception:  # noqa: BLE001
            logger.exception("retail: échec sitemap %s", retailer.code)
            stats["skipped"] += 1
            continue
        if not modified:
            continue
        politeness.clear_retailer_errors(db, retailer.code)

        known = set(db.scalars(
            select(RetailOffer.url).where(RetailOffer.retailer_id == retailer.id)
        ).all())
        for sku in skus:
            if budget.remaining <= 0 and stats["new_offers"] >= cap:
                break
            if sku.url in known:
                continue
            offer = RetailOffer(
                retailer_id=retailer.id, url=sku.url[:512],
                title=(sku.title or None), retailer_sku=sku.retailer_sku,
                current_stock_state="unknown", first_seen_at=now,
            )
            db.add(offer)
            db.flush()
            known.add(sku.url)
            stats["new_offers"] += 1
            if not dry and stats["alerts"] < _NEW_SKU_ALERT_CAP:
                create_retail_alert(db, kind="NEW_SKU", offer=offer, retailer_name=retailer.name,
                                    severity=sku_severity)
                stats["alerts"] += 1
        db.commit()

    mode = " [dry-run]" if dry else ""
    stats["summary"] = (
        f"{stats['new_offers']} nouveaux SKU / {stats['alerts']} alertes / "
        f"{stats['blocked']} bloqués{mode}"
    )
    return stats
