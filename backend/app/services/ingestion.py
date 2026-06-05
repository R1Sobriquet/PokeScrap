"""Ingestion des prix PokeTrace → ``price_snapshots``.

Mode-aware via ``get_setting`` (aucun mode en dur) :
  * ``valuation_market`` → ``market`` + devise (``US``→USD, ``EU``→EUR) ;
  * ``feature_grading_enabled=false`` → on ignore les tiers gradés ;
  * ``price_cache_ttl_min`` → cache anti-gaspillage (on saute un produit dont le
    dernier snapshot est plus jeune que le TTL).

Garde-quota : une ``QuotaExceeded`` interrompt le run et écrit une alerte
``tech_error`` ; une erreur réseau ponctuelle est loggée par produit puis on
continue. **Aucune logique de décision ici.**
"""

from __future__ import annotations

import datetime as dt
import logging

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.poketrace import PokeTracePriceProvider, QuotaExceeded
from app.adapters.ports import PriceProvider
from app.config import get_setting
from app.models import Alert, PriceSnapshot, Product, Watchlist
from app.services.tier_mapping import map_tier

logger = logging.getLogger("services.ingestion")


def _utcnow() -> dt.datetime:
    """Heure UTC naïve (convention applicative pour les colonnes DATETIME)."""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _currency_for_market(market: str) -> str:
    return "USD" if market == "US" else "EUR"


def _has_fresh_snapshot(
    db: Session, product_id: int, ttl_min: int, now: dt.datetime
) -> bool:
    """Vrai si un snapshot PokeTrace plus jeune que le TTL existe déjà."""
    cutoff = now - dt.timedelta(minutes=ttl_min)
    latest = db.scalar(
        select(func.max(PriceSnapshot.captured_at)).where(
            PriceSnapshot.product_id == product_id,
            PriceSnapshot.source == "poketrace",
        )
    )
    return latest is not None and latest >= cutoff


def _write_tech_error(db: Session, title: str, payload: dict) -> None:
    db.add(
        Alert(
            alert_type="tech_error",
            severity="warning",
            title=title,
            payload=payload,
            status="pending",
        )
    )
    db.commit()


def _snapshot_rows_from_card(
    product_id: int,
    card: dict,
    *,
    market: str,
    currency: str,
    grading_enabled: bool,
    now: dt.datetime,
) -> list[PriceSnapshot]:
    """Construit les lignes ``price_snapshots`` à partir du détail d'une carte."""
    prices = card.get("prices") or {}
    rows: list[PriceSnapshot] = []
    for tier, p in prices.items():
        mapping = map_tier(tier)
        if mapping is None:
            continue
        # En mode Free, on n'ingère que les tiers bruts.
        if not mapping.is_raw and not grading_enabled:
            continue
        rows.append(
            PriceSnapshot(
                product_id=product_id,
                source="poketrace",
                market=market,
                grade_company=mapping.grade_company,
                grade=mapping.grade,
                condition_code=mapping.condition_code,
                currency=currency,
                country_code="US" if market == "US" else None,
                price_avg=p.get("avg"),
                price_low=p.get("low"),
                price_high=p.get("high"),
                avg_1d=p.get("avg1d"),
                avg_7d=p.get("avg7d"),
                avg_30d=p.get("avg30d"),
                sale_count=p.get("saleCount"),
                approx_sale_count=1 if p.get("approxSaleCount") else 0,
                captured_at=now,
            )
        )
    return rows


def ingest_prices(
    db: Session,
    product_ids: list[int],
    *,
    provider: PriceProvider | None = None,
    now: dt.datetime | None = None,
) -> int:
    """Ingère les prix des produits donnés. Renvoie le nombre de lignes écrites."""
    if not product_ids:
        return 0

    provider = provider or PokeTracePriceProvider()
    now = now or _utcnow()

    market = str(get_setting("valuation_market", default="US"))
    currency = _currency_for_market(market)
    grading_enabled = bool(get_setting("feature_grading_enabled", default=False))
    ttl_min = int(get_setting("price_cache_ttl_min", default=360))

    written = 0
    for product_id in product_ids:
        product = db.get(Product, product_id)
        if product is None or not product.poketrace_id:
            logger.warning("Produit %s sans poketrace_id — ignoré.", product_id)
            continue

        # Cache anti-gaspillage : protège le budget de requêtes.
        if _has_fresh_snapshot(db, product_id, ttl_min, now):
            logger.debug("Produit %s : snapshot frais (< %smin) — cache.", product_id, ttl_min)
            continue

        try:
            card = provider.get_card(product.poketrace_id, market=market)
        except QuotaExceeded as exc:
            logger.warning("Quota épuisé : arrêt de l'ingestion (%s).", exc)
            _write_tech_error(
                db,
                "Quota PokeTrace épuisé",
                {"detail": str(exc), "remaining_products": len(product_ids) - written},
            )
            break
        except httpx.HTTPError as exc:
            logger.warning("Erreur PokeTrace produit %s : %s", product_id, exc)
            _write_tech_error(
                db,
                "Indispo PokeTrace",
                {"product_id": product_id, "detail": str(exc)},
            )
            continue

        rows = _snapshot_rows_from_card(
            product_id,
            card,
            market=market,
            currency=currency,
            grading_enabled=grading_enabled,
            now=now,
        )
        if rows:
            db.add_all(rows)
            db.commit()
            written += len(rows)

    logger.info("Ingestion terminée : %s snapshots écrits.", written)
    return written


def ingest_watchlist_prices(
    db: Session, *, provider: PriceProvider | None = None
) -> int:
    """Ingère les prix de tous les produits de la watchlist active."""
    product_ids = list(
        db.scalars(
            select(Watchlist.product_id).where(Watchlist.is_active == 1)
        ).all()
    )
    return ingest_prices(db, product_ids, provider=provider)
