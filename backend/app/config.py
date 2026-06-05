"""Configuration de l'application.

Deux niveaux de configuration, volontairement séparés :

* ``Settings`` (pydantic-settings) → **infra & secrets**, chargés depuis ``.env``.
  C'est ici que vivent les identifiants, l'hôte MySQL, les ports, le secret JWT…

* ``get_setting(key)`` → **constantes métier**, lues depuis la table SQL ``settings``
  (le "registre des paramètres figés"). Jamais en dur dans le code. La valeur est
  typée selon la colonne ``value_type`` et mise en cache mémoire ; le cache est
  invalidé explicitement à l'écriture via ``invalidate_setting``.
"""

from __future__ import annotations

import json
import threading
from decimal import Decimal
from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import text


class Settings(BaseSettings):
    """Infra & secrets chargés depuis l'environnement (.env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_env: str = "development"
    app_timezone: str = "Europe/Paris"
    api_port: int = 8000
    frontend_port: int = 5173

    # --- Auth ---
    jwt_secret: str = "change_me"
    jwt_expire_min: int = 720
    admin_username: str = "erwann"
    admin_password: str = "change_me"

    # --- MySQL ---
    db_host: str = "db"
    db_port: int = 3306
    db_name: str = "pokemon_arbitrage"
    db_user: str = "app"
    db_password: str = "change_me"

    # --- PokeTrace (clé serveur uniquement, jamais côté frontend) ---
    poketrace_api_key: str = ""
    poketrace_base_url: str = "https://api.poketrace.com/v1"

    # --- PSA Public API ---
    psa_api_username: str = ""
    psa_api_password: str = ""
    psa_base_url: str = "https://www.psacard.com/publicapi"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    """Singleton des réglages infra (mis en cache pour tout le process)."""
    return Settings()


# ---------------------------------------------------------------------------
#  Registre métier — table `settings`
# ---------------------------------------------------------------------------

_cache: dict[str, Any] = {}
_cache_lock = threading.Lock()


def _coerce(value: str, value_type: str) -> Any:
    """Convertit la valeur stockée (VARCHAR) vers son type Python."""
    if value_type == "int":
        return int(value)
    if value_type == "decimal":
        # Decimal pour la précision, mais comparable à un float/int.
        return Decimal(value)
    if value_type == "bool":
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if value_type == "json":
        return json.loads(value)
    # "string" et tout le reste
    return value


def get_setting(key: str, *, default: Any = None) -> Any:
    """Lit une constante métier depuis la table ``settings`` (typée + cachée).

    La première lecture frappe la base ; les suivantes servent le cache mémoire
    jusqu'à invalidation explicite. Lève ``KeyError`` si la clé est absente et
    qu'aucun ``default`` n'est fourni.
    """
    with _cache_lock:
        if key in _cache:
            return _cache[key]

    # Import local pour éviter une dépendance circulaire config <-> db.
    from app.db import engine

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT setting_value, value_type FROM settings "
                "WHERE setting_key = :k"
            ),
            {"k": key},
        ).first()

    if row is None:
        if default is not None:
            return default
        raise KeyError(f"setting introuvable: {key!r}")

    value = _coerce(row[0], row[1])
    with _cache_lock:
        _cache[key] = value
    return value


def invalidate_setting(key: str | None = None) -> None:
    """Invalide le cache d'un réglage (ou tout le cache si ``key is None``).

    À appeler après toute écriture dans la table ``settings`` (jalons 2+).
    """
    with _cache_lock:
        if key is None:
            _cache.clear()
        else:
            _cache.pop(key, None)
