"""Scraper Playwright — STUB Jalon 1.

Le conteneur démarre, prouve son câblage en loggant « scraper prêt (stub) »,
puis reste en vie (idle) sans rien scraper. Réseau sortant uniquement.
"""

from __future__ import annotations

import logging
import time

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] scraper: %(message)s"
)
logger = logging.getLogger("scraper")


def main() -> None:
    logger.info("scraper prêt (stub)")
    # Boucle d'inactivité : évite que `restart: unless-stopped` ne reboucle.
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
