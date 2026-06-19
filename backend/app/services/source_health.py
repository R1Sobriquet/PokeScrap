"""Moniteur dead-man's-switch des sources marché + télémétrie de run.

Chaque run de source écrit ses compteurs dans une ligne ``settings`` JSON
(``marketdata_run_state``). ``check_sources`` détecte fraîcheur / erreurs / volume
nul et **alerte sur le canal santé** (Discord + Telegram) via le pipeline
``alerts`` existant — avec dédup par source (cooldown). C'est le seul moment où
l'humain est sollicité.
"""

from __future__ import annotations

import datetime as dt
import json
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_setting, invalidate_setting
from app.models import Alert, DataQuarantine, MatchReview, Setting

logger = logging.getLogger("services.source_health")

_STATE_KEY = "marketdata_run_state"
KNOWN_SOURCES = ("ppt", "tcgdex", "ebay")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _load(db: Session) -> dict:
    row = db.scalar(select(Setting).where(Setting.setting_key == _STATE_KEY))
    if row is None or not row.setting_value:
        return {}
    try:
        return json.loads(row.setting_value)
    except json.JSONDecodeError:
        return {}


def _save(db: Session, state: dict) -> None:
    row = db.scalar(select(Setting).where(Setting.setting_key == _STATE_KEY))
    value = json.dumps(state)
    if row is None:
        db.add(Setting(setting_key=_STATE_KEY, setting_value=value, value_type="json",
                       description="Télémétrie de run des sources marché (auto)"))
    else:
        row.setting_value = value
    db.commit()
    invalidate_setting(_STATE_KEY)


def record_source_run(db: Session, source: str, stats: dict, *, now: dt.datetime | None = None) -> None:
    """Persiste les compteurs d'un run de source (pour le moniteur)."""
    now = now or _utcnow()
    state = _load(db)
    entry = state.get(source, {})
    entry.update({
        "last_run_at": now.isoformat(),
        "requests": int(stats.get("requests", 0)),
        "stored": int(stats.get("stored", 0)),
        "quarantined": int(stats.get("quarantined", 0)),
        "errors": int(stats.get("errors", 0)),
        "blocked": int(stats.get("blocked", 0)),
    })
    if stats.get("stored", 0) > 0 and stats.get("errors", 0) == 0:
        entry["last_ok_at"] = now.isoformat()
    state[source] = entry
    _save(db, state)


def _enabled(source: str) -> bool:
    return bool(get_setting(f"marketdata_{source}_enabled", default=(source == "tcgdex")))


def _symptom(entry: dict, now: dt.datetime, max_age_h: int, min_volume: int) -> str | None:
    last_run = entry.get("last_run_at")
    if not last_run:
        return None  # jamais exécutée → pas de bruit
    try:
        age_h = (now - dt.datetime.fromisoformat(last_run)).total_seconds() / 3600
    except ValueError:
        return None
    if age_h > max_age_h:
        return f"source muette (dernier run il y a {age_h:.0f}h)"
    if entry.get("blocked", 0) > 0 and entry.get("stored", 0) == 0:
        return "bloquée (403/429, circuit ouvert) — 0 stockée"
    if entry.get("errors", 0) > 0 and entry.get("stored", 0) == 0:
        return f"erreurs ({entry['errors']}) — 0 stockée"
    if entry.get("requests", 0) > 0 and entry.get("stored", 0) < min_volume \
            and entry.get("quarantined", 0) == 0:
        return "volume nul (0 résultat exploitable)"
    return None


def emit_daily_digest(db: Session, *, now: dt.datetime | None = None) -> bool:
    """1×/jour (si ``alert_digest_enabled``) : 1 alerte INFO résumant les events
    non urgents (quarantaine 24h + file de review) — batchée par ``flush_digest``."""
    if not bool(get_setting("alert_digest_enabled", default=False)):
        return False
    now = now or _utcnow()
    state = _load(db)
    if state.get("last_digest_date") == now.date().isoformat():
        return False  # déjà émis aujourd'hui

    since = now - dt.timedelta(hours=24)
    quarantined = db.scalar(select(func.count()).select_from(DataQuarantine)
                            .where(DataQuarantine.created_at >= since)) or 0
    reviews = db.scalar(select(func.count()).select_from(MatchReview)
                        .where(MatchReview.status == "pending")) or 0
    db.add(Alert(
        alert_type="health", severity="info", status="pending",
        title="Digest quotidien — moat de données",
        payload={"subtype": "daily_digest", "quarantined_24h": int(quarantined),
                 "match_review_pending": int(reviews),
                 "message": f"{quarantined} en quarantaine (24h) · {reviews} à matcher."},
    ))
    state["last_digest_date"] = now.date().isoformat()
    _save(db, state)
    return True


def check_sources(db: Session, *, now: dt.datetime | None = None,
                  cooldown_min: int | None = None) -> dict:
    """Évalue chaque source activée ; alerte santé (dédup) sur symptôme."""
    now = now or _utcnow()
    max_age_h = int(get_setting("source_health_fresh_max_age_h", default=30))
    min_volume = int(get_setting("source_health_min_volume", default=1))
    cooldown = cooldown_min if cooldown_min is not None else int(get_setting("alert_cooldown_min", default=60))

    state = _load(db)
    stats = {"checked": 0, "unhealthy": 0, "alerts": 0}
    changed = False

    for source in KNOWN_SOURCES:
        if not _enabled(source):
            continue
        stats["checked"] += 1
        entry = state.get(source, {})
        symptom = _symptom(entry, now, max_age_h, min_volume)
        if not symptom:
            continue
        stats["unhealthy"] += 1

        last_alert = entry.get("last_health_alert_at")
        recent = False
        if last_alert:
            try:
                recent = (now - dt.datetime.fromisoformat(last_alert)).total_seconds() / 60 < cooldown
            except ValueError:
                recent = False
        if recent:
            continue

        db.add(Alert(
            alert_type="health", severity="warning", status="pending",
            title=f"Source marché « {source} » en panne",
            payload={"subtype": "source_health", "source": source, "symptom": symptom,
                     "last_ok_at": entry.get("last_ok_at"),
                     "message": f"Source {source} : {symptom}."},
        ))
        entry["last_health_alert_at"] = now.isoformat()
        state[source] = entry
        changed = True
        stats["alerts"] += 1

    if changed:
        _save(db, state)
    else:
        db.commit()  # persiste les alertes créées hors _save
    if emit_daily_digest(db, now=now):
        stats["digest"] = True
    stats["summary"] = (f"{stats['checked']} sources / {stats['unhealthy']} en panne "
                        f"/ {stats['alerts']} alertes")
    return stats
