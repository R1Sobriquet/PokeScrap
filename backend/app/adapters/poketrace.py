"""Adapter PokeTrace (PriceProvider) — STUB Jalon 1."""

from __future__ import annotations

from typing import Any

from app.adapters.ports import PriceProvider


class PokeTracePriceProvider(PriceProvider):
    def get_price(self, product_ref: str, **kwargs: Any) -> Any:
        raise NotImplementedError("jalon 2")
