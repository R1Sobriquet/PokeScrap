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
from app.services.ingestion import ingest_watchlist_prices
from app.services.runtime_settings import ensure_runtime_settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] scheduler: %(message)s"
)
logger = logging.getLogger("scheduler")

TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Paris")
JOB_REFRESH_PRICES = os.getenv("JOB_REFRESH_PRICES", "0 6 * * *")
JOB_REFRESH_HISTORY = os.getenv("JOB_REFRESH_HISTORY", "0 4 * * *")

# Provider persistant : son compteur de quota journalier survit entre les runs
# tant que le process scheduler vit (reset interne à minuit UTC).
_provider: PokeTracePriceProvider | None = None


def _get_provider() -> PokeTracePriceProvider:
    global _provider
    if _provider is None:
        _provider = PokeTracePriceProvider()
    return _provider


def heartbeat() -> None:
    logger.info("heartbeat")


def refresh_prices() -> None:
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        written = ingest_watchlist_prices(db, provider=_get_provider())
    logger.info("refresh_prices: %s snapshots écrits", written)


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
    logger.info(
        "Scheduler démarré (tz=%s, refresh_prices='%s', refresh_history='%s').",
        TIMEZONE,
        JOB_REFRESH_PRICES,
        JOB_REFRESH_HISTORY,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler arrêté.")


if __name__ == "__main__":
    main()
