"""Valeur de flip — le vrai but du restock : acheter au prix officiel (~MSRP).

Une offre détaillant en stock = achetable au prix retail. Si la **valeur marché**
du produit lié est supérieure, c'est une opportunité (acheter bas, revendre au
marché). On croise ``retail_offers.current_price`` avec la valeur marché du
produit (snapshots marché POSSÉDÉS en priorité, sinon PokeTrace) → upside % +
verdict BUY/PASS. Le matching (``retail_offers.product_id``) active ce signal.

``fx`` / ``market`` passés explicitement (pas de ``get_setting`` dans le chemin
chaud — évite tout effet de bord transaction en test).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MarketPriceSnapshot

# (seuil upside %, verdict, ton UI). upside = (marché − retail) / retail.
_FLIP_VERDICTS = [
    (35.0, "STRONG BUY", "buy"),
    (15.0, "BUY", "buy"),
    (0.0, "FAIR", "fair"),
]


def flip_verdict(upside_pct: float) -> tuple[str, str]:
    for threshold, label, tone in _FLIP_VERDICTS:
        if upside_pct >= threshold:
            return label, tone
    return "PASS", "pass"


def _latest_market(db: Session, ref: str, market: str):
    return db.scalar(
        select(MarketPriceSnapshot).where(
            MarketPriceSnapshot.product_ref == ref,
            MarketPriceSnapshot.market == market,
            MarketPriceSnapshot.price.is_not(None),
        ).order_by(MarketPriceSnapshot.captured_date.desc()).limit(1)
    )


def market_value_eur(db: Session, product_id: int, *, fx: float, market: str) -> tuple[float | None, str | None]:
    """Valeur marché EUR : snapshots marché EU → US×fx → PokeTrace. (valeur, source)."""
    ref = str(product_id)
    eu = _latest_market(db, ref, "eu")
    if eu is not None and eu.price is not None:
        return float(eu.price), f"market:{eu.source}"
    us = _latest_market(db, ref, "us")
    if us is not None and us.price is not None:
        return round(float(us.price) * fx, 2), f"market:{us.source}"
    # Repli PokeTrace (price_snapshots).
    from app.services.prices import get_latest_price
    snap = get_latest_price(db, product_id, market=("US" if market == "US" else "EU"))
    if snap is not None and snap.price_avg is not None:
        val = float(snap.price_avg) * (fx if market == "US" else 1.0)
        return round(val, 2), "poketrace"
    return None, None


def flip_for_offer(db: Session, offer, *, fx: float, market: str) -> dict:
    """Calcule le flip d'une offre. Champs ``None`` si non calculable (non matchée
    ou pas de valeur marché) — l'alerte reste émise, sans verdict."""
    retail = float(offer.current_price) if offer.current_price is not None else None
    out = {"retail_price": retail, "market_value": None, "market_source": None,
           "upside_pct": None, "verdict": None, "verdict_tone": None}
    if offer.product_id is None or retail is None or retail <= 0:
        return out
    mv, src = market_value_eur(db, offer.product_id, fx=fx, market=market)
    if mv is None:
        return out
    upside = round((mv - retail) / retail * 100, 1)
    label, tone = flip_verdict(upside)
    out.update({"market_value": mv, "market_source": src, "upside_pct": upside,
                "verdict": label, "verdict_tone": tone})
    return out
