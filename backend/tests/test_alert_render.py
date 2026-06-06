"""Tests du rendu d'alerte (specs neutres, sans Discord)."""

from __future__ import annotations

import datetime as dt

from app.models import Alert
from app.notifications.render import channel_for, render_alert
from app.notifications.specs import COLOR_CRITICAL, COLOR_WARNING


def _alert(**kw):
    a = Alert(**kw)
    a.id = 7  # alerte transiente : on fixe l'id pour les custom_id
    return a


def test_channel_routing():
    assert channel_for("buy") == "achats"
    assert channel_for("sell_x2") == "ventes"
    assert channel_for("palier_up") == "portefeuille"
    assert channel_for("tax_provision") == "portefeuille"
    assert channel_for("tech_error") == "systeme"
    assert channel_for("unknown") == "systeme"


def test_render_buy_has_buttons_and_link():
    a = _alert(
        alert_type="buy", severity="warning", title="Charizard ex",
        created_at=dt.datetime(2026, 6, 5, 10, 0),
        payload={
            "acquisition_cost_total": 33.0, "estimated_resale_value": 74.29,
            "ratio_pct": 44.4, "score": 0.5, "tier": "S++", "is_trinity": True,
            "listing_url": "https://example.test/a", "value_proxy": True,
        },
    )
    rendered = render_alert(a)
    assert rendered.channel_key == "achats"
    assert rendered.embed.color == COLOR_WARNING
    labels = [b.label for b in rendered.buttons]
    assert labels == ["Voir", "Acheté", "Ignorer"]
    bought = next(b for b in rendered.buttons if b.label == "Acheté")
    assert bought.custom_id == "alert:7:action:bought"
    voir = next(b for b in rendered.buttons if b.label == "Voir")
    assert voir.url == "https://example.test/a"


def test_render_tech_error_no_buttons():
    a = _alert(alert_type="tech_error", severity="critical", title="Quota épuisé",
               created_at=None, payload={"message": "boom"})
    rendered = render_alert(a)
    assert rendered.channel_key == "systeme"
    assert rendered.embed.color == COLOR_CRITICAL
    assert rendered.buttons == ()


def test_render_palier_up_has_confirm_later():
    a = _alert(alert_type="palier_up", severity="info", title="Palier 2 → 3",
               created_at=None, payload={"message": "Promotion soutenue"})
    rendered = render_alert(a)
    assert rendered.channel_key == "portefeuille"
    assert [b.label for b in rendered.buttons] == ["Confirmer", "Plus tard"]
    assert rendered.buttons[0].custom_id == "alert:7:action:confirm"
