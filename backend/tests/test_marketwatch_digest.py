"""Tests du digest « cartes à cibler » : dry-run stdout + render bot + routage."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app.models import Alert, DailySignal, TcgdexCard
from app.notifications.render import render_alert
from app.services.marketwatch_digest import run_digest

TODAY = dt.date(2026, 6, 1)


def _seed_signal(db, **kw):
    db.add(TcgdexCard(card_id="sv03.5-161", set_id="sv03.5", set_name="151",
                      number="161", rarity="Double Rare", pokemon="Charizard",
                      name_en="Charizard ex"))
    base = dict(card_id="sv03.5-161", language="EN", price_eur=Decimal("15.00"),
                near_low=Decimal("0.8000"), drawdown_sma=Decimal("0.1000"),
                bottoming=Decimal("0.5000"), cross_lang=Decimal("0"),
                liquidity=Decimal("0.5000"), momentum_7d=Decimal("0.2000"),
                score=Decimal("0.5000"), budget_band="10_20",
                buy_url="https://cardmarket.test/x", computed_at=TODAY)
    base.update(kw)
    db.add(DailySignal(**base))
    db.commit()


def test_dry_run_prints_text_without_writing_alert(db_session):
    _seed_signal(db_session)
    res = run_digest(db_session, dry_run=True, day=TODAY)
    assert "text" in res
    assert "Charizard ex" in res["text"]
    assert "10–20" in res["text"]
    # Dry-run : aucune alerte créée.
    assert db_session.scalar(select(Alert)) is None


def test_run_digest_creates_marketwatch_alert(db_session):
    _seed_signal(db_session)
    res = run_digest(db_session, dry_run=False, day=TODAY)
    assert "cible" in res["summary"]
    alert = db_session.scalar(select(Alert))
    assert alert is not None
    assert alert.alert_type == "marketwatch"
    assert alert.severity == "warning"  # → envoyé tel quel (pas fondu dans le digest info)


def test_alert_renders_grouped_embed_to_marketwatch_channel(db_session):
    _seed_signal(db_session)
    run_digest(db_session, dry_run=False, day=TODAY)
    alert = db_session.scalar(select(Alert))
    rendered = render_alert(alert)
    assert rendered.channel_key == "marketwatch"
    assert rendered.embed.title.startswith("🎯 Cartes à cibler")
    # Le champ de la tranche 10–20 € contient la carte.
    joined = " ".join(f.name + " " + f.value for f in rendered.embed.fields)
    assert "Charizard ex" in joined


def test_empty_day_reports_empty(db_session):
    res = run_digest(db_session, dry_run=True, day=TODAY)
    assert "vide" in res["summary"] or "impossible" in res["summary"]
