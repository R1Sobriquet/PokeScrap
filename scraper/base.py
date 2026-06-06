"""Base commune des scrapers de plateforme (conteneur scraper).

Implémente ``SourcingProvider.scrape`` en réutilisant le parsing pur
(``app.scraping.parser``) ; les classes filles ne font que déclarer leur
``platform`` (et donc leur bloc de sélecteurs). Délai humain randomisé avant
chaque fetch (hygiène anti-ban polie).
"""

from __future__ import annotations

import logging
import random
import time
from urllib.parse import quote_plus

from app.adapters.ports import SourcingProvider
from app.scraping.models import RawListing, SelectorsBroken
from app.scraping.parser import parse_listings

logger = logging.getLogger("scraper.base")


class BaseScraper(SourcingProvider):
    platform = "unknown"

    def __init__(self, fetcher, selectors: dict, *, break_threshold: float = 30.0,
                 min_delay_s: float = 4.0, max_delay_s: float = 11.0):
        self._fetcher = fetcher
        self._sel = selectors[self.platform]
        self._break_threshold = break_threshold
        self._min_delay = min_delay_s
        self._max_delay = max_delay_s

    def _polite_delay(self) -> None:
        time.sleep(random.uniform(self._min_delay, self._max_delay))

    def scrape(self, query: str) -> list[RawListing]:
        url = self._sel["search_url"].format(query=quote_plus(query))
        self._polite_delay()
        html = self._fetcher.fetch(url)  # peut lever ScraperBlocked
        result = parse_listings(
            html, self._sel, platform=self.platform,
            break_threshold=self._break_threshold, base_url=self._sel.get("base_url", ""),
        )
        if result.broken:
            raise SelectorsBroken(result.reason or f"structure cassée ({self.platform})")
        logger.info("%s : %s annonces pour %r", self.platform, len(result.listings), query)
        return result.listings
