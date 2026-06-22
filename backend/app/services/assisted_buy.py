"""Achat ASSISTÉ (Phase C) — carting + deep-link ; l'humain finalise (paiement + 3DS).

NON-OBJECTIFS (jamais implémentés) : paiement automatique, contournement 3DS/SCA,
stockage de moyens de paiement, contournement anti-bot au checkout. On ajoute au
panier sur la **session connectée de l'utilisateur** puis on pousse un deep-link
vers le panier pré-rempli — c'est tout.

Garde-fous : kill-switch global, allow-list (``buy_rules``), plafond prix (anti-
scalp : prix gonflé → on ne carte PAS), cap quantité, dry-run, idempotence,
audit (``buy_attempts``). Carting bloqué (anti-bot) → dégrade en deep-link produit.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.models import Alert, BuyAttempt, BuyRule, RetailOffer, Retailer

logger = logging.getLogger("services.assisted_buy")

#: ``cart_poster(template, cookie, url, sku, qty) -> cart_url`` — injectable en test.
#: Lève ``CartBlocked`` si l'ajout panier échoue (anti-bot, session expirée…).
CartPoster = Callable[..., str]


class CartBlocked(Exception):
    pass


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _default_cart_poster(template: str, cookie: str, *, url: str, sku: str | None,
                         qty: int, cart_view: str) -> str:
    """POST d'ajout panier sur la session de l'utilisateur (cookie fourni). Renvoie
    le deep-link panier. Échec HTTP → ``CartBlocked`` (jamais d'acharnement)."""
    add_url = (template.replace("{sku}", str(sku or "")).replace("{qty}", str(qty))
               .replace("{url}", url))
    try:
        resp = httpx.post(add_url, headers={"Cookie": cookie, "Accept": "application/json"},
                          timeout=15.0)
    except httpx.HTTPError as exc:
        raise CartBlocked(str(exc)) from exc
    if resp.status_code >= 400:
        raise CartBlocked(f"http_{resp.status_code}")
    return cart_view


def find_active_rule(db: Session, offer: RetailOffer) -> BuyRule | None:
    """Règle active correspondant à l'offre (scope offer puis product_type)."""
    rules = db.scalars(select(BuyRule).where(BuyRule.is_enabled == 1)).all()
    for r in rules:
        if r.retailer_id is not None and r.retailer_id != offer.retailer_id:
            continue
        if r.scope == "offer" and r.scope_value == str(offer.id):
            return r
    for r in rules:
        if r.retailer_id is not None and r.retailer_id != offer.retailer_id:
            continue
        if r.scope == "product_type" and r.scope_value == (offer.product_type or ""):
            return r
    return None


def _alert(db: Session, *, offer: RetailOffer, retailer: Retailer, status: str,
           qty: int, cart_url: str | None, reason: str | None) -> None:
    price = float(offer.current_price) if offer.current_price is not None else None
    if status in ("carted", "dry_run"):
        head = "🛒 Ajouté au panier" + (" [simulé]" if status == "dry_run" else "")
        msg = (f"{head} chez {retailer.name} — {price} {offer.currency} ×{qty}. "
               f"Finalise ici (TU fais le paiement + 3DS).")
    else:  # blocked → deep-link produit
        msg = (f"⚠️ Carting indisponible chez {retailer.name} ({reason}). "
               f"Lien produit ci-dessous — fais-le à la main.")
    db.add(Alert(
        alert_type="restock", severity="warning", status="pending",
        title=offer.title or offer.url,
        payload={"subtype": "ASSISTED_BUY", "retailer": retailer.name,
                 "buy_status": status, "quantity": qty, "price": price,
                 "currency": offer.currency, "url": offer.url,
                 "cart_url": cart_url or offer.url, "reason": reason, "message": msg},
    ))


def _recent_attempt(db: Session, offer_id: int, now: dt.datetime, cooldown_min: int) -> bool:
    cutoff = now - dt.timedelta(minutes=cooldown_min)
    return db.scalar(select(BuyAttempt.id).where(
        BuyAttempt.offer_id == offer_id,
        BuyAttempt.status.in_(("carted", "dry_run")),
        BuyAttempt.created_at >= cutoff,
    )) is not None


def attempt_buy(db: Session, *, offer: RetailOffer, retailer: Retailer,
                rule: BuyRule | None = None, cart_poster: CartPoster | None = None,
                now: dt.datetime | None = None) -> dict:
    """Tente le carting d'une offre sous garde-fous. Renvoie ``{status, reason}``.
    N'effectue **jamais** de paiement."""
    now = now or _utcnow()
    if not bool(get_setting("assisted_buy_enabled", default=False)):
        return {"status": "disabled"}  # kill-switch

    rule = rule or find_active_rule(db, offer)
    if rule is None:
        return {"status": "no_rule"}  # allow-list : rien hors règle active

    cooldown = int(get_setting("retail_restock_cooldown_min", default=360))
    if _recent_attempt(db, offer.id, now, cooldown):
        return {"status": "duplicate"}  # idempotence

    qty = max(1, int(rule.max_quantity))
    price = offer.current_price
    # Plafond prix (anti-scalp) : prix manquant ou gonflé → on NE carte PAS.
    if price is None or float(price) > float(rule.max_price):
        db.add(BuyAttempt(offer_id=offer.id, channel="online", status="skipped",
                          reason="price_ceiling"))
        db.commit()
        return {"status": "skipped", "reason": "price_ceiling"}

    dry = bool(get_setting("assisted_buy_dry_run", default=True))
    cookie = str(get_setting(f"assisted_buy_cookie_{retailer.code}", default="") or "")
    template = retailer.cart_add_url_template
    cart_view = retailer.cart_view_url or offer.url

    if dry:
        db.add(BuyAttempt(offer_id=offer.id, channel="online", status="dry_run", cart_url=cart_view))
        _alert(db, offer=offer, retailer=retailer, status="dry_run", qty=qty,
               cart_url=cart_view, reason=None)
        db.commit()
        return {"status": "dry_run"}

    if not template or not cookie:  # pas d'endpoint / pas de session → deep-link
        reason = "no_endpoint" if not template else "no_session"
        db.add(BuyAttempt(offer_id=offer.id, channel="online", status="blocked",
                          cart_url=offer.url, reason=reason))
        _alert(db, offer=offer, retailer=retailer, status="blocked", qty=qty,
               cart_url=offer.url, reason=reason)
        db.commit()
        return {"status": "blocked", "reason": reason}

    poster = cart_poster or _default_cart_poster
    try:
        cart_url = poster(template, cookie, url=offer.url, sku=offer.retailer_sku,
                          qty=qty, cart_view=cart_view)
    except CartBlocked as exc:  # anti-bot / session → dégrade en deep-link
        db.add(BuyAttempt(offer_id=offer.id, channel="online", status="blocked",
                          cart_url=offer.url, reason=str(exc)[:128]))
        _alert(db, offer=offer, retailer=retailer, status="blocked", qty=qty,
               cart_url=offer.url, reason="anti_bot")
        db.commit()
        logger.warning("assisted_buy: carting bloqué (%s) — deep-link.", exc)
        return {"status": "blocked", "reason": "anti_bot"}

    db.add(BuyAttempt(offer_id=offer.id, channel="online", status="carted", cart_url=cart_url))
    _alert(db, offer=offer, retailer=retailer, status="carted", qty=qty,
           cart_url=cart_url, reason=None)
    db.commit()
    return {"status": "carted", "cart_url": cart_url}
