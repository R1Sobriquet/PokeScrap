"""État du palier courant (persisté dans ``settings.current_tier_number``)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import invalidate_setting
from app.models import Setting, TierConfig

_KEY = "current_tier_number"


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
