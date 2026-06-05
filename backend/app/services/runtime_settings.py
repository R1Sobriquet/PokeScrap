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
