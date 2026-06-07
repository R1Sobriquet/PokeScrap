"""Fetch Playwright (conteneur scraper) — sortant, anti-détection LÉGÈRE.

Posture : pas de course à l'armement. On masque les signaux d'automation
évidents, on utilise un UA/locale/timezone/viewport réalistes, un rythme lent et
aléatoire, et on **persiste le contexte** (cookies via storage_state) entre runs.
Sur blocage (403 / captcha / DataDome) : diagnostic précis (code, titre, URL),
**screenshot debug** dans un volume, puis ``ScraperBlocked``. On ne contourne rien.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import pathlib
import random
import time

from playwright.sync_api import sync_playwright

from app.scraping.antibot import REALISTIC_UA, STEALTH_INIT_JS, classify_block
from app.scraping.models import ScraperBlocked

logger = logging.getLogger("scraper.fetch")


def _truthy(value: str, default: bool = True) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class PlaywrightFetcher:
    def __init__(
        self,
        *,
        user_agent: str | None = None,
        cookies: list | None = None,
        platform: str = "default",
        headless: bool | None = None,
        storage_dir: str | None = None,
        debug_dir: str | None = None,
        min_delay_s: float = 2.0,
        max_delay_s: float = 6.0,
    ):
        self._ua = user_agent or REALISTIC_UA
        self._cookies = cookies or []
        self._platform = platform
        self._headless = _truthy(os.getenv("SCRAPE_HEADLESS", ""), True) if headless is None else headless
        self._storage_dir = storage_dir or os.getenv("SCRAPE_STATE_DIR", "/app/state")
        self._debug_dir = debug_dir or os.getenv("SCRAPE_DEBUG_DIR", "/tmp/scraper-debug")
        self._min_delay = min_delay_s
        self._max_delay = max_delay_s

    def _state_path(self) -> pathlib.Path:
        return pathlib.Path(self._storage_dir) / f"{self._platform}.json"

    def _save_screenshot(self, page, reason: str) -> str | None:
        try:
            pathlib.Path(self._debug_dir).mkdir(parents=True, exist_ok=True)
            ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = str(pathlib.Path(self._debug_dir) / f"{self._platform}_{reason}_{ts}.png")
            page.screenshot(path=path, full_page=False)
            return path
        except Exception:  # pragma: no cover - le debug ne doit jamais casser le run
            logger.exception("Screenshot debug impossible")
            return None

    def fetch(self, url: str, *, timeout_ms: int = 25000) -> str:
        state_path = self._state_path()
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self._headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = browser.new_context(
                user_agent=self._ua,
                locale="fr-FR",
                timezone_id="Europe/Paris",
                viewport={"width": 1280, "height": 800},
                storage_state=str(state_path) if state_path.exists() else None,
            )
            context.add_init_script(STEALTH_INIT_JS)
            # playwright-stealth en bonus s'il est installé (sinon init script ci-dessus).
            try:  # pragma: no cover
                from playwright_stealth import stealth_sync  # type: ignore
            except Exception:  # pragma: no cover
                stealth_sync = None
            if self._cookies:
                context.add_cookies(self._cookies)
            page = context.new_page()
            if stealth_sync:  # pragma: no cover
                try:
                    stealth_sync(page)
                except Exception:
                    logger.debug("playwright-stealth indisponible/échec — init script seul.")

            # Délai humain aléatoire avant l'action.
            time.sleep(random.uniform(self._min_delay, self._max_delay))
            try:
                response = page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                status = response.status if response else 0
                html = page.content()
                title = (page.title() or "")[:200]
                reason = classify_block(status, html)
                if reason:
                    shot = self._save_screenshot(page, reason)
                    logger.warning(
                        "Blocage %s sur %s — status=%s titre=%r url=%s screenshot=%s",
                        reason, self._platform, status, title, page.url, shot,
                    )
                    raise ScraperBlocked(
                        f"{self._platform}: {reason} (status={status}, titre={title!r})",
                        reason=reason, status=status, url=page.url, title=title,
                    )
                # Succès → on persiste le contexte (cookies) pour le prochain run.
                try:
                    pathlib.Path(self._storage_dir).mkdir(parents=True, exist_ok=True)
                    context.storage_state(path=str(state_path))
                except Exception:  # pragma: no cover
                    logger.debug("Persistance storage_state impossible.")
                return html
            finally:
                browser.close()
