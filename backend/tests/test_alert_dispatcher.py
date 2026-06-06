"""Tests du dispatcher (routage balanced, quiet hours, dedup/cooldown, digest)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.models import Alert
from app.services.alert_dispatcher import dispatch_pending, flush_digest, in_quiet_hours
from tests.conftest import insert_setting
from tests.fakes import FakeNotifier

# 12:00 UTC = 14:00 Europe/Paris (CEST) → hors quiet hours.
NOON = dt.datetime(2026, 6, 5, 12, 0, 0)
# 00:00 UTC = 02:00 Paris → dans quiet hours 23:00-08:00.
NIGHT = dt.datetime(2026, 6, 5, 0, 0, 0)


def _settings(db):
    insert_setting(db, "notify_mode", "balanced", "string")
    insert_setting(db, "quiet_hours", "23:00-08:00", "string")
    insert_setting(db, "alert_cooldown_min", "60", "int")
    insert_setting(db, "digest_time", "09:00", "string")


def _alert(db, *, atype="buy", severity="warning", status="pending",
           product_id=None, listing_id=None, created_at=NOON, title="T", payload=None):
    a = Alert(alert_type=atype, severity=severity, status=status, product_id=product_id,
              sourcing_listing_id=listing_id, title=title, payload=payload or {}, created_at=created_at)
    db.add(a)
    db.commit()
    return a


def test_in_quiet_hours_wraps_midnight():
    assert in_quiet_hours(NIGHT, "23:00-08:00") is True
    assert in_quiet_hours(NOON, "23:00-08:00") is False


def test_balanced_routing_critical_warning_info(db_session):
    _settings(db_session)
    _alert(db_session, severity="critical", product_id=1)
    _alert(db_session, severity="warning", product_id=2)
    _alert(db_session, severity="info", atype="reinvest", product_id=3)

    notifier = FakeNotifier()
    stats = dispatch_pending(db_session, notifier, now=NOON)

    assert stats["sent"] == 2          # critical + warning poussés
    assert stats["pinged"] == 1        # seul le critical ping
    assert stats["digest_queued"] == 1  # info laissé en file
    pings = [m["ping"] for m in notifier.sent]
    assert pings.count(True) == 1
    # l'info n'a pas été envoyée et reste pending
    info = db_session.scalar(select(Alert).where(Alert.severity == "info"))
    assert info.status == "pending"


def test_quiet_hours_defers_non_critical(db_session):
    _settings(db_session)
    _alert(db_session, severity="warning", product_id=1)
    _alert(db_session, severity="critical", product_id=2)

    notifier = FakeNotifier()
    stats = dispatch_pending(db_session, notifier, now=NIGHT)

    assert stats["deferred"] == 1   # warning différé
    assert stats["sent"] == 1       # critical passe outre les quiet hours
    assert notifier.sent[0]["ping"] is True


def test_blocked_filters_never_pushed(db_session):
    _settings(db_session)
    _alert(db_session, atype="illiquid", severity="warning", product_id=1)
    _alert(db_session, atype="anti_pump", severity="warning", product_id=2)

    notifier = FakeNotifier()
    stats = dispatch_pending(db_session, notifier, now=NOON)

    assert stats["sent"] == 0
    assert stats["skipped"] == 2
    assert notifier.sent == []


def test_dedup_same_run(db_session):
    _settings(db_session)
    # Même (type, cible) deux fois → un seul envoi.
    _alert(db_session, severity="warning", product_id=1)
    _alert(db_session, severity="warning", product_id=1)

    notifier = FakeNotifier()
    stats = dispatch_pending(db_session, notifier, now=NOON)
    assert stats["sent"] == 1
    assert stats["skipped"] == 1


def test_cooldown_blocks_then_allows(db_session):
    _settings(db_session)
    # Un envoi déjà effectué il y a 10 min sur (buy, product 1).
    sent = _alert(db_session, severity="warning", product_id=1, status="sent")
    sent.sent_to_discord_at = NOON - dt.timedelta(minutes=10)
    db_session.commit()
    # Nouvelle alerte même cible.
    _alert(db_session, severity="warning", product_id=1)

    notifier = FakeNotifier()
    stats = dispatch_pending(db_session, notifier, now=NOON)  # cooldown 60 → bloqué
    assert stats["sent"] == 0
    assert stats["skipped"] == 1

    # 90 min plus tard, cooldown écoulé → envoyé.
    notifier2 = FakeNotifier()
    stats2 = dispatch_pending(db_session, notifier2, now=NOON + dt.timedelta(minutes=90))
    assert stats2["sent"] == 1


def test_flush_digest(db_session):
    _settings(db_session)
    _alert(db_session, severity="info", atype="reinvest", product_id=1, title="A")
    _alert(db_session, severity="info", atype="grading", product_id=2, title="B")

    notifier = FakeNotifier()
    res = flush_digest(db_session, notifier, now=NOON)

    assert res["digested"] == 2
    assert len(notifier.sent) == 1
    assert notifier.sent[0]["channel"] == "systeme"
    remaining = db_session.scalars(select(Alert).where(Alert.status == "pending")).all()
    assert remaining == []
