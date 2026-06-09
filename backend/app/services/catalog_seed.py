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


def _scalar(value: Any, *subkeys: str) -> Any:
    """Réduit une valeur à un scalaire. Si ``value`` est un dict, tente ``subkeys``
    (sinon ``None``) ; jamais un dict/list ne sort d'ici → aucune colonne scalaire
    ne reçoit du structuré."""
    if isinstance(value, dict):
        for k in subkeys:
            v = value.get(k)
            if isinstance(v, (str, int, float)):
                return v
        return None
    if isinstance(value, (list, tuple)):
        return None
    return value


def _set_fields(card: dict, entry: dict) -> tuple[Any, Any]:
    """Extrait (set_name, set_slug) — ``set`` peut être un dict {name, slug} ou un str."""
    s = card.get("set")
    if isinstance(s, dict):
        name, slug = s.get("name"), s.get("slug")
    else:
        name = s if isinstance(s, str) else _scalar(card.get("setName"))
        slug = _scalar(card.get("setSlug")) or _scalar(card.get("set_slug"))
    return (entry.get("set") or name, entry.get("set_slug") or slug)


def _ref(card: dict, *keys: str) -> str | None:
    """Extrait un identifiant marketplace scalaire depuis ``refs`` (tolère objets)."""
    refs = card.get("refs") or {}
    if not isinstance(refs, dict):
        return None
    for key in keys:
        v = refs.get(key)
        if isinstance(v, dict):
            v = v.get("id") or v.get("value")
        if v not in (None, ""):
            return str(v)
    return None


def upsert_product(db: Session, card: dict, entry: dict) -> Product:
    """Crée ou met à jour le ``products`` correspondant à une carte PokeTrace.

    Chaque champ imbriqué (``set``, ``refs``, ``image``, ``language``…) est réduit
    à sa valeur scalaire ; aucune colonne ne reçoit un dict brut.
    """
    poketrace_id = _scalar(card.get("id"))
    product = None
    if poketrace_id:
        product = db.scalar(
            select(Product).where(Product.poketrace_id == poketrace_id)
        )
    if product is None:
        product = Product(poketrace_id=poketrace_id)
        db.add(product)

    set_name, set_slug = _set_fields(card, entry)
    number = entry.get("card_number") or _scalar(card.get("cardNumber")) or _scalar(card.get("number"))
    image = _scalar(card.get("image"), "large", "small", "url") or _scalar(card.get("imageUrl"))

    product.product_type = entry.get("product_type", "single")
    product.name = entry.get("name") or _scalar(card.get("name")) or entry.get("search", "")
    product.set_name = set_name
    product.set_slug = set_slug
    product.card_number = (str(number) if number not in (None, "") else None)
    product.variant = entry.get("variant") or _scalar(card.get("variant"))
    product.rarity = entry.get("rarity") or _scalar(card.get("rarity"))
    product.language = entry.get("language") or _scalar(card.get("language"), "code", "name") or "EN"
    product.cardmarket_id = _ref(card, "cardmarketId", "cardmarket", "cardmarket_id") or product.cardmarket_id
    product.tcgplayer_id = _ref(card, "tcgplayerId", "tcgplayer", "tcgplayer_id") or product.tcgplayer_id
    product.image_url = image or product.image_url
    db.flush()  # garantit product.id pour la watchlist
    return product


def upsert_watchlist(db: Session, product: Product, entry: dict) -> Watchlist:
    """Crée ou met à jour la ligne de watchlist d'un produit.

    ``entry['source']`` (défaut 'manual') marque l'origine — une entrée 'manual'
    n'est jamais écrasée par le sync auto des sets.
    """
    watch = db.scalar(
        select(Watchlist).where(Watchlist.product_id == product.id)
    )
    if watch is None:
        watch = Watchlist(product_id=product.id)
        db.add(watch)

    watch.source = entry.get("source", "manual")
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


def add_manual_watchlist(
    db: Session,
    *,
    search: str,
    provider: PriceProvider | None = None,
    market: str = "US",
    **overrides,
) -> dict:
    """Ajout manuel d'un produit à la watchlist (réutilise ``seed_catalog``).

    Lance la recherche PokeTrace, upsert le produit, et ajoute en watchlist avec
    ``source='manual'`` (jamais écrasé par le sync auto). Si la recherche ne
    renvoie rien : aucune création, statut ``not_found``.
    """
    if not (search and search.strip()):
        return {"status": "empty_search", "message": "Le texte de recherche est requis."}

    entry = {"search": search.strip(), "source": "manual"}
    entry.update({k: v for k, v in overrides.items() if v is not None})

    result = seed_catalog(db, [entry], provider=provider, market=market)
    if result["products"] == 0:
        return {"status": "not_found",
                "message": f"Aucun produit trouvé pour « {search.strip()} »."}

    product = db.scalar(
        select(Product).order_by(Product.id.desc())
    )  # le dernier upsert ; suffisant pour le retour UI
    return {"status": "ok", "message": "Produit ajouté à la watchlist (manuel).",
            "product_id": product.id if product else None, **result}
