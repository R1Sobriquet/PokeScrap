"""Orchestration du sourcing (best-effort, isolée).

Pour chaque provider activé et chaque requête sauvegardée : scrape poliment,
upsert dans ``sourcing_listings`` (dédup ``(platform, external_id)``), matche le
titre aux produits de la watchlist, puis déclenche ``evaluate_listing`` (J3).

Robustesse : toute exception d'un provider est captée → alerte ``tech_error`` ;
un blocage déclenche un backoff. **Jamais** d'exception propagée : une panne du
scraper n'interrompt aucun autre job.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.models import Alert, Product, SourcingListing, Watchlist
from app.scraping.models import RawListing, ScraperBlocked, SelectorsBroken
from app.services import scrape_state
from app.services.buy_evaluation import evaluate_listing
from app.services.matching import MatchProduct, match_listing

logger = logging.getLogger("services.sourcing")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _tech_error(db: Session, title: str, payload: dict) -> None:
    db.add(Alert(alert_type="tech_error", severity="warning", status="pending",
                 title=title, payload=payload))
    db.commit()


def _match_products(db: Session) -> list[MatchProduct]:
    rows = db.execute(
        select(Watchlist, Product).join(Product, Watchlist.product_id == Product.id)
        .where(Watchlist.is_active == 1)
    ).all()
    return [
        MatchProduct(
            product_id=p.id, name=p.name, set_name=p.set_name, set_slug=p.set_slug,
            card_number=p.card_number, keywords=w.keywords,
            is_illustration_rare=bool(w.is_illustration_rare),
        )
        for w, p in rows
    ]


def build_queries(db: Session) -> list[str]:
    """Requêtes sauvegardées + dérivées de la watchlist (ciblées, dédupliquées)."""
    queries: list[str] = []
    saved = get_setting("saved_queries", default=[])
    if isinstance(saved, list):
        queries.extend(str(q) for q in saved)
    for w, p in db.execute(
        select(Watchlist, Product).join(Product, Watchlist.product_id == Product.id)
        .where(Watchlist.is_active == 1)
    ).all():
        if p.name:
            queries.append(f"{p.name} {p.set_name or ''}".strip())
    # dédup en préservant l'ordre
    seen: set[str] = set()
    out = []
    for q in queries:
        key = q.lower()
        if q and key not in seen:
            seen.add(key)
            out.append(q)
    return out


def _upsert_and_evaluate(
    db: Session, raw: RawListing, products: list[MatchProduct], now: dt.datetime
) -> str:
    """Insère une annonce nouvelle (dédup) et l'évalue. Renvoie le statut d'action."""
    existing = db.scalar(
        select(SourcingListing).where(
            SourcingListing.platform == raw.platform,
            SourcingListing.external_id == raw.external_id,
        )
    )
    if existing is not None:
        return "duplicate"  # déjà vue → pas de ré-évaluation

    default_lot = int(float(get_setting("bulk_lot_target_size", default=30)))
    detected, total_cards = match_listing(raw.raw_title, products, default_lot=default_lot)

    listing = SourcingListing(
        platform=raw.platform,
        external_id=raw.external_id,
        url=raw.url,
        raw_title=raw.raw_title,
        asking_price=raw.asking_price,
        shipping_cost=raw.shipping_cost,
        location=raw.location,
        listed_at=raw.listed_at,
        detected_at=now,
        detected_products=detected,
        estimated_total_cards=total_cards,
        status="new",
    )
    db.add(listing)
    db.commit()
    evaluate_listing(db, listing.id)
    return "evaluated"


def _platform_enabled(platform: str) -> bool:
    """Toggle par source via settings (live, éditable au dashboard)."""
    return bool(get_setting(f"scrape_{platform}_enabled", default=True))


def scrape_sourcing(db: Session, providers: list, *, now: dt.datetime | None = None) -> dict:
    """Boucle de sourcing best-effort. Ne lève jamais."""
    now = now or _utcnow()
    max_listings = int(float(get_setting("scrape_max_listings_per_run", default=40)))
    cooldown_cap = int(float(get_setting("scrape_blocked_cooldown_min", default=120)))
    # Rythme lent : une (ou peu de) recherche par source par run pour commencer.
    max_queries = int(float(get_setting("scrape_max_queries_per_run", default=1)))
    queries = build_queries(db)[: max(max_queries, 0)]
    products = _match_products(db)

    stats = {"scraped": 0, "new": 0, "duplicates": 0, "blocked": [], "errors": 0, "disabled": []}

    for provider in providers:
        platform = getattr(provider, "platform", provider.__class__.__name__)
        if not _platform_enabled(platform):
            logger.info("Plateforme %s désactivée (settings) — on saute.", platform)
            stats["disabled"].append(platform)
            continue
        if scrape_state.is_blocked(db, platform, now):
            logger.info("Plateforme %s en backoff — on saute ce run.", platform)
            continue

        for query in queries:
            if stats["scraped"] >= max_listings:
                break
            try:
                listings = provider.scrape(query)
            except ScraperBlocked as exc:
                minutes = scrape_state.record_block(db, platform, now, cooldown_cap_min=cooldown_cap)
                _tech_error(db, f"Scraping bloqué — {platform}", {
                    "platform": platform, "query": query, "backoff_min": minutes,
                    "reason": getattr(exc, "reason", None), "http_status": getattr(exc, "status", None),
                    "page_title": getattr(exc, "title", None), "page_url": getattr(exc, "url", None),
                    "detail": str(exc),
                })
                logger.warning("Bloqué sur %s : reason=%s status=%s url=%s", platform,
                               getattr(exc, "reason", None), getattr(exc, "status", None),
                               getattr(exc, "url", None))
                stats["blocked"].append(platform)
                break  # stop poli sur cette plateforme
            except SelectorsBroken as exc:
                _tech_error(db, f"Sélecteurs cassés — {platform}",
                            {"platform": platform, "query": query, "detail": str(exc)})
                stats["errors"] += 1
                break
            except Exception as exc:  # best-effort : on isole toute autre panne
                logger.exception("Erreur scraping %s/%s", platform, query)
                _tech_error(db, f"Erreur scraping — {platform}",
                            {"platform": platform, "query": query, "detail": str(exc)})
                stats["errors"] += 1
                continue

            # succès → on lève un éventuel backoff résiduel
            scrape_state.clear_block(db, platform)
            for raw in listings:
                if stats["scraped"] >= max_listings:
                    break
                stats["scraped"] += 1
                try:
                    result = _upsert_and_evaluate(db, raw, products, now)
                except Exception as exc:  # une annonce malformée ne casse pas le run
                    logger.exception("Erreur traitement annonce %s", raw.external_id)
                    _tech_error(db, "Erreur traitement annonce",
                                {"platform": platform, "external_id": raw.external_id, "detail": str(exc)})
                    stats["errors"] += 1
                    continue
                if result == "evaluated":
                    stats["new"] += 1
                elif result == "duplicate":
                    stats["duplicates"] += 1

    logger.info("scrape_sourcing: %s", stats)
    return stats


def purge_old_sourcing(db: Session, *, now: dt.datetime | None = None) -> int:
    """Purge les annonces dismissed/expired plus vieilles que la rétention."""
    now = now or _utcnow()
    retention_days = int(float(get_setting("sourcing_retention_days", default=90)))
    cutoff = now - dt.timedelta(days=retention_days)
    result = db.execute(
        delete(SourcingListing).where(
            SourcingListing.status.in_(("dismissed", "expired")),
            SourcingListing.detected_at < cutoff,
        )
    )
    db.commit()
    purged = result.rowcount or 0
    logger.info("Purge sourcing : %s annonces supprimées (< %s).", purged, cutoff.date())
    return purged
