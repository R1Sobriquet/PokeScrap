"""Adapter de sourcing (SourcingProvider) — STUB Jalon 1."""

from __future__ import annotations

from typing import Any

from app.adapters.ports import SourcingProvider


class ScraperSourcingProvider(SourcingProvider):
    def fetch_listings(self, **kwargs: Any) -> Any:
        raise NotImplementedError("jalon 2")
