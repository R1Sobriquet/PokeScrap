"""Orchestration de la décision d'achat (couche application = I/O).

Rassemble les données (prix via ``get_latest_price``, état du portefeuille,
réglages), appelle les **fonctions pures** de ``domain/``, puis écrit le verdict
sur l'annonce et, si tout passe, une alerte ``buy`` (``status='pending'``). Le
tout dans **une seule transaction**. Aucune décision n'est prise ici : seulement
de la collecte de données et de la persistance.
"""

from __future__ import annotations

import datetime as dt
import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.domain.buying import evaluate_buy, opportunity_score
from app.domain.filters import passes_S4
from app.domain.tiers import cash_min_pct, can_buy, resolve_current_tier
from app.domain.types import (
    DetectedProduct,
    ListingInput,
    PriceInfo,
    TierBand,
    ValuationParams,
)
from app.domain.valuation import net_value, to_eur
from app.models import Alert, Product, SourcingListing, TierConfig, Watchlist
from app.services.portfolio import portfolio_state
from app.services.prices import get_latest_price

logger = logging.getLogger("services.buy_evaluation")

# Valeur sentinelle pour ``sourcing_listings.ratio_pct`` (DECIMAL(6,2), max 9999.99).
# Un ratio au-delà signifie « bien trop cher, bloqué » : la valeur exacte n'a aucune
# importance pour la décision (la règle des 50 % a déjà tranché), seul le stockage
# doit rester dans les bornes de la colonne.
RATIO_PCT_MAX = 9999.99


def _cap_ratio(ratio: float | None) -> float | None:
    return None if ratio is None else min(ratio, RATIO_PCT_MAX)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _f(value, default=0.0) -> float:
    return float(value) if value is not None else default


# ----------------------------------------------------- collecte des données
def _fee_rates() -> dict:
    return {
        "cardmarket": _f(get_setting("fee_rate_cardmarket", default=5.0)),
        "ebay": _f(get_setting("fee_rate_ebay", default=12.0)),
        "vinted": _f(get_setting("fee_rate_vinted", default=0.0)),
    }


def _valuation_params(market: str) -> ValuationParams:
    fx = _f(get_setting("fx_usd_eur", default=0.92)) if market == "US" else 1.0
    return ValuationParams(
        min_match_confidence=_f(get_setting("min_match_confidence", default=0.70)),
        default_sell_platform=str(get_setting("default_sell_platform", default="cardmarket")),
        bulk_value_per_card=_f(get_setting("bulk_value_per_card", default=0.05)),
        vinted_fee_rate=_f(get_setting("fee_rate_vinted", default=0.0)),
        lot_confidence_haircut=_f(get_setting("lot_confidence_haircut", default=0.85)),
        fee_rates=_fee_rates(),
        ir_lot_value_share=_f(get_setting("ir_lot_value_share", default=50)),
        fx=fx,
    )


def _tier_bands(db: Session) -> list[TierBand]:
    rows = db.scalars(select(TierConfig)).all()
    return [
        TierBand(
            tier_number=r.tier_number,
            capital_min=float(r.capital_min),
            capital_max=float(r.capital_max) if r.capital_max is not None else None,
            cash_min_pct=float(r.cash_min_pct),
        )
        for r in rows
    ]


def _detected_products(db: Session, listing: SourcingListing) -> tuple[DetectedProduct, ...]:
    """Construit les DTO produits depuis ``detected_products`` (JSON).

    ``is_illustration_rare`` est pris de l'annonce si fourni, sinon déduit de la
    watchlist du produit.
    """
    raw = listing.detected_products or []
    out: list[DetectedProduct] = []
    for item in raw:
        pid = item.get("product_id")
        if pid is None:
            continue
        is_ir = item.get("is_illustration_rare")
        if is_ir is None:
            watch = db.scalar(select(Watchlist).where(Watchlist.product_id == pid))
            is_ir = bool(watch.is_illustration_rare) if watch else False
        out.append(
            DetectedProduct(
                product_id=pid,
                qty=int(item.get("qty", 1)),
                confidence=float(item.get("confidence", 1.0)),
                is_illustration_rare=bool(is_ir),
            )
        )
    return tuple(out)


