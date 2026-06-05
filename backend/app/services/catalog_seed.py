"""Seeding du catalogue ``products`` + ``watchlist`` depuis un fichier YAML.

Pour chaque entrée du fichier, on recherche la carte via PokeTrace (``market=US``
au Jalon 2), on **upsert** le produit (id PokeTrace + refs Cardmarket/TCGplayer),
puis on **upsert** la ligne de watchlist avec ses flags. Idempotent : relancer la
commande met à jour sans dupliquer.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.poketrace import PokeTracePriceProvider
from app.adapters.ports import PriceProvider
from app.models import Product, Watchlist

logger = logging.getLogger("services.catalog_seed")


def _first(card: dict, *keys: str) -> Any:
    for key in keys:
        if card.get(key) not in (None, ""):
            return card[key]
    return None


def _refs(card: dict) -> dict:
    return card.get("refs") or {}


def upsert_product(db: Session, card: dict, entry: dict) -> Product:
    """Crée ou met à jour le ``products`` correspondant à une carte PokeTrace."""
    poketrace_id = card.get("id")
    product = None
    if poketrace_id:
        product = db.scalar(
            select(Product).where(Product.poketrace_id == poketrace_id)
        )
    if product is None:
        product = Product(poketrace_id=poketrace_id)
        db.add(product)

    refs = _refs(card)
    product.product_type = entry.get("product_type", "single")
    product.name = entry.get("name") or _first(card, "name") or entry.get("search", "")
    product.set_name = entry.get("set") or _first(card, "set", "setName")
    product.set_slug = entry.get("set_slug") or _first(card, "setSlug", "set_slug")
    product.card_number = str(
        entry.get("card_number") or _first(card, "number", "cardNumber") or ""
    ) or None
    product.rarity = entry.get("rarity") or _first(card, "rarity")
    product.language = entry.get("language") or _first(card, "language") or "EN"
    product.cardmarket_id = _first(refs, "cardmarket", "cardmarket_id") or product.cardmarket_id
    product.tcgplayer_id = _first(refs, "tcgplayer", "tcgplayer_id") or product.tcgplayer_id
    product.image_url = _first(card, "image", "imageUrl") or product.image_url
    db.flush()  # garantit product.id pour la watchlist
    return product


def upsert_watchlist(db: Session, product: Product, entry: dict) -> Watchlist:
    """Crée ou met à jour la ligne de watchlist d'un produit."""
    watch = db.scalar(
        select(Watchlist).where(Watchlist.product_id == product.id)
    )
    if watch is None:
        watch = Watchlist(product_id=product.id)
        db.add(watch)

    watch.tier = entry.get("tier", "B")
    watch.is_trinity = 1 if entry.get("is_trinity") else 0
    watch.is_illustration_rare = 1 if entry.get("is_illustration_rare") else 0
    if entry.get("min_discount_pct") is not None:
        watch.min_discount_pct = entry["min_discount_pct"]
    if entry.get("target_resale_hours") is not None:
        watch.target_resale_hours = entry["target_resale_hours"]
    if entry.get("priority_coef") is not None:
        watch.priority_coef = entry["priority_coef"]
    watch.keywords = entry.get("keywords")
    watch.notes = entry.get("notes")
    watch.is_active = 0 if entry.get("is_active") is False else 1
    return watch


def seed_catalog(
    db: Session,
    entries: list[dict],
    *,
    provider: PriceProvider | None = None,
    market: str = "US",
) -> dict[str, int]:
    """Peuple ``products`` + ``watchlist`` depuis les entrées YAML.

    Renvoie un compte ``{products, watchlist, skipped}``.
    """
    provider = provider or PokeTracePriceProvider()
    result = {"products": 0, "watchlist": 0, "skipped": 0}

    for entry in entries:
        query = entry.get("search") or entry.get("name")
        if not query:
            logger.warning("Entrée sans 'search'/'name' — ignorée : %s", entry)
            result["skipped"] += 1
            continue

        hits = provider.search_cards(query, market=market, limit=5)
        if not hits:
            logger.warning("Aucun résultat PokeTrace pour %r — ignoré.", query)
            result["skipped"] += 1
            continue

        card = hits[0]  # meilleur match (l'API trie par pertinence)
        product = upsert_product(db, card, entry)
        upsert_watchlist(db, product, entry)
        result["products"] += 1
        result["watchlist"] += 1

    db.commit()
    logger.info(
        "Seeding terminé : %s produits, %s watchlist, %s ignorés.",
        result["products"],
        result["watchlist"],
        result["skipped"],
    )
    return result
