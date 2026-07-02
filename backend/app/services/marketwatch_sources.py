"""Assemble les sources de prix carte-centric activées (flags ``settings``/env).

Clés/secrets lus via ``settings`` avec repli ``.env`` (jamais en dur), comme le
moat marché. Cardmarket = fichiers (URL/chemin configurables). PPT & eBay ne
passent QUE les cartes ciblées (watchlist matchée sur ``products.tcgdex_id``),
pour honorer les quotas.
"""

from __future__ import annotations

import datetime as dt
import logging
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.marketwatch.domain import RegistryCard
from app.marketwatch.registry import load_registry
from app.models import Product, TcgdexCard, Watchlist

logger = logging.getLogger("services.marketwatch_sources")


def _cfg(setting_key: str, env_key: str, default: str = "") -> str:
    return str(get_setting(setting_key, default="") or os.getenv(env_key, "") or default)


def _watched_registry_cards(db: Session) -> list[RegistryCard]:
    """Cartes de la watchlist active rapprochées d'un ``card_id`` TCGdex."""
    rows = db.execute(
        select(Product).join(Watchlist, Watchlist.product_id == Product.id)
        .where(Watchlist.is_active == 1, Product.tcgdex_id.is_not(None))
    ).scalars().all()
    out: list[RegistryCard] = []
    for p in rows:
        card = db.get(TcgdexCard, p.tcgdex_id)
        if card is not None:
            out.append(RegistryCard(
                card_id=card.card_id, set_id=card.set_id, set_name=card.set_name,
                number=card.number, name_en=card.name_en, name_fr=card.name_fr,
                name_jp=card.name_jp))
        else:  # pas encore dans le registre → on retombe sur les champs produit
            out.append(RegistryCard(card_id=str(p.tcgdex_id), set_name=p.set_name,
                                    number=p.card_number, name_en=p.name))
    return out


def build_card_sources(db: Session, *, today: dt.date | None = None) -> list:
    """Liste des ``CardPriceSource`` activées (peut être vide)."""
    today = today or dt.date.today()
    sources: list = []

    # --- Cardmarket (fichiers quotidiens) ---
    if bool(get_setting("marketwatch_cardmarket_enabled", default=True)):
        products_url = _cfg("marketwatch_cardmarket_products_url", "MARKETWATCH_CARDMARKET_PRODUCTS_URL")
        guide_url = _cfg("marketwatch_cardmarket_priceguide_url", "MARKETWATCH_CARDMARKET_PRICEGUIDE_URL")
        if products_url and guide_url:
            from app.marketwatch.sources.cardmarket_file import CardmarketFileSource
            lang = _cfg("marketwatch_cardmarket_lang", "MARKETWATCH_CARDMARKET_LANG", "EN")
            try:
                sources.append(CardmarketFileSource.from_files(
                    products_url, guide_url, load_registry(db), language=lang))
            except Exception:  # noqa: BLE001 - fichier indispo ne casse pas le run
                logger.exception("cardmarket: chargement des fichiers impossible.")
        else:
            logger.info("cardmarket: URLs/chemins non configurés — source ignorée.")

    targets = _watched_registry_cards(db)

    # --- PPT (US+EU) sur cartes ciblées ---
    if bool(get_setting("marketwatch_ppt_enabled", default=False)) and targets:
        key = _cfg("ppt_api_key", "PPT_API_KEY")
        if key:
            from app.marketdata.sources.ppt import PokemonPriceTrackerAdapter
            from app.marketwatch.sources.ppt_cards import PptCardSource
            fx = float(get_setting("fx_usd_eur", default=0.92))
            sources.append(PptCardSource(targets, PokemonPriceTrackerAdapter(api_key=key),
                                         fx_usd_eur=fx, captured_at=today))

    # --- eBay annonces actives sur cartes ciblées ---
    if bool(get_setting("marketwatch_ebay_enabled", default=False)) and targets:
        cid = _cfg("ebay_client_id", "EBAY_CLIENT_ID")
        secret = _cfg("ebay_client_secret", "EBAY_CLIENT_SECRET")
        if cid and secret:
            try:
                from app.marketdata.sources.ebay import EbayBrowseAdapter
                from app.marketwatch.sources.ebay_active import EbayActiveCardSource
                sources.append(EbayActiveCardSource(
                    targets, EbayBrowseAdapter(client_id=cid, client_secret=secret),
                    captured_at=today))
            except Exception:  # noqa: BLE001
                logger.exception("ebay: adapter indisponible — source ignorée.")

    return sources
