"""Observabilité : heartbeats de jobs, agrégat ``/status``, dead-man's switch.

La fraîcheur est dérivée des **données** (max captured_at, etc.) et de rows
``settings`` ``heartbeat:<job>`` écrites par les workers. Le dead-man's switch
couvre le cas « tout est silencieux parce que c'est cassé ».
"""

from __future__ import annotations

import datetime as dt
import os
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_setting, invalidate_setting
from app.models import AccountSnapshot, Alert, PriceSnapshot, Setting, SourcingListing

HB_PREFIX = "heartbeat:"
LAST_BACKUP_KEY = "last_backup_at"
HEARTBEAT_FILE = os.getenv("HEARTBEAT_FILE", "/tmp/heartbeat")

# Jobs « toujours actifs » surveillés par le dead-man's switch.
DEADMAN_JOBS = ("scheduler", "bot", "scraper")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _parse(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def _age_min(ts: dt.datetime | None, now: dt.datetime) -> float | None:
    if ts is None:
        return None
    return round((now - ts).total_seconds() / 60.0, 1)


def _upsert(db: Session, key: str, value: str, value_type: str = "string") -> None:
    row = db.scalar(select(Setting).where(Setting.setting_key == key))
    if row is None:
        db.add(Setting(setting_key=key, setting_value=value, value_type=value_type,
                       description="Observabilité (auto)"))
    else:
        row.setting_value = value
    db.commit()
    invalidate_setting(key)


def touch_heartbeat_file(path: str = HEARTBEAT_FILE) -> None:
    """Liveness fichier pour le healthcheck Docker des workers."""
    try:
        with open(path, "w") as fh:
            fh.write(str(time.time()))
    except OSError:
        pass


def record_heartbeat(db: Session, job: str, now: dt.datetime | None = None) -> None:
    _upsert(db, HB_PREFIX + job, (now or _utcnow()).isoformat())


def record_backup(db: Session, now: dt.datetime | None = None) -> None:
    _upsert(db, LAST_BACKUP_KEY, (now or _utcnow()).isoformat())


def get_status(db: Session, *, now: dt.datetime | None = None) -> dict:
    now = now or _utcnow()
    last_price = db.scalar(select(func.max(PriceSnapshot.captured_at)))
    last_sourcing = db.scalar(select(func.max(SourcingListing.detected_at)))
    last_snapshot = db.scalar(select(func.max(AccountSnapshot.snapshot_date)))
    last_backup = _parse(
        (db.scalar(select(Setting.setting_value).where(Setting.setting_key == LAST_BACKUP_KEY)))
    )
    heartbeats = {
        row.setting_key[len(HB_PREFIX):]: _age_min(_parse(row.setting_value), now)
        for row in db.scalars(
            select(Setting).where(Setting.setting_key.like(HB_PREFIX + "%"))
        ).all()
    }
    block_state = get_setting("scrape_block_state", default={})
    try:
        quota_used = get_setting("poketrace_requests_today")
    except KeyError:
        quota_used = None
    pending = len(db.scalars(select(Alert.id).where(Alert.status == "pending")).all())

    return {
        "db": "ok",
        "now": now.isoformat(),
        "freshness": {
            "price_age_min": _age_min(last_price, now),
            "sourcing_age_min": _age_min(last_sourcing, now),
            "last_snapshot_date": last_snapshot.isoformat() if last_snapshot else None,
            "backup_age_min": _age_min(last_backup, now),
        },
        "heartbeats_age_min": heartbeats,
        "scraper_blocked_platforms": list(block_state) if isinstance(block_state, dict) else [],
        "poketrace_requests_today": quota_used,
        "pending_alerts": pending,
    }


def run_dead_mans_switch(db: Session, *, now: dt.datetime | None = None) -> dict:
    """Émet une ``tech_error`` pour tout job critique silencieux trop longtemps."""
    now = now or _utcnow()
    max_age = int(float(get_setting("job_heartbeat_max_age_min", default=720)))
    stale = []
    for job in DEADMAN_JOBS:
        row = db.scalar(select(Setting).where(Setting.setting_key == HB_PREFIX + job))
        if row is None:
            continue  # jamais démarré → on n'alerte pas
        age = _age_min(_parse(row.setting_value), now)
        if age is not None and age > max_age:
            stale.append({"job": job, "age_min": age})

    for entry in stale:
        title = f"Dead-man's switch — job '{entry['job']}' silencieux"
        existing = db.scalar(
            select(Alert.id).where(Alert.alert_type == "tech_error",
                                   Alert.status == "pending", Alert.title == title)
        )
        if existing is None:
            db.add(Alert(alert_type="tech_error", severity="critical", status="pending",
                         title=title, payload={"job": entry["job"], "age_min": entry["age_min"],
                                               "max_age_min": max_age}))
    if stale:
        db.commit()
    return {"stale": stale, "max_age_min": max_age}