def _price_map(db: Session, detected, market: str) -> dict[int, PriceInfo]:
    prices: dict[int, PriceInfo] = {}
    for d in detected:
        snap = get_latest_price(db, d.product_id, market=market)
        if snap is None:
            prices[d.product_id] = PriceInfo(price=None)
        else:
            prices[d.product_id] = PriceInfo(
                price=_f(snap.price_avg, None) if snap.price_avg is not None else None,
                avg_7d=_f(snap.avg_7d, None) if snap.avg_7d is not None else None,
                avg_30d=_f(snap.avg_30d, None) if snap.avg_30d is not None else None,
                sale_count=snap.sale_count,
                approx_sale_count=bool(snap.approx_sale_count),
            )
    return prices


def _value_driver(detected, prices, params: ValuationParams):
    """Produit identifié qui porte le plus de valeur (pour filtres & scoring)."""
    best = None
    best_val = -1.0
    for d in detected:
        if d.confidence < params.min_match_confidence:
            continue
        info = prices.get(d.product_id)
        if info is None or info.price is None:
            unit = 0.0
        else:
            unit = net_value(
                to_eur(info.price, params.fx),
                params.default_sell_platform,
                fee_rates=params.fee_rates,
            )
        val = unit * d.qty
        if val > best_val:
            best_val = val
            best = d
    return best


_CERT_RE = re.compile(r"psa[^0-9]{0,8}(\d{7,9})", re.IGNORECASE)


def _detect_cert_number(listing: SourcingListing) -> str | None:
    """Numéro de cert PSA détecté dans les produits détectés ou le titre."""
    for item in listing.detected_products or []:
        if isinstance(item, dict) and item.get("cert_number"):
            return str(item["cert_number"])
    match = _CERT_RE.search(listing.raw_title or "")
    return match.group(1) if match else None


