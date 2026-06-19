"""Parsing pur d'une page produit → ``OfferSnapshot`` (zéro I/O, testable).

Priorité au **JSON-LD** schema.org (``Product``/``Offer``) ; **fallback DOM**
uniquement si aucun nœud ``Product`` JSON-LD n'est trouvé (cf. brief).
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from app.retail.domain import (
    IN_STOCK,
    OUT_OF_STOCK,
    PREORDER,
    UNKNOWN,
    OfferSnapshot,
    normalize_availability,
)

_PREORDER_HINTS = ("précommande", "precommande", "pré-commande", "pre-order", "preorder", "présale")
_OOS_HINTS = ("rupture", "indisponible", "épuisé", "epuise", "out of stock", "non disponible",
              "produit épuisé", "victime de son succès")
_INSTOCK_HINTS = ("ajouter au panier", "add to cart", "en stock", "disponible", "ajouter au panier")


def _to_decimal(value) -> Decimal | None:
    """Convertit un prix hétérogène ('29,99', '29.99', 29.9) en ``Decimal``."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    s = str(value).strip().replace("\xa0", "").replace(" ", "")
    s = s.replace("€", "").replace("EUR", "")
    if "," in s and "." in s:  # '1.299,99' → '1299.99'
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _flatten(data):
    """Aplati listes et ``@graph`` pour itérer sur tous les nœuds JSON-LD."""
    if isinstance(data, list):
        for d in data:
            yield from _flatten(d)
    elif isinstance(data, dict):
        graph = data.get("@graph")
        if isinstance(graph, list):
            for d in graph:
                yield from _flatten(d)
        yield data


def _iter_jsonld(soup: BeautifulSoup):
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (tag.string or tag.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        yield from _flatten(data)


def _first_image(value) -> str | None:
    """Extrait une URL d'image depuis ``image`` JSON-LD (str | list | ImageObject)."""
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        u = value.get("url") or value.get("contentUrl")
        return u if isinstance(u, str) and u else None
    if isinstance(value, list):
        for item in value:
            u = _first_image(item)
            if u:
                return u
    return None


def _is_product(node: dict) -> bool:
    t = node.get("@type")
    if isinstance(t, list):
        return any(str(x).lower() == "product" for x in t)
    return str(t).lower() == "product"


def _first_offer(offers):
    """Renvoie le premier ``Offer`` exploitable (dict), depuis un dict ou une liste."""
    if isinstance(offers, dict):
        if offers.get("@type") in ("AggregateOffer", "aggregateoffer"):
            sub = offers.get("offers")
            if sub:
                return _first_offer(sub)
        return offers
    if isinstance(offers, list):
        for o in offers:
            if isinstance(o, dict):
                return o
    return None


def parse_jsonld_offer(html: str, url: str) -> OfferSnapshot | None:
    """Extrait l'offre depuis le JSON-LD ``Product`` ; ``None`` si absent."""
    soup = BeautifulSoup(html, "html.parser")
    for node in _iter_jsonld(soup):
        if not _is_product(node):
            continue
        offer = _first_offer(node.get("offers")) or {}
        spec = offer.get("priceSpecification") if isinstance(offer, dict) else None
        spec = spec if isinstance(spec, dict) else {}
        state = normalize_availability(offer.get("availability"))
        price = _to_decimal(offer.get("price") or spec.get("price"))
        currency = offer.get("priceCurrency") or spec.get("priceCurrency") or "EUR"
        sku = node.get("sku") or node.get("mpn")
        return OfferSnapshot(
            url=url,
            stock_state=state,
            price=price,
            currency=str(currency)[:3] or "EUR",
            title=node.get("name"),
            image=_first_image(node.get("image")),
            retailer_sku=str(sku) if sku else None,
            source="jsonld",
        )
    return None


def parse_dom_offer(html: str, url: str) -> OfferSnapshot:
    """Fallback DOM : déduit l'état stock du texte/boutons et le prix des meta."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True).lower()

    if any(k in text for k in _PREORDER_HINTS):
        state = PREORDER
    elif any(k in text for k in _OOS_HINTS):
        state = OUT_OF_STOCK
    elif any(k in text for k in _INSTOCK_HINTS):
        state = IN_STOCK
    else:
        state = UNKNOWN

    price = None
    currency = "EUR"
    for attrs in ({"itemprop": "price"}, {"property": "product:price:amount"}):
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content"):
            price = _to_decimal(meta["content"])
            break
    for attrs in ({"itemprop": "priceCurrency"}, {"property": "product:price:currency"}):
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content"):
            currency = str(meta["content"])[:3] or "EUR"
            break

    title = None
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        title = og["content"]
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()

    image = None
    ogimg = soup.find("meta", attrs={"property": "og:image"}) or soup.find(
        "meta", attrs={"name": "og:image"}
    )
    if ogimg and ogimg.get("content"):
        image = ogimg["content"]

    return OfferSnapshot(
        url=url, stock_state=state, price=price, currency=currency, title=title,
        image=image, source="dom",
    )


def parse_offer(html: str, url: str) -> OfferSnapshot:
    """JSON-LD prioritaire, fallback DOM si aucun ``Product`` JSON-LD."""
    return parse_jsonld_offer(html, url) or parse_dom_offer(html, url)
