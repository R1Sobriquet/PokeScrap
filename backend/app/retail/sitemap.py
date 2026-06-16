"""Lecture de sitemaps (radar nouveaux SKU) — parsing pur + cache ETag.

Parse un ``sitemap.xml`` ou un index de sitemaps, filtre les URLs produits
pertinentes (motifs Pokémon/TCG), et mémorise ``ETag``/``Last-Modified`` par
détaillant (settings JSON ``retail_sitemap_cache``) pour ne pas re-télécharger si
rien n'a changé.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import invalidate_setting
from app.models import Setting
from app.retail.domain import SkuRef

#: Indices d'URL produit Pokémon/TCG (best-effort, élargir au besoin).
PRODUCT_URL_HINTS = (
    "pokemon", "pokémon", "tcg", "elite-trainer", "etb", "coffret", "display",
    "booster", "ecb", "dresseur", "scellé", "scelle",
)
#: Motifs à exclure (catégories, recherche, aide…).
EXCLUDE_URL_HINTS = ("/aide", "/help", "/category/", "/recherche", "/search", "/account")

_CACHE_KEY = "retail_sitemap_cache"


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_sitemap(xml_text: str) -> tuple[str, list[SkuRef]]:
    """Parse un sitemap. Renvoie ``(kind, entries)`` où kind ∈ urlset|sitemapindex.

    Pour un ``sitemapindex``, ``entries`` liste les sous-sitemaps (à re-fetcher) ;
    pour un ``urlset``, les URLs produits/pages.
    """
    root = ET.fromstring(xml_text.strip())
    kind = _localname(root.tag)
    entries: list[SkuRef] = []
    for child in root:
        loc = lastmod = None
        for el in child:
            name = _localname(el.tag)
            if name == "loc":
                loc = (el.text or "").strip()
            elif name == "lastmod":
                lastmod = (el.text or "").strip()
        if loc:
            entries.append(SkuRef(url=loc, lastmod=lastmod))
    return kind, entries


def looks_like_product(url: str, hints: tuple[str, ...] = PRODUCT_URL_HINTS) -> bool:
    """Heuristique : URL produit Pokémon pertinente (et non une catégorie)."""
    low = url.lower()
    if any(x in low for x in EXCLUDE_URL_HINTS):
        return False
    return any(h in low for h in hints)


def filter_product_skus(skus, hints: tuple[str, ...] = PRODUCT_URL_HINTS) -> list[SkuRef]:
    return [s for s in skus if looks_like_product(s.url, hints)]


# --------------------------------------------------------------- cache ETag / Last-Modified
def load_cache(db: Session) -> dict:
    row = db.scalar(select(Setting).where(Setting.setting_key == _CACHE_KEY))
    if row is None or not row.setting_value:
        return {}
    try:
        return json.loads(row.setting_value)
    except json.JSONDecodeError:
        return {}


def conditional_headers(cache: dict, code: str) -> dict[str, str]:
    """En-têtes ``If-None-Match`` / ``If-Modified-Since`` depuis le cache."""
    entry = cache.get(code) or {}
    headers: dict[str, str] = {}
    if entry.get("etag"):
        headers["If-None-Match"] = entry["etag"]
    if entry.get("last_modified"):
        headers["If-Modified-Since"] = entry["last_modified"]
    return headers


def save_cache(db: Session, code: str, *, etag: str | None, last_modified: str | None) -> None:
    cache = load_cache(db)
    cache[code] = {"etag": etag, "last_modified": last_modified}
    row = db.scalar(select(Setting).where(Setting.setting_key == _CACHE_KEY))
    value = json.dumps(cache)
    if row is None:
        db.add(Setting(setting_key=_CACHE_KEY, setting_value=value, value_type="json",
                       description="Cache ETag/Last-Modified des sitemaps retail (auto)"))
    else:
        row.setting_value = value
    db.commit()
    invalidate_setting(_CACHE_KEY)
