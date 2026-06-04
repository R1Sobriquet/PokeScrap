"""Scheduler APScheduler — Jalon 1.

Prouve son câblage : un heartbeat loggé chaque minute, et la tâche
``refresh_prices`` enregistrée (sur le cron ``JOB_REFRESH_PRICES``) qui se
contente de logger « TODO jalon 2 ». Aucune logique métier.
"""

from __future__ import annotations

import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] scheduler: %(message)s"
)
logger = logging.getLogger("scheduler")

TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Paris")
JOB_REFRESH_PRICES = os.getenv("JOB_REFRESH_PRICES", "0 6 * * *")


def heartbeat() -> None:
    logger.info("heartbeat")


def refresh_prices() -> None:
    logger.info("refresh_prices — TODO jalon 2")


def main() -> None:
    scheduler = BlockingScheduler(timezone=TIMEZONE)
    scheduler.add_job(heartbeat, "interval", minutes=1, id="heartbeat")
    scheduler.add_job(
        refresh_prices,
        CronTrigger.from_crontab(JOB_REFRESH_PRICES, timezone=TIMEZONE),
        id="refresh_prices",
    )
    logger.info("Scheduler démarré (tz=%s, refresh_prices='%s').", TIMEZONE, JOB_REFRESH_PRICES)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler arrêté.")


if __name__ == "__main__":
    main()
