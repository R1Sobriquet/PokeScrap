"""Scheduler APScheduler — Jalon 2.

Remplace les stubs du Jalon 1 par les vraies tâches d'ingestion, en réutilisant
la couche données du backend (``app.services``) sur la même base MySQL :

  * ``heartbeat``       — preuve de vie, chaque minute ;
  * ``refresh_prices``  — ingère les prix de la watchlist active (cron
    ``JOB_REFRESH_PRICES``), en réutilisant un provider PokeTrace persistant
    pour que le garde-quota journalier survive entre les exécutions ;
  * ``refresh_history`` — différé tant que ``feature_history_full=false`` (Free).
"""

from __future__ import annotations

import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.adapters.poketrace import PokeTracePriceProvider
from app.config import get_setting
from app.db import SessionLocal
from app.logging_config import setup_logging
from app.services.grading_service import run_grading_scan
from app.services.health_status import record_heartbeat, run_dead_mans_switch, touch_heartbeat_file
from app.services.ingestion import ingest_watchlist_prices
from app.services.kpi_snapshot import run_kpi_snapshot
from app.services.pe_signal_service import run_pe_accumulation_scan
from app.services.movers import compute_top_movers
from app.services.retail_jobs import run_check_restocks, run_detect_new_skus
from app.services.retention import prune_price_snapshots
from app.services.runtime_settings import ensure_runtime_settings
from app.services.selling_service import evaluate_position_sales
from app.services.tracked_sets import ensure_default_tracked_sets, sync_tracked_sets

setup_logging()  # logs JSON + redaction des secrets
logger = logging.getLogger("scheduler")

TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Paris")
JOB_REFRESH_PRICES = os.getenv("JOB_REFRESH_PRICES", "0 6 * * *")
JOB_REFRESH_HISTORY = os.getenv("JOB_REFRESH_HISTORY", "0 4 * * *")
JOB_KPI_SNAPSHOT = os.getenv("JOB_KPI_SNAPSHOT", "55 23 * * *")

# Provider persistant : son compteur de quota journalier survit entre les runs
# tant que le process scheduler vit (reset interne à minuit UTC).
_provider: PokeTracePriceProvider | None = None


def _get_provider() -> PokeTracePriceProvider:
    global _provider
    if _provider is None:
        _provider = PokeTracePriceProvider()
    return _provider


def heartbeat() -> None:
    touch_heartbeat_file()  # liveness fichier (healthcheck Docker)
    with SessionLocal() as db:
        record_heartbeat(db, "scheduler")
    logger.info("heartbeat")


def dead_mans_switch() -> None:
    with SessionLocal() as db:
        result = run_dead_mans_switch(db)
    if result["stale"]:
        logger.warning("dead_mans_switch: jobs silencieux %s", result["stale"])


def prune_snapshots() -> None:
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = prune_price_snapshots(db)
    logger.info("prune_snapshots: %s", result)


def sync_sets() -> None:
    # Intervalle long (1×/jour) : on économise le quota PokeTrace (250/j).
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        ensure_default_tracked_sets(db)
        result = sync_tracked_sets(db, provider=_get_provider())
    logger.info("sync_tracked_sets: %s", result)


def scan_movers() -> None:
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        movers = compute_top_movers(db)
    logger.info("scan_movers: %s top movers", len(movers))


def refresh_prices() -> None:
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        written = ingest_watchlist_prices(db, provider=_get_provider())
        # Une fois les prix rafraîchis : signal PE + évaluation des ventes.
        pe = run_pe_accumulation_scan(db)
        sells = evaluate_position_sales(db)
    logger.info(
        "refresh_prices: %s snapshots ; PE=%s ; ventes=%s", written, pe["fire"], sells["sell"]
    )


def kpi_snapshot() -> None:
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = run_kpi_snapshot(db)
    logger.info("kpi_snapshot: %s", result)


def grading_scan() -> None:
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = run_grading_scan(db)
    logger.info("grading_scan: %s", result)


def retail_check_restocks() -> None:
    # Veille restock sur la watchlist (intervalle prudent ; no-op si désactivé).
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = run_check_restocks(db)
    logger.info("retail_check_restocks: %s", result.get("summary"))


def retail_detect_new_skus() -> None:
    # Radar nouveaux SKU via sitemaps (fréquence basse ; no-op si désactivé).
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = run_detect_new_skus(db)
    logger.info("retail_detect_new_skus: %s", result.get("summary"))


def refresh_history() -> None:
    if not bool(get_setting("feature_history_full", default=False)):
        logger.info("refresh_history différé : mode Free")
        return
    # Mode Pro (jalon ultérieur) : ingestion de l'historique par tier.
    logger.info("refresh_history: mode Pro — TODO ingestion history")


def train_release_model() -> None:
    # Future Radar : (ré)entraîne le modèle de scoring (no-op si données insuffisantes).
    from app.ml.scorer import train

    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = train(db)
    logger.info("train_release_model: %s", result.get("summary"))


