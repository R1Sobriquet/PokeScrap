"""DTO neutres du scraping (aucune dépendance Playwright/DB)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


class ScraperBlocked(RuntimeError):
    """Levée quand une plateforme bloque (CAPTCHA / 403 / mur anti-bot).

    On ne lutte pas : l'orchestration capte cette exception, émet une alerte
    ``tech_error`` (avec le diagnostic) et applique un backoff sur la plateforme.
    Porte des détails structurés pour le diagnostic (cause, code HTTP, URL, titre).
    """

    def __init__(self, message: str, *, reason: str | None = None,
                 status: int | None = None, url: str | None = None,
                 title: str | None = None):
        super().__init__(message)
        self.reason = reason
        self.status = status
        self.url = url
        self.title = title


class SelectorsBroken(RuntimeError):
    """Levée quand la structure HTML ne correspond plus aux sélecteurs."""


@dataclass(frozen=True)
class RawListing:
    platform: str
    external_id: str
    url: str
    raw_title: str
    asking_price: float
    shipping_cost: float = 0.0
    location: str | None = None
    listed_at: dt.datetime | None = None