# ----------------------------------------------------------- orchestration
def evaluate_listing(db: Session, listing_id: int, *, cert_provider=None) -> dict:
    """Évalue une annonce et persiste son statut (+ alerte si elle passe).

    Si un n° de cert est détecté et qu'un ``cert_provider`` est fourni, l'annonce
    est d'abord vérifiée (J7) : cert invalide → bloquée avant toute validation.
    """
    listing = db.get(SourcingListing, listing_id)
    if listing is None:
        raise ValueError(f"sourcing_listing {listing_id} introuvable")

    # Garde-fou authenticité : un slab au cert invalide est bloqué d'emblée.
    cert_number = _detect_cert_number(listing)
    if cert_number and cert_provider is not None:
        from app.services.grading_service import verify_slab

        verdict = verify_slab(db, cert_number, provider=cert_provider)
        if verdict["decision"] == "hard_block":
            listing.status = "blocked"
            listing.filter_flags = {"cert_invalid": True, "cert_number": cert_number}
            listing.evaluated_at = _utcnow()
            db.commit()
            return {"listing_id": listing_id, "status": "blocked", "reason": "cert_invalid",
                    "cert_number": cert_number}

    market = str(get_setting("valuation_market", default="US"))
    params = _valuation_params(market)

    detected = _detected_products(db, listing)
    prices = _price_map(db, detected, market)
    listing_input = ListingInput(
        acquisition_cost_total=_f(listing.asking_price)
        + _f(listing.shipping_cost)
        + _f(listing.protection_cost),
        estimated_total_cards=int(listing.estimated_total_cards or 0),
        detected_products=detected,
    )

    # --- domain : règle des 50 % + garde-fou IR ---------------------------
    buy = evaluate_buy(
        listing_input,
        prices,
        params,
        fifty_rule_threshold_pct=_f(get_setting("fifty_rule_threshold_pct", default=50)),
        ir_min_discount_pct=_f(get_setting("ir_min_discount_pct", default=30)),
    )

    # --- domain : filtres S4 sur le value driver --------------------------
    driver = _value_driver(detected, prices, params)
    driver_info = prices.get(driver.product_id) if driver else None
    driver_product = db.get(Product, driver.product_id) if driver else None
    fomo_scope = str(get_setting("fomo_scope", default="global"))
    in_scope = True
    if fomo_scope == "set" and driver_product is not None:
        in_scope = bool(driver_product.set_slug) and (
            driver_product.set_slug == str(get_setting("fomo_freeze_reason", default=""))
        )
    filt = passes_S4(
        avg_7d=driver_info.avg_7d if driver_info else None,
        avg_30d=driver_info.avg_30d if driver_info else None,
        sale_count=driver_info.sale_count if driver_info else None,
        approx_sale_count=driver_info.approx_sale_count if driver_info else False,
        pump_rise_pct=_f(get_setting("pump_rise_pct", default=40)),
        min_sale_count=int(_f(get_setting("min_sale_count", default=5))),
        illiquid_approx_multiplier=int(_f(get_setting("illiquid_approx_multiplier", default=2))),
        fomo_freeze=bool(get_setting("fomo_freeze", default=False)),
        fomo_scope=fomo_scope,
        in_scope=in_scope,
        trends_enabled=bool(get_setting("fomo_trends_enabled", default=False)),
        trends_spike=False,  # pas de proxy Trends au Jalon 3
    )

    # --- domain : garde-fou cash ------------------------------------------
    state = portfolio_state(db)
    tiers = _tier_bands(db)
    resolved = resolve_current_tier(state.operational_capital, tiers)
    tier_band = resolved if isinstance(resolved, TierBand) else None
    pct = cash_min_pct(
        state.operational_capital,
        tier_band,
        cash_min_below_150_pct=_f(get_setting("cash_min_below_150_pct", default=15)),
    )
    cash = can_buy(listing_input.acquisition_cost_total, state, cash_min_pct=pct)

    # --- persistance (transaction unique) ---------------------------------
    now = _utcnow()
    listing.evaluated_at = now
    listing.estimated_resale_value = buy.resale_value
    # Plafonné aux bornes de la colonne (revente très faible → ratio énorme).
    listing.ratio_pct = _cap_ratio(buy.ratio_pct)
    listing.passes_50_rule = 1 if buy.passes else 0

    passes_all = buy.passes and filt.passes and cash.allowed

    flags = dict(filt.flags)
    flags["ratio_block"] = not buy.passes
    flags["buy_reason"] = buy.reason
    flags["cash_block"] = not cash.allowed
    if not cash.allowed:
        flags["cash_detail"] = cash.detail

    if passes_all:
        listing.status = "flagged"
        listing.filter_flags = flags
        watch = (
            db.scalar(select(Watchlist).where(Watchlist.product_id == driver.product_id))
            if driver
            else None
        )
        tier = watch.tier if watch else "B"
        score = opportunity_score(
            ratio_pct=buy.ratio_pct,
            threshold_pct=_f(get_setting("fifty_rule_threshold_pct", default=50)),
            priority_coef=float(watch.priority_coef) if watch else 1.0,
            sale_count=driver_info.sale_count if driver_info else None,
            tier=tier,
            w_margin=_f(get_setting("w_margin", default=0.5)),
            w_liquidity=_f(get_setting("w_liquidity", default=0.3)),
            w_tier=_f(get_setting("w_tier", default=0.2)),
            liquidity_midpoint=_f(get_setting("min_sale_count", default=5)),
        )
        is_trinity = bool(watch.is_trinity) if watch else False
        db.add(
            Alert(
                alert_type="buy",
                severity="warning",
                status="pending",
                product_id=driver.product_id if driver else None,
                sourcing_listing_id=listing.id,
                title=f"Achat potentiel : {listing.raw_title[:200]}",
                payload={
                    "score": round(score, 4),
                    "ratio_pct": buy.ratio_pct,
                    "estimated_resale_value": buy.resale_value,
                    "acquisition_cost_total": round(listing_input.acquisition_cost_total, 2),
                    "listing_url": listing.url,
                    "is_trinity": is_trinity,
                    "tier": tier,
                    "value_proxy": market == "US",
                },
            )
        )
        result_status = "flagged"
    else:
        listing.status = "blocked"
        listing.filter_flags = flags
        result_status = "blocked"

    db.commit()
    logger.info(
        "Annonce %s évaluée : %s (ratio=%s, passes_50=%s).",
        listing_id, result_status, buy.ratio_pct, buy.passes,
    )
    return {
        "listing_id": listing_id,
        "status": result_status,
        "ratio_pct": buy.ratio_pct,
        "estimated_resale_value": buy.resale_value,
        "passes_50_rule": buy.passes,
        "filter_flags": flags,
    }
