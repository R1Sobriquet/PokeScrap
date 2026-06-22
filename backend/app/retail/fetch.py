"""Adapter HTTP du port ``RetailSourcePort`` (httpx léger, sans Playwright).

Tourne dans les conteneurs existants (backend/scheduler) — aucune escalade
anti-bot. Lève ``RetailBlocked`` sur 403/429/DataDome/captcha pour que l'appelant
applique backoff + circuit breaker (``politeness``). Le parsing est délégué aux
fonctions pures de ``parse``/``sitemap``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable

import httpx

from app.retail.domain import OfferSnapshot, Retailer, SkuRef
from app.retail.parse import parse_availability_json, parse_offer, parse_store_availability_json
from app.retail.politeness import default_headers
from app.retail.ports import RetailSourcePort
from app.retail.sitemap import filter_product_skus, parse_sitemap
from app.scraping.antibot import classify_block

#: ``http_get(url, headers) -> (status_code, text, headers)`` — injectable en test.
HttpGet = Callable[[str, dict], tuple[int, str, dict]]


class RetailBlocked(Exception):
    """Détaillant bloquant (403/429/DataDome/captcha) — déclenche le circuit breaker."""

    def __init__(self, reason: str, status: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.status = status


def httpx_get(url: str, headers: dict, *, timeout: float = 15.0) -> tuple[int, str, dict]:
    """GET httpx (suit les redirections). Renvoie ``(status, text, headers_lower)``."""
    resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    return resp.status_code, resp.text, {k.lower(): v for k, v in resp.headers.items()}


class HttpRetailSource(RetailSourcePort):
    """Source détaillant concrète : sitemap (nouveaux SKU) + page produit (état/prix)."""

    def __init__(self, retailer: Retailer, *, http_get: HttpGet | None = None,
                 max_sitemap_children: int = 3):
        self.retailer = retailer
        self._get = http_get or httpx_get
        self._max_children = max_sitemap_children

    def _guarded_get(self, url: str, headers: dict | None = None) -> tuple[str, dict]:
        status, text, resp_headers = self._get(url, headers or default_headers())
        reason = classify_block(status, text)
        if reason:
            raise RetailBlocked(reason, status)
        if status >= 400:
            raise RetailBlocked(f"http_{status}", status)
        return text, resp_headers

    def fetch_offer(self, url: str) -> OfferSnapshot:
        text, _ = self._guarded_get(url)
        return parse_offer(text, url)

    def fetch_availability(self, url: str, *, template: str | None = None,
                           sku: str | None = None, etag: str | None = None):
        """Dispo via endpoint XHR JSON (léger) si ``template`` fourni, sinon fetch
        de la page. Requête conditionnelle ETag : 304 → ``(None, etag)`` (inchangé,
        on saute le parsing). Renvoie ``(OfferSnapshot | None, new_etag)``."""
        if not template:
            return self.fetch_offer(url), None
        avail_url = template.replace("{sku}", str(sku or "")).replace("{url}", url)
        headers = {**default_headers(), "Accept": "application/json"}
        if etag:
            headers["If-None-Match"] = etag
        status, text, resp_headers = self._get(avail_url, headers)
        reason = classify_block(status, text)
        if reason:
            raise RetailBlocked(reason, status)
        if status == 304:  # inchangé depuis le dernier check → économie d'octets
            return None, etag
        if status >= 400:
            raise RetailBlocked(f"http_{status}", status)
        new_etag = resp_headers.get("etag")
        try:
            data = json.loads(text) if text else None
        except (ValueError, TypeError):
            data = None
        if data is None:  # endpoint a renvoyé du non-JSON → robustesse : page
            return parse_offer(text, url) if text else self.fetch_offer(url), new_etag
        return parse_availability_json(data, url), new_etag

    def fetch_store_availability(self, url: str, *, template: str, sku: str | None = None,
                                store_code: str | None = None, etag: str | None = None):
        """Dispo MAGASIN via l'endpoint XHR (sélection magasin). Requête
        conditionnelle ETag : 304 → ``(None, etag)``. Renvoie ``((state, price) |
        None, new_etag)``. ``template`` requis (pas de fallback page : la dispo
        magasin n'est pas dans le JSON-LD générique)."""
        avail_url = (template.replace("{sku}", str(sku or ""))
                     .replace("{store_code}", str(store_code or "")).replace("{url}", url))
        headers = {**default_headers(), "Accept": "application/json"}
        if etag:
            headers["If-None-Match"] = etag
        status, text, resp_headers = self._get(avail_url, headers)
        reason = classify_block(status, text)
        if reason:
            raise RetailBlocked(reason, status)
        if status == 304:
            return None, etag
        if status >= 400:
            raise RetailBlocked(f"http_{status}", status)
        try:
            data = json.loads(text) if text else None
        except (ValueError, TypeError):
            data = None
        if data is None:
            return ("unknown", None), resp_headers.get("etag")
        return parse_store_availability_json(data), resp_headers.get("etag")

    def list_catalog_skus(self, retailer: Retailer | None = None) -> Iterable[SkuRef]:
        """Lit le sitemap (recurse 1 niveau sur un index) et filtre les URLs produits."""
        retailer = retailer or self.retailer
        if not retailer.sitemap_url:
            return []
        text, _ = self._guarded_get(retailer.sitemap_url)
        kind, entries = parse_sitemap(text)
        if kind == "sitemapindex":
            collected: list[SkuRef] = []
            # On ne fouille que les sous-sitemaps qui sentent le produit Pokémon.
            children = filter_product_skus(entries) or list(entries)
            for child in children[: self._max_children]:
                try:
                    sub_text, _ = self._guarded_get(child.url)
                except RetailBlocked:
                    raise
                except Exception:  # noqa: BLE001 - un sous-sitemap KO ne casse pas le run
                    continue
                _, sub_entries = parse_sitemap(sub_text)
                collected.extend(sub_entries)
            entries = collected
        return filter_product_skus(entries)
