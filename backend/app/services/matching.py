"""Matching annonce → produit(s) — MVP mots-clés (pur, testable).

Compare un ``raw_title`` aux produits de la watchlist (nom / set / numéro /
keywords) et renvoie des ``detected_products`` avec une confiance graduée, plus
une estimation du nombre total de cartes (regex sur le titre).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Confiances graduées.
CONFIDENCE_SET_NUMBER = 0.95  # set + numéro exacts
CONFIDENCE_NAME = 0.75        # nom du produit
CONFIDENCE_KEYWORD = 0.55     # mot-clé large

_QTY_PATTERNS = [
    re.compile(r"lot\s+de\s+(\d+)", re.I),
    re.compile(r"(\d+)\s*cartes", re.I),
    re.compile(r"\bx\s*(\d+)\b", re.I),
    re.compile(r"\b(\d+)\s*pcs?\b", re.I),
]


@dataclass(frozen=True)
class MatchProduct:
    product_id: int
    name: str | None = None
    set_name: str | None = None
    set_slug: str | None = None
    card_number: str | None = None
    keywords: str | None = None
    is_illustration_rare: bool = False


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def estimate_total_cards(title: str, *, default_single: int = 1, default_lot: int = 30) -> int:
    """Extrait une quantité du titre ; sinon heuristique (lot → défaut, sinon 1)."""
    for pat in _QTY_PATTERNS:
        m = pat.search(title)
        if m:
            try:
                value = int(m.group(1))
                if value > 0:
                    return value
            except ValueError:
                continue
    return default_lot if "lot" in _norm(title) else default_single


def _confidence(title_n: str, product: MatchProduct) -> float:
    set_token = _norm(product.set_name) if product.set_name else (
        _norm(product.set_slug.replace("-", " ")) if product.set_slug else None
    )
    number = str(product.card_number).lower() if product.card_number else None
    if set_token and number and set_token in title_n and re.search(rf"\b{re.escape(number)}\b", title_n):
        return CONFIDENCE_SET_NUMBER
    if product.name and _norm(product.name) in title_n:
        return CONFIDENCE_NAME
    if product.keywords:
        for kw in product.keywords.split("|"):
            kw = _norm(kw.strip())
            if kw and kw in title_n:
                return CONFIDENCE_KEYWORD
    return 0.0


def match_listing(
    raw_title: str,
    products: list[MatchProduct],
    *,
    default_lot: int = 30,
) -> tuple[list[dict], int]:
    """Renvoie ``(detected_products, estimated_total_cards)``.

    ``detected_products`` = ``[{product_id, confidence, is_illustration_rare}]``
    pour chaque produit ayant une confiance > 0 (le filtrage ≥
    ``min_match_confidence`` est fait en aval, cohérent avec J3).
    """
    title_n = _norm(raw_title)
    detected: list[dict] = []
    for product in products:
        conf = _confidence(title_n, product)
        if conf > 0:
            detected.append(
                {
                    "product_id": product.product_id,
                    "confidence": conf,
                    "is_illustration_rare": product.is_illustration_rare,
                }
            )
    detected.sort(key=lambda d: d["confidence"], reverse=True)
    return detected, estimate_total_cards(raw_title, default_lot=default_lot)
