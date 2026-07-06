"""Préférences PER-USER — overlay typé du registre global ``settings``.

Résolution : ``user_settings(user_id, clé)`` → sinon ``get_setting(clé)`` (le
registre global reste la source des **défauts**, zéro seeding par utilisateur).
Même coercion de types que le registre (int/decimal/bool/json/string). Pas de
cache : les lectures per-user sont rares (services threadés) et une valeur
fraîche évite tout partage d'état entre requêtes de users différents.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import _coerce, get_setting
from app.models import UserSetting


def get_user_setting(db: Session, user_id: int, key: str, *, default: Any = None) -> Any:
    """Valeur effective d'une clé pour un utilisateur (override → global → default)."""
    row = db.scalar(select(UserSetting).where(
        UserSetting.user_id == user_id, UserSetting.setting_key == key,
    ))
    if row is not None and row.setting_value is not None:
        return _coerce(row.setting_value, row.value_type)
    return get_setting(key, default=default)


def set_user_setting(db: Session, user_id: int, key: str, value: str,
                     value_type: str = "string") -> None:
    """Écrit (upsert) l'override d'une clé pour un utilisateur."""
    row = db.scalar(select(UserSetting).where(
        UserSetting.user_id == user_id, UserSetting.setting_key == key,
    ))
    if row is None:
        db.add(UserSetting(user_id=user_id, setting_key=key,
                           setting_value=value, value_type=value_type))
    else:
        row.setting_value = value
        row.value_type = value_type
    db.commit()


def clear_user_setting(db: Session, user_id: int, key: str) -> None:
    """Supprime l'override (retour au défaut global). Silencieux si absent."""
    row = db.scalar(select(UserSetting).where(
        UserSetting.user_id == user_id, UserSetting.setting_key == key,
    ))
    if row is not None:
        db.delete(row)
        db.commit()