def market_snapshot_daily() -> None:
    # Moat : tire les prix marché des produits watchés (no-op si désactivé).
    from app.services.market_snapshot import run_market_snapshot

    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = run_market_snapshot(db)
    logger.info("market_snapshot_daily: %s", result.get("summary"))


def calendar_sync() -> None:
    from app.services.calendar_sync import run_calendar_sync

    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = run_calendar_sync(db)
    logger.info("calendar_sync: %s", result.get("summary"))


def match_products() -> None:
    from app.services.product_matching import run_match_products

    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = run_match_products(db)
    logger.info("match_products: %s", result.get("summary"))


def source_health_check() -> None:
    from app.services.source_health import check_sources

    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = check_sources(db)
    logger.info("source_health_check: %s", result.get("summary"))


def flip_radar_scan() -> None:
    # Flip Radar : opportunités d'achat-revente en stock (no-op si dry-run).
    from app.services.flip_radar import run_flip_radar

    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = run_flip_radar(db)
    logger.info("flip_radar_scan: %s", result.get("summary"))


def main() -> None:
    scheduler = BlockingScheduler(timezone=TIMEZONE)
    scheduler.add_job(heartbeat, "interval", minutes=1, id="heartbeat")
    scheduler.add_job(
        refresh_prices,
        CronTrigger.from_crontab(JOB_REFRESH_PRICES, timezone=TIMEZONE),
        id="refresh_prices",
    )
    scheduler.add_job(
        refresh_history,
        CronTrigger.from_crontab(JOB_REFRESH_HISTORY, timezone=TIMEZONE),
        id="refresh_history",
    )
    scheduler.add_job(
        kpi_snapshot,
        CronTrigger.from_crontab(JOB_KPI_SNAPSHOT, timezone=TIMEZONE),
        id="kpi_snapshot",
    )
    # Grading hebdo (no-op propre hors mode Pro) : lundi 03:00.
    scheduler.add_job(
        grading_scan,
        CronTrigger(day_of_week="mon", hour=3, minute=0, timezone=TIMEZONE),
        id="grading_scan",
    )
    # Dead-man's switch : toutes les 30 min. Pruning rétention : quotidien 04:15.
    scheduler.add_job(dead_mans_switch, "interval", minutes=30, id="dead_mans_switch")
    scheduler.add_job(
        prune_snapshots, CronTrigger(hour=4, minute=15, timezone=TIMEZONE), id="prune_snapshots"
    )
    # Auto-watchlist par set : 1×/jour (quota). Top movers : après le refresh prix.
    scheduler.add_job(sync_sets, CronTrigger(hour=5, minute=0, timezone=TIMEZONE), id="sync_tracked_sets")
    scheduler.add_job(scan_movers, CronTrigger(hour=6, minute=30, timezone=TIMEZONE), id="scan_movers")
    # PokéStock FR Phase A — poll court (agressif sur le planning) ; la CADENCE
    # RÉELLE par offre est pilotée par son tier (hot/normal/cold). No-op tant que
    # retail_sourcing_enabled=false. Tier hot ~45 s, normal ~5 min, cold ~horaire.
    poll_sec = int(os.getenv("RETAIL_POLL_INTERVAL_SEC", "45"))
    scheduler.add_job(retail_check_restocks, "interval", seconds=poll_sec, id="retail_check_restocks")
    scheduler.add_job(
        retail_detect_new_skus,
        CronTrigger(hour="7,19", minute=15, timezone=TIMEZONE),
        id="retail_detect_new_skus",
    )
    # Future Radar — ré-entraînement hebdo du modèle ML : dimanche 03:30.
    scheduler.add_job(
        train_release_model,
        CronTrigger(day_of_week="sun", hour=3, minute=30, timezone=TIMEZONE),
        id="train_release_model",
    )
    # Moat de données marché — agressif sur le planning, léger sur les requêtes.
    # Snapshot quotidien 02:00 ; calendrier + matching 1×/jour ; santé toutes les 2h.
    scheduler.add_job(market_snapshot_daily, CronTrigger(hour=2, minute=0, timezone=TIMEZONE), id="market_snapshot_daily")
    scheduler.add_job(calendar_sync, CronTrigger(hour=4, minute=40, timezone=TIMEZONE), id="calendar_sync")
    scheduler.add_job(match_products, CronTrigger(hour=5, minute=20, timezone=TIMEZONE), id="match_products")
    scheduler.add_job(source_health_check, "interval", hours=2, id="source_health_check")
    scheduler.add_job(flip_radar_scan, "interval", hours=3, id="flip_radar_scan")
    logger.info(
        "Scheduler démarré (tz=%s, prices='%s', history='%s', kpi='%s', grading=weekly, deadman=30m).",
        TIMEZONE,
        JOB_REFRESH_PRICES,
        JOB_REFRESH_HISTORY,
        JOB_KPI_SNAPSHOT,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler arrêté.")


if __name__ == "__main__":
    main()
