"""Source Cardmarket = FICHIERS publics quotidiens (price-guide + catalogue).

L'API Cardmarket est fermée et le scraping bloqué (DataDome) → on consomme les
**fichiers en téléchargement quotidien** : un price-guide (low/avg/trend par
``idProduct``) et un catalogue produits (``idProduct`` ↔ nom/extension/numéro).

URL/chemins configurables (setting + env, repli fichier local pour tests/offline).
Le parsing est **défensif** (les noms de champs varient) ; chaque ``idProduct``
non rapproché d'une carte TCGdex est compté et journalisé (jamais bloquant).

``captured_at`` = date du fichier → ré-ingestion le même jour = upsert, sans doublon.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

import httpx

from app.marketwatch.domain import CardmarketProduct, CardSnapshot, RegistryCard
from app.marketwatch.matcher import AUTO_CONFIDENCE, match_cardmarket
from app.marketwatch.ports import CardPriceSource

logger = logging.getLogger("marketwatch.cardmarket")


def _dec(v) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _first(d: dict, *keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _parse_date(value) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def parse_products(raw) -> list[CardmarketProduct]:
    """Catalogue → liste de ``CardmarketProduct`` (défensif sur les champs)."""
    rows = raw.get("products") if isinstance(raw, dict) else raw
    out: list[CardmarketProduct] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        idp = _first(r, "idProduct", "id_product", "id")
        name = _first(r, "name", "enName", "localName")
        if idp is None or not name:
            continue
        out.append(CardmarketProduct(
            id_product=str(idp), name=str(name),
            expansion=(_first(r, "expansionName", "expansion", "idExpansion") and
                       str(_first(r, "expansionName", "expansion", "idExpansion"))),
            number=(_first(r, "number", "collectorNumber", "nr", "cardNumber") and
                    str(_first(r, "number", "collectorNumber", "nr", "cardNumber"))),
        ))
    return out


def parse_price_guide(raw) -> dict[str, dict]:
    """Price-guide → ``{idProduct: {avg, low, trend}}`` (défensif)."""
    rows = None
    if isinstance(raw, dict):
        rows = raw.get("priceGuides") or raw.get("priceguides") or raw.get("data")
    if rows is None:
        rows = raw
    out: dict[str, dict] = {}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        idp = _first(r, "idProduct", "id_product", "id")
        if idp is None:
            continue
        out[str(idp)] = {
            "avg": _dec(_first(r, "avg", "avgPrice", "averagePrice", "avg7", "avg30")),
            "low": _dec(_first(r, "low", "lowPrice", "ll")),
            "trend": _dec(_first(r, "trend", "trendPrice")),
        }
    return out


def _load(src: str, opener=None) -> object:
    """Charge un JSON depuis une URL (http) ou un chemin local."""
    if opener is not None:
        return opener(src)
    if src.startswith("http://") or src.startswith("https://"):
        resp = httpx.get(src, timeout=60.0, follow_redirects=True)
        resp.raise_for_status()
        return resp.json()
    with open(src, encoding="utf-8") as fh:
        return json.load(fh)


class CardmarketFileSource(CardPriceSource):
    code = "cardmarket"

    def __init__(
        self,
        products: Sequence[CardmarketProduct],
        price_guide: dict[str, dict],
        registry: Sequence[RegistryCard],
        *,
        captured_at: dt.date,
        language: str = "EN",
        min_confidence: float = AUTO_CONFIDENCE,
    ):
        self._products = list(products)
        self._guide = price_guide
        self._registry = list(registry)
        self._captured_at = captured_at
        self._language = language
        self._min_conf = min_confidence
        #: produits non rapprochés (pour log / match_review) : (product, match|None)
        self.unmatched: list[tuple[CardmarketProduct, object]] = []

    @classmethod
    def from_files(cls, products_src: str, priceguide_src: str, registry, *,
                   language: str = "EN", opener=None, **kw) -> CardmarketFileSource:
        prods_raw = _load(products_src, opener)
        guide_raw = _load(priceguide_src, opener)
        file_date = (_parse_date(_first(guide_raw, "createdAt", "date"))
                     if isinstance(guide_raw, dict) else None)
        return cls(
            parse_products(prods_raw), parse_price_guide(guide_raw), registry,
            captured_at=file_date or dt.date.today(), language=language, **kw,
        )

    def fetch(self) -> list[CardSnapshot]:
        out: list[CardSnapshot] = []
        self.unmatched = []
        for prod in self._products:
            row = self._guide.get(prod.id_product)
            if not row:
                continue
            price = row.get("trend") or row.get("avg")
            if price is None:
                continue
            m = match_cardmarket(prod, self._registry)
            if m is None or m.confidence < self._min_conf:
                self.unmatched.append((prod, m))
                continue
            out.append(CardSnapshot(
                card_id=m.card_id, source="cardmarket", language=self._language,
                price_eur=price, price_native=price, currency="EUR",
                trend_eur=row.get("trend"), captured_at=self._captured_at,
                meta={"id_product": prod.id_product, "confidence": m.confidence,
                      "method": m.method, "low": str(row.get("low") or "")},
            ))
        if self.unmatched:
            logger.info("cardmarket: %d produits non rapprochés (sur %d).",
                        len(self.unmatched), len(self._products))
        return out
