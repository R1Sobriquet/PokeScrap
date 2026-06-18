"""Deal Analyzer — note une annonce face au prix marché PokeTrace (scalping index).

Flux : (1) fetch léger de la page (JSON-LD/DOM, réutilise ``HttpRetailSource``)
→ prix + titre + état ; (2) recherche PokeTrace par titre → meilleure carte →
``card_value`` (UNOPENED scellé / NEAR_MINT single) convertie en EUR ; (3) écart
prix annoncé vs marché → verdict. Le radar **signale, il n'achète pas**.

Une seule requête sortante par analyse (action manuelle de l'utilisateur).
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.adapters.poketrace import PokeTracePriceProvider
from app.adapters.ports import PriceProvider
from app.config import get_setting
from app.domain.valuation import to_eur
from app.retail.domain import Retailer as RetailerDC
from app.retail.fetch import HttpRetailSource, RetailBlocked
from app.services.tracked_sets import card_value

logger = logging.getLogger("services.deal_analyzer")


def _fx() -> float:
    """Facteur USD→EUR si le marché de valorisation est US, sinon 1.0."""
    market = str(get_setting("valuation_market", default="US"))
    if market == "US":
        try:
            return float(get_setting("fx_usd_eur", default=0.92))
        except (TypeError, ValueError):
            return 0.92
    return 1.0


# (seuil d'écart en %, verdict, ton UI). Écart = (marché - annoncé) / marché.
_VERDICTS = [
    (25.0, "STRONG BUY", "buy"),
    (10.0, "BUY", "buy"),
    (-8.0, "FAIR", "fair"),
    (-25.0, "RICH", "warn"),
]


def _verdict(discount_pct: float) -> tuple[str, str]:
    for threshold, label, tone in _VERDICTS:
        if discount_pct >= threshold:
            return label, tone
    return "OVERPRICED", "pass"


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").replace("www.", "") or "—"


def analyze_listing(
    db: Session,
    url: str,
    *,
    provider: PriceProvider | None = None,
    source: HttpRetailSource | None = None,
) -> dict:
    """Analyse une annonce par URL. Renvoie un dict de verdict (jamais d'exception
    fatale : les états dégradés sont encodés dans ``status``)."""
    url = (url or "").strip()
    if not url.startswith("http"):
        return {"status": "invalid_url", "message": "URL invalide."}

    host = _host(url)
    if source is None:
        source = HttpRetailSource(RetailerDC(code=host, name=host, base_url=f"https://{host}"))

    # (1) Fetch de l'annonce.
    try:
        snap = source.fetch_offer(url)
    except RetailBlocked as exc:
        return {"status": "blocked", "source": host, "message": f"Fetch bloqué ({exc.reason})."}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Deal analyzer fetch KO (%s): %s", url, exc)
        return {"status": "fetch_failed", "source": host, "message": "Fetch indisponible."}

    listed = float(snap.price) if snap.price is not None else None
    result = {
        "status": "ok",
        "source": host,
        "product": snap.title or url,
        "listed_price": listed,
        "currency": snap.currency or "EUR",
        "stock_state": snap.stock_state,
    }

    if listed is None:
        result["status"] = "no_price"
        result["message"] = "Prix introuvable sur la page."
        return result

    # (2) Prix marché PokeTrace par titre.
    provider = provider or PokeTracePriceProvider()
    market_eur = None
    matched = None
    if snap.title:
        try:
            market = str(get_setting("valuation_market", default="US"))
            hits = provider.search_cards(snap.title, market=market, limit=5)
            if hits:
                matched = hits[0]
                usd = card_value(matched)
                if usd is not None:
                    market_eur = round(to_eur(usd, _fx()), 2)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Deal analyzer PokeTrace KO: %s", exc)

    result["matched_name"] = (matched or {}).get("name") if matched else None
    result["market_value_eur"] = market_eur

    # (3) Verdict.
    if market_eur and market_eur > 0:
        discount = round((market_eur - listed) / market_eur * 100, 1)
        label, tone = _verdict(discount)
        result["discount_pct"] = discount
        result["verdict"] = label
        result["verdict_tone"] = tone
    else:
        result["discount_pct"] = None
        result["verdict"] = "NO COMP"
        result["verdict_tone"] = "fair"
        result["message"] = "Aucun comparable marché — verdict prix seul indisponible."

    return result
