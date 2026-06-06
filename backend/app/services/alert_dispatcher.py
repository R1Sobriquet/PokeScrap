"""Dispatcher d'alertes (service backend, exécuté en boucle dans le process bot).

Parcourt les alertes ``pending`` et les pousse via le ``Notifier`` selon
``notify_mode`` (balanced), en respectant ``quiet_hours``, le dedup et le
``alert_cooldown_min``. Les filtres dashboard-only ne sont jamais poussés. Les
``info`` sont mises en file et envoyées en un digest à ``digest_time``.

Sans dépendance discord.py : prend un ``Notifier`` (port) en argument, donc
testable avec un faux notifier.
"""

from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.ports import Notifier
from app.config import get_setting
from app.notifications.render import PARIS, render_alert
from app.notifications.specs import COLOR_INFO, EmbedField, EmbedSpec

logger = logging.getLogger("services.alert_dispatcher")

#: Filtres anti-erreurs : visibles au dashboard, jamais poussés en notification.
BLOCKED_FILTERS = {"anti_pump", "illiquid", "anti_fomo"}

_SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _to_paris(now: dt.datetime) -> dt.datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    return now.astimezone(PARIS)


def _parse_hhmm(text: str) -> dt.time:
    h, m = text.strip().split(":")
    return dt.time(int(h), int(m))


def in_quiet_hours(now: dt.datetime, quiet_hours: str) -> bool:
    """Vrai si l'heure locale (Paris) est dans la fenêtre calme (gère le wrap)."""
    try:
        start_s, end_s = quiet_hours.split("-")
        start, end = _parse_hhmm(start_s), _parse_hhmm(end_s)
    except (ValueError, AttributeError):
        return False
    local = _to_paris(now).time()
    if start <= end:
        return start <= local < end
    return local >= start or local < end  # fenêtre à cheval sur minuit


def is_digest_time(now: dt.datetime, digest_time: str, poll_sec: int) -> bool:
    """Vrai si ``now`` tombe dans le créneau ``[digest_time, digest_time+poll)``."""
    try:
        target = _parse_hhmm(digest_time)
    except (ValueError, AttributeError):
        return False
    local = _to_paris(now)
    target_dt = local.replace(hour=target.hour, minute=target.minute, second=0, microsecond=0)
    delta = (local - target_dt).total_seconds()
    return 0 <= delta < max(poll_sec, 1)


def _target_key(a) -> tuple:
    return (a.alert_type, a.product_id, a.sourcing_listing_id, a.position_id)


def _recent_send_exists(db: Session, alert, cooldown_min: int, now: dt.datetime) -> bool:
    from app.models import Alert  # local : évite un import circulaire au chargement

    cutoff = now - dt.timedelta(minutes=cooldown_min)

    def eq(col, val):
        return col.is_(None) if val is None else col == val

    stmt = select(Alert.id).where(
        Alert.id != alert.id,
        Alert.alert_type == alert.alert_type,
        eq(Alert.product_id, alert.product_id),
        eq(Alert.sourcing_listing_id, alert.sourcing_listing_id),
        eq(Alert.position_id, alert.position_id),
        Alert.sent_to_discord_at.is_not(None),
        Alert.sent_to_discord_at >= cutoff,
    )
    return db.scalar(stmt) is not None


def dispatch_pending(db: Session, notifier: Notifier, *, now: dt.datetime | None = None) -> dict:
    """Pousse les alertes pending (critical/warning) ; met les info en file digest."""
    from app.models import Alert

    now = now or _utcnow()
    quiet = str(get_setting("quiet_hours", default="23:00-08:00"))
    cooldown = int(get_setting("alert_cooldown_min", default=60))

    stats = {"sent": 0, "pinged": 0, "deferred": 0, "skipped": 0, "digest_queued": 0}

    pending = list(db.scalars(select(Alert).where(Alert.status == "pending")).all())
    pending.sort(key=lambda a: (_SEVERITY_RANK.get(a.severity, 3), a.created_at or now))

    sent_keys: set[tuple] = set()
    for alert in pending:
        if alert.alert_type in BLOCKED_FILTERS:
            stats["skipped"] += 1
            continue
        if alert.severity == "info":
            stats["digest_queued"] += 1  # traité par flush_digest
            continue
        if alert.severity != "critical" and in_quiet_hours(now, quiet):
            stats["deferred"] += 1
            continue

        key = _target_key(alert)
        if key in sent_keys or _recent_send_exists(db, alert, cooldown, now):
            stats["skipped"] += 1
            continue

        rendered = render_alert(alert)
        ping = alert.severity == "critical"
        notifier.send(rendered.channel_key, rendered.embed, rendered.buttons, ping=ping)
        alert.sent_to_discord_at = now
        alert.status = "sent"
        sent_keys.add(key)
        stats["sent"] += 1
        if ping:
            stats["pinged"] += 1

    db.commit()
    return stats


def flush_digest(db: Session, notifier: Notifier, *, now: dt.datetime | None = None) -> dict:
    """Envoie un embed récapitulatif des alertes ``info`` pending puis les marque sent."""
    from app.models import Alert

    now = now or _utcnow()
    infos = [
        a
        for a in db.scalars(
            select(Alert).where(Alert.status == "pending", Alert.severity == "info")
        ).all()
        if a.alert_type not in BLOCKED_FILTERS
    ]
    if not infos:
        return {"digested": 0}

    fields = tuple(
        EmbedField(a.title[:200], (a.payload or {}).get("subtype") or a.alert_type, inline=False)
        for a in infos[:25]
    )
    embed = EmbedSpec(
        title=f"🗞️ Digest — {len(infos)} info(s)",
        description=None,
        color=COLOR_INFO,
        fields=fields,
        footer=_to_paris(now).strftime("%Y-%m-%d %H:%M %Z"),
    )
    notifier.send("systeme", embed, ())
    for a in infos:
        a.status = "sent"
        a.sent_to_discord_at = now
    db.commit()
    logger.info("Digest envoyé : %s info(s).", len(infos))
    return {"digested": len(infos)}
