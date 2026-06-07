"""Entrypoint du conteneur scraper (Playwright).

Orchestre A→F : construit les providers activés (.env), puis lance, à intervalle
``SCRAPE_INTERVAL_MIN``, ``scrape_sourcing`` (collecte → dédup → match → évalue)
et une purge de rétention quotidienne. Best-effort : toute panne est isolée, le
reste de l'app (prix, KPI) continue dans ses propres conteneurs.
"""

from __future__ import annotations

import json
import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import get_setting
from app.db import SessionLocal
from app.logging_config import setup_logging
from app.scraping.selectors import get_selectors
from app.services.health_status import record_heartbeat, touch_heartbeat_file
from app.services.runtime_settings import ensure_runtime_settings
from app.services.sourcing import purge_old_sourcing, scrape_sourcing

setup_logging()  # logs JSON + redaction des secrets
logger = logging.getLogger("scraper")

TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Paris")
INTERVAL_MIN = int(os.getenv("SCRAPE_INTERVAL_MIN", "45"))


def _enabled(name: str, default: str = "true") -> bool:
    return str(os.getenv(name, default)).strip().lower() in ("1", "true", "yes", "on")


def _cookies(prefix: str) -> list:
    raw = os.getenv(f"SCRAPE_{prefix}_COOKIES", "").strip()
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Cookies %s illisibles (JSON) — session anonyme.", prefix)
        return []


def build_providers(selectors: dict, break_threshold: float) -> list:
    # Imports Playwright différés : le module reste importable sans navigateur.
    from scraper.fetch import PlaywrightFetcher
    from scraper.leboncoin import LeboncoinScraper
    from scraper.vinted import VintedScraper

    ua = os.getenv("SCRAPE_USER_AGENT") or None
    providers = []
    if _enabled("SCRAPE_VINTED_ENABLED"):
        providers.append(VintedScraper(
            PlaywrightFetcher(user_agent=ua, cookies=_cookies("VINTED")),
            selectors, break_threshold=break_threshold,
        ))
    if _enabled("SCRAPE_LBC_ENABLED"):
        providers.append(LeboncoinScraper(
            PlaywrightFetcher(user_agent=ua, cookies=_cookies("LBC")),
            selectors, break_threshold=break_threshold,
        ))
    return providers


def alive() -> None:
    """Liveness fichier + heartbeat DB (le scrape réel est espacé)."""
    touch_heartbeat_file()
    try:
        with SessionLocal() as db:
            record_heartbeat(db, "scraper")
    except Exception:  # pragma: no cover - robustesse
        logger.exception("heartbeat scraper en échec (isolé).")


def run_scrape() -> None:
    try:
        with SessionLocal() as db:
            ensure_runtime_settings(db)
            record_heartbeat(db, "scraper")
            break_threshold = float(get_setting("selector_break_threshold", default=30))
            providers = build_providers(get_selectors(), break_threshold)
            if not providers:
                logger.info("Aucun provider activé — run ignoré.")
                return
            scrape_sourcing(db, providers)
    except Exception:  # le scraper ne doit jamais tuer son conteneur
        logger.exception("Run de scraping en échec (isolé).")


def run_purge() -> None:
    try:
        with SessionLocal() as db:
            purge_old_sourcing(db)
    except Exception:
        logger.exception("Purge sourcing en échec (isolée).")


def main() -> None:
    logger.info("scraper prêt (Playwright) — interval=%smin", INTERVAL_MIN)
    alive()  # heartbeat initial
    scheduler = BlockingScheduler(timezone=TIMEZONE)
    scheduler.add_job(alive, "interval", minutes=1, id="alive")
    scheduler.add_job(run_scrape, "interval", minutes=INTERVAL_MIN, id="scrape_sourcing")
    scheduler.add_job(run_purge, "cron", hour=4, minute=30, id="purge_sourcing")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("scraper arrêté.")


if __name__ == "__main__":
    main()
