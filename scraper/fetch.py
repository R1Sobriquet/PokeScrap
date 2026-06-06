"""Fetch Playwright (conteneur scraper uniquement) — I/O réseau sortant.

Scraping poli : un seul navigateur, séquentiel, délai humain randomisé géré par
l'appelant. Détection de blocage (403 / CAPTCHA / DataDome) → ``ScraperBlocked``.
**Aucun contournement anti-bot** : on détecte et on s'arrête.
"""

from __future__ import annotations

import logging

from playwright.sync_api import sync_playwright

from app.scraping.models import ScraperBlocked

logger = logging.getLogger("scraper.fetch")

_BLOCK_MARKERS = ("datadome", "captcha", "are you a human", "access denied", "px-captcha")


class PlaywrightFetcher:
    def __init__(self, *, user_agent: str | None = None, cookies: list | None = None):
        self._ua = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
        self._cookies = cookies or []

    def fetch(self, url: str, *, timeout_ms: int = 20000) -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=self._ua)
            if self._cookies:
                context.add_cookies(self._cookies)
            page = context.new_page()
            try:
                response = page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                status = response.status if response else 0
                html = page.content()
            finally:
                browser.close()

        lowered = html.lower()
        if status in (403, 429) or any(marker in lowered for marker in _BLOCK_MARKERS):
            raise ScraperBlocked(f"Blocage détecté (status={status}) sur {url}")
        return html
