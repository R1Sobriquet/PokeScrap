"""Couche domaine PokéStock FR — dataclasses pures (zéro I/O).

États stock normalisés (schema.org → interne) et types de produits scellés. Le
domaine ne connaît ni httpx, ni l'ORM : les adapters traduisent vers/depuis ces
structures.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

# États stock canoniques (alignés sur l'ENUM ``retail_offers.current_stock_state``).
IN_STOCK = "in_stock"
OUT_OF_STOCK = "out_of_stock"
PREORDER = "preorder"
UNKNOWN = "unknown"

STOCK_STATES = (IN_STOCK, OUT_OF_STOCK, PREORDER, UNKNOWN)

#: Transitions qui déclenchent une alerte restock (depuis → vers).
RESTOCK_FROM = {OUT_OF_STOCK, UNKNOWN}
RESTOCK_TO = {IN_STOCK, PREORDER}

# Types de produits scellés reconnus (best-effort depuis le titre/URL).
PRODUCT_TYPES = ("etb", "display", "bundle", "coffret", "upc", "booster", "autre")

#: schema.org ``offers.availability`` → état canonique.
SCHEMA_AVAILABILITY = {
    "instock": IN_STOCK,
    "in_stock": IN_STOCK,
    "onlineonly": IN_STOCK,
    "limitedavailability": IN_STOCK,
    "preorder": PREORDER,
    "presale": PREORDER,
    "outofstock": OUT_OF_STOCK,
    "soldout": OUT_OF_STOCK,
    "discontinued": OUT_OF_STOCK,
    "backorder": OUT_OF_STOCK,
}


def normalize_availability(raw: str | None) -> str:
    """Mappe une valeur schema.org ``availability`` vers un état canonique."""
    if not raw:
        return UNKNOWN
    key = raw.rsplit("/", 1)[-1].strip().lower().replace(" ", "")
    return SCHEMA_AVAILABILITY.get(key, UNKNOWN)


@dataclass(frozen=True)
class Retailer:
    code: str
    name: str
    base_url: str | None = None
    sitemap_url: str | None = None
    is_active: bool = True


@dataclass(frozen=True)
class SkuRef:
    """Référence d'un SKU repérée dans un sitemap (radar nouveaux SKU)."""

    url: str
    retailer_sku: str | None = None
    title: str | None = None
    lastmod: str | None = None


@dataclass(frozen=True)
class OfferSnapshot:
    """Instantané d'une page produit (état stock + prix), source de la transition."""

    url: str
    stock_state: str = UNKNOWN
    price: Decimal | None = None
    currency: str = "EUR"
    title: str | None = None
    image: str | None = None
    retailer_sku: str | None = None
    product_type: str | None = None
    fetched_at: dt.datetime | None = None
    source: str = "jsonld"  # 'jsonld' | 'dom' | 'error'


@dataclass(frozen=True)
class RetailAlert:
    """Payload de notification unifié (RESTOCK / NEW_SKU)."""

    type: str  # 'RESTOCK' | 'NEW_SKU'
    title: str
    url: str
    retailer_name: str
    stock_state: str = UNKNOWN
    price: Decimal | None = None
    currency: str = "EUR"
    detected_at: dt.datetime | None = None
