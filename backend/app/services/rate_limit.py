"""Rate limiting minimaliste en mémoire (fenêtre fixe, par IP + portée).

Zéro dépendance : suffisant pour un backend mono-process (uvicorn). Derrière
Caddy, l'IP client réelle arrive dans ``X-Forwarded-For`` (premier élément).
Désactivable via ``RATE_LIMIT_ENABLED=false`` (tests). Utilisé en dépendance
FastAPI : ``Depends(rate_limit("login", max_calls=5, window_s=60))`` → 429.
"""

from __future__ import annotations

import threading
import time

from fastapi import HTTPException, Request, status

from app.config import get_settings

_lock = threading.Lock()
_buckets: dict[tuple[str, str], tuple[float, int]] = {}  # (scope, ip) -> (début fenêtre, nb)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def reset_rate_limits() -> None:
    """Vide les compteurs (isolation entre tests)."""
    with _lock:
        _buckets.clear()


def rate_limit(scope: str, *, max_calls: int, window_s: int = 60):
    """Fabrique une dépendance FastAPI limitant ``scope`` à N appels / fenêtre."""

    def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        key = (scope, _client_ip(request))
        now = time.monotonic()
        with _lock:
            start, count = _buckets.get(key, (now, 0))
            if now - start >= window_s:  # nouvelle fenêtre
                start, count = now, 0
            count += 1
            _buckets[key] = (start, count)
        if count > max_calls:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de tentatives — réessaie dans une minute.",
                headers={"Retry-After": str(window_s)},
            )

    return dependency
