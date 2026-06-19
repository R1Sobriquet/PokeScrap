"""Tests notifications PokéStock FR : render embed restock, Telegram, composite."""

from __future__ import annotations

import datetime as dt
import types

from app.adapters.composite_notifier import CompositeNotifier
from app.adapters.telegram_notifier import TelegramNotifier, render_html
from app.notifications.render import channel_for, render_alert
from app.notifications.specs import EmbedField, EmbedSpec
from tests.fakes import FakeNotifier


def _alert(alert_type="restock"):
    return types.SimpleNamespace(
        id=1, alert_type=alert_type, severity="warning",
        title="ETB Pokémon", created_at=dt.datetime(2026, 6, 16, 10, 0),
        payload={"subtype": "RESTOCK", "retailer": "Cultura", "stock_state": "in_stock",
                 "price": 59.99, "currency": "EUR", "url": "https://c/p/etb.html",
                 "message": "De retour en stock chez Cultura."},
    )


def test_retail_alerts_route_to_restock_channel():
    assert channel_for("restock") == "restock"
    assert channel_for("new_sku") == "restock"


def test_render_restock_embed_has_link_and_state():
    rendered = render_alert(_alert("restock"))
    assert rendered.channel_key == "restock"
    assert "Restock" in rendered.embed.title
    labels = {f.name: f.value for f in rendered.embed.fields}
    assert labels["Enseigne"] == "Cultura"
    assert "stock" in labels["État"].lower()
    assert rendered.buttons and rendered.buttons[0].url == "https://c/p/etb.html"


def test_telegram_html_render():
    embed = EmbedSpec(title="🔔 Restock — ETB", description="dispo", color=0,
                      fields=(EmbedField("Prix", "59.99 EUR"),), footer="2026",
                      url="https://c/p/etb.html")
    html = render_html(embed)
    assert "<b>" in html and "Prix : 59.99 EUR" in html and 'href="https://c/p/etb.html"' in html


def test_telegram_only_restock_channel_and_enabled():
    sent = []
    tg = TelegramNotifier("tok", "chat", is_enabled=lambda: True,
                          poster=lambda token, payload: sent.append((token, payload)))
    embed = EmbedSpec(title="t", description=None, color=0, fields=(), footer="")
    # Canaux arbitrage → ignorés
    assert tg.send("achats", embed) is None and not sent
    # Canal restock → envoyé
    assert tg.send("restock", embed) is True
    assert sent and sent[0][1]["parse_mode"] == "HTML"


def test_telegram_disabled_is_noop():
    sent = []
    tg = TelegramNotifier("tok", "chat", is_enabled=lambda: False,
                          poster=lambda t, p: sent.append(p))
    assert tg.send("restock", EmbedSpec(title="t", description=None, color=0, fields=(), footer="")) is None
    assert not sent


def test_telegram_not_configured_is_noop():
    sent = []
    tg = TelegramNotifier("", "", is_enabled=lambda: True, poster=lambda t, p: sent.append(p))
    assert tg.send("restock", EmbedSpec(title="t", description=None, color=0, fields=(), footer="")) is None
    assert not sent


def test_composite_fans_out_to_all_children():
    a, b = FakeNotifier(), FakeNotifier()
    comp = CompositeNotifier([a, b])
    comp.send("restock", EmbedSpec(title="t", description=None, color=0, fields=(), footer=""))
    assert len(a.sent) == 1 and len(b.sent) == 1


def test_composite_isolates_child_failure():
    class Boom(FakeNotifier):
        def send(self, *a, **k):
            raise RuntimeError("down")

    ok = FakeNotifier()
    comp = CompositeNotifier([Boom(), ok])
    comp.send("restock", EmbedSpec(title="t", description=None, color=0, fields=(), footer=""))
    assert len(ok.sent) == 1  # le second canal a reçu malgré l'échec du premier
