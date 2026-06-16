"""Politesse & robustesse du sourcing retail (parties pures + circuit breaker).

Posture identique au scraping existant : pas de course à l'armement. On respecte
``robots.txt``, on présente un UA réaliste, on espace les requêtes (intervalle +
jitter), on plafonne par run, et on s'arrête (backoff/circuit breaker) dès qu'un
détaillant nous bloque. Le circuit breaker **réutilise** ``scrape_state`` (pas de
mécanisme parallèle) avec une clé ``retail:<code>``.
"""

from __future__ import annotations

import datetime as dt
import random
import urllib.robotparser

from sqlalchemy.orm import Session

from app.scraping.antibot import REALISTIC_UA
from app.services import scrape_state


def default_headers() -> dict[str, str]:
    """En-têtes HTTP réalistes (Chrome desktop, locale FR)."""
    return {
        "User-Agent": REALISTIC_UA,
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def jittered_delay_s(min_delay_ms: int, jitter_ratio: float = 0.4) -> float:
    """Délai (secondes) = min + jitter aléatoire (anti-pattern régulier)."""
    if min_delay_ms <= 0:
        return 0.0
    return (min_delay_ms / 1000.0) * (1.0 + random.uniform(0.0, jitter_ratio))


def robots_allows(robots_txt: str | None, url: str, ua: str = REALISTIC_UA) -> bool:
    """Vrai si ``url`` est autorisée par le ``robots.txt`` fourni.

    Sans robots.txt exploitable, on autorise (best-effort) — le throttling et le
    plafond de requêtes restent la garantie de politesse.
    """
    if not robots_txt:
        return True
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(robots_txt.splitlines())
    except Exception:  # noqa: BLE001 - robots.txt malformé → on n'interdit pas
        return True
    try:
        return rp.can_fetch(ua, url)
    except Exception:  # noqa: BLE001
        return True


class RequestBudget:
    """Plafond de requêtes HTTP par run (``retail_request_cap_per_run``)."""

    def __init__(self, cap: int):
        self.cap = max(0, int(cap))
        self.used = 0

    def allow(self) -> bool:
        if self.used >= self.cap:
            return False
        self.used += 1
        return True

    @property
    def remaining(self) -> int:
        return max(0, self.cap - self.used)


# --------------------------------------------------- circuit breaker (réutilise scrape_state)
def _platform(code: str) -> str:
    return f"retail:{code}"


def is_retailer_blocked(db: Session, code: str, now: dt.datetime) -> bool:
    """Vrai si le détaillant est en backoff (circuit ouvert)."""
    return scrape_state.is_blocked(db, _platform(code), now)


def record_retailer_error(db: Session, code: str, now: dt.datetime, *, cooldown_cap_min: int) -> int:
    """Enregistre une erreur consécutive → backoff exponentiel ; renvoie les minutes."""
    return scrape_state.record_block(db, _platform(code), now, cooldown_cap_min=cooldown_cap_min)


def clear_retailer_errors(db: Session, code: str) -> None:
    """Réinitialise le compteur d'erreurs (succès → circuit refermé)."""
    scrape_state.clear_block(db, _platform(code))


def retailer_error_count(db: Session, code: str) -> int:
    """Nombre d'erreurs consécutives en cours pour ce détaillant."""
    return int(scrape_state.block_info(db, _platform(code)).get("count", 0))


def circuit_open(db: Session, code: str, now: dt.datetime, max_errors: int) -> bool:
    """Circuit ouvert = en backoff OU compteur d'erreurs ≥ seuil."""
    if is_retailer_blocked(db, code, now):
        return True
    return retailer_error_count(db, code) >= max(1, int(max_errors))
