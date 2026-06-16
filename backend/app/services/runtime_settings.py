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
    ("telegram_enabled", "false", "bool", "Active les notifications Telegram (token/chat_id dans .env)"),
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
