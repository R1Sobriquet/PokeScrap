"""Amorçage idempotent des réglages métier ajoutés après l'init du schéma.

``db/schema.sql`` seede le registre pour les **nouvelles** installations. Pour une
base déjà initialisée (volume persistant du Jalon 1), cette fonction insère les
clés manquantes sans écraser les valeurs existantes — « passer en Pro » reste une
simple édition de ligne.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import invalidate_setting
from app.models import Setting

logger = logging.getLogger("services.runtime_settings")

#: (clé, valeur, type, description) — défauts mode Free.
RUNTIME_SETTING_DEFAULTS: list[tuple[str, str, str, str]] = [
    ("price_cache_ttl_min", "360", "int", "Ne pas re-requêter un prix plus jeune que N minutes"),
    ("poketrace_daily_limit", "250", "int", "Quota requêtes/jour PokeTrace (Free 250, Pro 10000)"),
    ("poketrace_min_interval_ms", "2000", "int", "Intervalle min entre requêtes (burst Free 1/2s)"),
    ("valuation_marketplace", "tcgplayer", "string", "Marketplace de valorisation (tcgplayer|ebay|cardmarket)"),
    ("fx_usd_eur", "0.92", "decimal", "Conversion proxy US→EUR en mode prototype"),
    ("dispatcher_poll_sec", "20", "int", "Période de la boucle d'envoi des alertes (secondes)"),
    ("scrape_max_listings_per_run", "40", "int", "Plafond d'annonces traitées par run de scraping"),
    ("scrape_blocked_cooldown_min", "120", "int", "Cooldown max (min) après blocage plateforme"),
    ("selector_break_threshold", "30", "int", "% de cartes sans champ obligatoire = structure cassée"),
    ('saved_queries', '["lot cartes pokemon","display prismatic evolutions"]', "json", "Requêtes de sourcing sauvegardées"),
    ("scrape_vinted_enabled", "true", "bool", "Active le scraping Vinted (toggle par source)"),
    ("scrape_leboncoin_enabled", "true", "bool", "Active le scraping LeBoncoin (toggle par source)"),
    ("scrape_max_queries_per_run", "1", "int", "Nb de recherches par source par run (rythme lent)"),
    ("sourcing_scraping_enabled", "false", "bool", "Active le scraping AUTO (off : DataDome ; sourcing manuel OK)"),
    ("tracked_sets_max_pages", "5", "int", "Pages max paginées par set/sync (quota PokeTrace)"),
    ("tracked_sets_page_size", "50", "int", "Taille de page pour le sync des sets"),
    ("movers_min_volume", "5", "int", "Volume minimal de ventes pour qu'un mover compte (anti-bruit)"),
    ("movers_top_n", "10", "int", "Nombre de top movers exposés par set"),
    ("job_heartbeat_max_age_min", "720", "int", "Âge max (min) d'un job critique avant dead-man's switch"),
    ("price_snapshot_detail_days", "60", "int", "Fenêtre détaillée des price_snapshots"),
    ("price_snapshot_pruning_enabled", "false", "bool", "Active l'élagage intraday des price_snapshots"),
    ("log_redact_secrets", "true", "bool", "Masque les secrets dans les logs"),
    # PokéStock FR — veille restock (défauts prudents : sourcing OFF, dry-run ON)
    ("retail_sourcing_enabled", "false", "bool", "Active le sourcing veille restock (master switch PokéStock FR)"),
    ("retail_dry_run", "true", "bool", "Mode dry-run : log les transitions sans créer d'alerte"),
    ("retail_cultura_enabled", "true", "bool", "Active le détaillant Cultura"),
    ("retail_fnac_enabled", "false", "bool", "Active le détaillant Fnac (WAF agressif : prudence)"),
    ("retail_micromania_enabled", "true", "bool", "Active le détaillant Micromania"),
    ("retail_check_interval_min", "60", "int", "Intervalle min (min) entre deux checks restock d'une offre"),
    ("retail_request_cap_per_run", "40", "int", "Plafond de requêtes HTTP par run de job retail"),
    ("retail_min_delay_ms", "3000", "int", "Délai min (ms) entre deux requêtes vers un même détaillant"),
    ("retail_restock_cooldown_min", "360", "int", "Cooldown (min) avant ré-alerte sur une même offre"),
    ("retail_circuit_max_errors", "5", "int", "Erreurs consécutives avant circuit breaker d'un détaillant"),
    ("restock_min_flip_pct", "0", "decimal", "Restock : alerte instantanée seulement si upside NET (marché vs MSRP) ≥ N% (sinon digest)"),
    ("resale_fee_pct", "12", "decimal", "Frais de revente (%) déduits pour le flip net (marketplace + port)"),
    ("flip_alert_min_pct", "25", "decimal", "Flip Radar : alerte proactive si une offre en stock dépasse N% net"),
    # Phase A — latence online (hot-list à plusieurs niveaux, défauts prudents).
    ("retail_tier_hot_sec", "45", "int", "Intervalle (s) de check des offres tier 'hot' (agressif)"),
    ("retail_tier_normal_min", "5", "int", "Intervalle (min) de check des offres tier 'normal'"),
    ("retail_tier_cold_min", "60", "int", "Intervalle (min) de check des offres tier 'cold'"),
    ("retail_poll_interval_sec", "45", "int", "Période (s) du job de poll restock (tier pilote la cadence réelle)"),
    ("retail_bucket_capacity", "12", "int", "Token bucket par enseigne : capacité (burst max de requêtes)"),
    ("retail_bucket_refill_per_sec", "0.25", "decimal", "Token bucket : tokens rechargés/s (débit soutenu max/enseigne)"),
    # Phase B — dispo en magasin (zone Agen). Plus lent que le hot online.
    ("retail_store_stock_enabled", "false", "bool", "Active la veille dispo en magasin (sous retail_sourcing_enabled)"),
    ("retail_store_check_interval_min", "60", "int", "Intervalle min (min) entre deux checks d'un (offre,magasin)"),
    ("retail_store_request_cap_per_run", "30", "int", "Plafond de requêtes par run du job dispo magasin"),
    ("telegram_enabled", "false", "bool", "Active les notifications Telegram (token/chat_id dans .env)"),
    # Moat de données marché — multi-sources (défauts prudents : tout OFF, watched-only)
    ("marketdata_enabled", "false", "bool", "Master switch du moat de données marché"),
    ("marketdata_ppt_enabled", "false", "bool", "Active la source PokemonPriceTracker (clé requise)"),
    ("marketdata_tcgdex_enabled", "true", "bool", "Active TCGdex (catalogue/calendrier, gratuit sans clé)"),
    ("marketdata_ebay_enabled", "false", "bool", "Active eBay Browse (annonces FR, OAuth requis)"),
    ("marketdata_request_cap_per_run_ppt", "90", "int", "Plafond requêtes/run PPT (quota free 100/j, marge)"),
    ("marketdata_request_cap_per_run_tcgdex", "60", "int", "Plafond requêtes/run TCGdex"),
    ("marketdata_request_cap_per_run_ebay", "40", "int", "Plafond requêtes/run eBay Browse"),
    ("marketdata_min_delay_ms", "1500", "int", "Délai min (ms) entre requêtes d'une même source marché"),
    ("marketdata_circuit_max_errors", "5", "int", "Erreurs consécutives avant circuit breaker d'une source"),
    ("match_confidence_threshold", "0.82", "decimal", "Seuil d'auto-acceptation du matching (sinon match_review)"),
    ("alert_digest_enabled", "false", "bool", "Regroupe les events non urgents en 1 digest/jour"),
    ("alert_digest_hour", "9", "int", "Heure (locale Paris) d'envoi du digest quotidien"),
    ("restock_debounce_min", "30", "int", "Anti-flapping : ignore les oscillations d'état sous N minutes"),
    ("source_health_fresh_max_age_h", "30", "int", "Âge max (h) d'un snapshot avant 'source muette'"),
    ("source_health_min_volume", "1", "int", "Volume min attendu par run avant 'source cassée'"),
    ("sanity_bounds_eur", '{"etb":[15,400],"display":[60,900],"upc":[40,400],"coffret":[15,400],"booster":[2,60],"bundle":[15,300],"autre":[1,5000]}', "json", "Bornes de sanité prix EUR par product_type (rejet → quarantaine)"),
]


def ensure_runtime_settings(db: Session) -> int:
    """Insère les réglages manquants. Renvoie le nombre de lignes ajoutées."""
    existing = set(db.scalars(select(Setting.setting_key)).all())
    added = 0
    for key, value, value_type, description in RUNTIME_SETTING_DEFAULTS:
        if key not in existing:
            db.add(
                Setting(
                    setting_key=key,
                    setting_value=value,
                    value_type=value_type,
                    description=description,
                )
            )
            added += 1
    if added:
        db.commit()
        invalidate_setting()
        logger.info("Réglages runtime amorcés : %s ajoutés.", added)
    return added
