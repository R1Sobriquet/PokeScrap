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
from app.services.retention import prune_price_snapshots
from app.services.runtime_settings import ensure_runtime_settings
from app.services.selling_service import evaluate_position_sales

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


def refresh_history() -> None:
    if not bool(get_setting("feature_history_full", default=False)):
        logger.info("refresh_history différé : mode Free")
        return
    # Mode Pro (jalon ultérieur) : ingestion de l'historique par tier.
    logger.info("refresh_history: mode Pro — TODO ingestion history")


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
