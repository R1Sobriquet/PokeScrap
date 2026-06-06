"""Parsing HTML → ``RawListing`` (pur, testable sur fixtures).

Détection de casse bruyante : 0 conteneur là où on attend des résultats, ou trop
de cartes sans champ obligatoire (titre/prix) → structure considérée cassée
(``ParseResult.broken``) plutôt que d'insérer du vide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.scraping.models import RawListing

_ID_RE = re.compile(r"(\d{5,})")


@dataclass(frozen=True)
class ParseResult:
    listings: list[RawListing]
    broken: bool
    reason: str | None = None


def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    t = text.replace(" ", " ").replace("\xa0", " ")
    t = re.sub(r"[^0-9,.\s]", "", t).replace(" ", "").strip()
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _text(node) -> str | None:
    return node.get_text(strip=True) if node else None


def _external_id(card, sel: dict, href: str | None) -> str | None:
    attr = sel.get("external_id_attr")
    if attr and card.has_attr(attr):
        return str(card[attr])
    if href:
        m = _ID_RE.search(href)
        if m:
            return m.group(1)
    return None


def parse_listings(
    html: str,
    sel: dict,
    *,
    platform: str,
    break_threshold: float,
    base_url: str = "",
) -> ParseResult:
    base_url = base_url or sel.get("base_url", "")
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(sel["container"]) if sel.get("container") else []
    if not cards:
        return ParseResult([], True, f"0 conteneur pour {platform} (sélecteur '{sel.get('container')}')")

    listings: list[RawListing] = []
    missing = 0
    for card in cards:
        title = _text(card.select_one(sel["title"])) if sel.get("title") else None
        price = parse_price(_text(card.select_one(sel["price"])) if sel.get("price") else None)
        if not title or price is None:
            missing += 1
            continue

        link_node = card.select_one(sel["link"]) if sel.get("link") else None
        href = link_node.get("href") if link_node else None
        url = urljoin(base_url, href) if href else (base_url or "")
        ext = _external_id(card, sel, href) or url

        shipping = parse_price(_text(card.select_one(sel["shipping"]))) if sel.get("shipping") else None
        location = _text(card.select_one(sel["location"])) if sel.get("location") else None

        listings.append(
            RawListing(
                platform=platform,
                external_id=str(ext),
                url=url,
                raw_title=title,
                asking_price=price,
                shipping_cost=shipping or 0.0,
                location=location,
            )
        )

    total = len(cards)
    if total and (missing / total * 100.0) > break_threshold:
        return ParseResult(
            [], True, f"{missing}/{total} cartes sans titre/prix sur {platform} — sélecteurs à mettre à jour"
        )
    return ParseResult(listings, False, None)
