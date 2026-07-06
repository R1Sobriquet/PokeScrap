"""État du palier courant.

Multi-user : le palier vit désormais PAR USER (``users.current_tier`` —
``get_user_tier``/``set_user_tier``). Les fonctions historiques adossées à
``settings.current_tier_number`` restent pour la transition (la Phase C threade
les appelants) ; la ligne admin est amorcée depuis cette clé au boot.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import invalidate_setting
from app.models import Setting, TierConfig, User

_KEY = "current_tier_number"


def get_user_tier(db: Session, user_id: int, default: int = 1) -> int:
    """Palier courant d'un utilisateur (``users.current_tier``)."""
    tier = db.scalar(select(User.current_tier).where(User.id == user_id))
    return int(tier) if tier is not None else default


def set_user_tier(db: Session, user_id: int, tier_number: int) -> None:
    """Fixe le palier courant d'un utilisateur."""
    user = db.get(User, user_id)
    if user is not None:
        user.current_tier = tier_number
        db.commit()


def get_current_tier_number(db: Session, default: int = 1) -> int:
    row = db.scalar(select(Setting).where(Setting.setting_key == _KEY))
    if row is None:
        return default
    try:
        return int(row.setting_value)
    except ValueError:
        return default


def set_current_tier(db: Session, tier_number: int) -> None:
    row = db.scalar(select(Setting).where(Setting.setting_key == _KEY))
    if row is None:
        db.add(
            Setting(
                setting_key=_KEY,
                setting_value=str(tier_number),
                value_type="int",
                description="Palier courant (état, mis à jour par le job KPI / confirmation)",
            )
        )
    else:
        row.setting_value = str(tier_number)
    db.commit()
    invalidate_setting(_KEY)


def tier_config_id(db: Session, tier_number: int) -> int | None:
    row = db.scalar(select(TierConfig).where(TierConfig.tier_number == tier_number))
    return row.id if row else None
