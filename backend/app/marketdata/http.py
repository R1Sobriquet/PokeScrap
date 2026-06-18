"""GET JSON injectable (httpx) — partagé par les adapters marché.

Signature ``(url, *, headers, params) -> (status, data)`` substituable en test.
Lève ``MarketBlocked`` sur 403/429 (→ circuit breaker côté job).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

#: ``json_get(url, *, headers, params) -> (status:int, data:Any)``
JsonGet = Callable[..., tuple[int, Any]]


class MarketBlocked(Exception):
    """Source bloquante (403/429) — déclenche backoff + circuit breaker."""

    def __init__(self, reason: str, status: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.status = status


def httpx_json_get(url: str, *, headers: dict | None = None,
                   params: dict | None = None, timeout: float = 20.0) -> tuple[int, Any]:
    resp = httpx.get(url, headers=headers, params=params, timeout=timeout, follow_redirects=True)
    if resp.status_code in (403, 429):
        raise MarketBlocked(f"http_{resp.status_code}", resp.status_code)
    data: Any = None
    try:
        data = resp.json()
    except ValueError:
        data = None
    return resp.status_code, data
