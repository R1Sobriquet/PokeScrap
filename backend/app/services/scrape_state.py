"""État de blocage par plateforme (backoff exponentiel, persisté en settings).

On ne contourne jamais un blocage : on s'arrête sur la plateforme et on attend.
L'état (``until`` + ``count``) vit dans une ligne ``settings`` JSON pour survivre
aux redémarrages du conteneur scraper.
"""

from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import invalidate_setting
from app.models import Setting

_KEY = "scrape_block_state"
_BASE_MIN = 15  # 1er backoff ; double à chaque blocage consécutif, plafonné


def _load(db: Session) -> dict:
    row = db.scalar(select(Setting).where(Setting.setting_key == _KEY))
    if row is None or not row.setting_value:
        return {}
    try:
        return json.loads(row.setting_value)
    except json.JSONDecodeError:
        return {}


def _save(db: Session, state: dict) -> None:
    row = db.scalar(select(Setting).where(Setting.setting_key == _KEY))
    value = json.dumps(state)
    if row is None:
        db.add(Setting(setting_key=_KEY, setting_value=value, value_type="json",
                       description="État de backoff scraping par plateforme (auto)"))
    else:
        row.setting_value = value
    db.commit()
    invalidate_setting(_KEY)


def is_blocked(db: Session, platform: str, now: dt.datetime) -> bool:
    entry = _load(db).get(platform)
    if not entry or not entry.get("until"):
        return False
    return now < dt.datetime.fromisoformat(entry["until"])


def record_block(db: Session, platform: str, now: dt.datetime, *, cooldown_cap_min: int) -> int:
    state = _load(db)
    count = int(state.get(platform, {}).get("count", 0)) + 1
    minutes = min(cooldown_cap_min, _BASE_MIN * (2 ** (count - 1)))
    state[platform] = {"until": (now + dt.timedelta(minutes=minutes)).isoformat(), "count": count}
    _save(db, state)
    return minutes


def clear_block(db: Session, platform: str) -> None:
    state = _load(db)
    if platform in state:
        state.pop(platform)
        _save(db, state)
