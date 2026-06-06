"""Rendu d'une alerte (ORM) → spec neutre d'embed + boutons.

Pas d'I/O : prend une alerte et produit un ``RenderedAlert``. Le routage par
salon et les boutons dépendent du ``alert_type``.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from app.notifications.specs import (
    SEVERITY_COLORS,
    STYLE_DANGER,
    STYLE_LINK,
    STYLE_PRIMARY,
    STYLE_SECONDARY,
    ButtonSpec,
    EmbedField,
    EmbedSpec,
    RenderedAlert,
)

PARIS = ZoneInfo("Europe/Paris")

#: alert_type → salon logique (id résolu via .env par l'adapter).
CHANNEL_ROUTING = {
    "buy": "achats",
    "palier_up": "portefeuille",
    "palier_down": "portefeuille",
    "grading": "portefeuille",
    "reinvest": "portefeuille",
    "tax_provision": "portefeuille",
    "tech_error": "systeme",
}


def channel_for(alert_type: str) -> str:
    if alert_type.startswith("sell_"):
        return "ventes"
    return CHANNEL_ROUTING.get(alert_type, "systeme")


def _footer(created_at: dt.datetime | None) -> str:
    when = created_at or dt.datetime.now(dt.timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when.astimezone(PARIS).strftime("%Y-%m-%d %H:%M %Z")


def _money(value) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "—"


def _buy_embed(alert, payload: dict) -> tuple[EmbedSpec, tuple[ButtonSpec, ...]]:
    trinity = "⭐ Trinité" if payload.get("is_trinity") else ""
    proxy = " (proxy)" if payload.get("value_proxy") else ""
    fields = [
        EmbedField("Coût d'acquisition", f"{_money(payload.get('acquisition_cost_total'))} €"),
        EmbedField("Revente nette est.", f"{_money(payload.get('estimated_resale_value'))} €{proxy}"),
        EmbedField("Ratio", f"{_money(payload.get('ratio_pct'))} %"),
        EmbedField("Score", _money(payload.get("score"))),
        EmbedField("Tier", str(payload.get("tier", "—"))),
    ]
    if trinity:
        fields.append(EmbedField("Statut", trinity, inline=False))
    url = payload.get("listing_url")
    embed = EmbedSpec(
        title=f"🛒 Achat potentiel — {alert.title}",
        description=None,
        color=SEVERITY_COLORS.get(alert.severity, SEVERITY_COLORS["warning"]),
        fields=tuple(fields),
        footer=_footer(alert.created_at),
        url=url,
    )
    buttons = [
        ButtonSpec("Voir", style=STYLE_LINK, url=url) if url else None,
        ButtonSpec("Acheté", style=STYLE_PRIMARY, custom_id=f"alert:{alert.id}:action:bought"),
        ButtonSpec("Ignorer", style=STYLE_SECONDARY, custom_id=f"alert:{alert.id}:action:ignore"),
    ]
    return embed, tuple(b for b in buttons if b is not None)


def _palier_embed(alert, payload: dict) -> tuple[EmbedSpec, tuple[ButtonSpec, ...]]:
    up = alert.alert_type == "palier_up"
    embed = EmbedSpec(
        title=f"{'⬆️' if up else '⬇️'} Palier — {alert.title}",
        description=payload.get("message"),
        color=SEVERITY_COLORS.get(alert.severity, SEVERITY_COLORS["info"]),
        fields=tuple(
            EmbedField(k, str(v)) for k, v in payload.items() if k != "message"
        ),
        footer=_footer(alert.created_at),
    )
    buttons: tuple[ButtonSpec, ...] = ()
    if up:  # palier_down est appliqué automatiquement (pas de bouton)
        buttons = (
            ButtonSpec("Confirmer", style=STYLE_PRIMARY, custom_id=f"alert:{alert.id}:action:confirm"),
            ButtonSpec("Plus tard", style=STYLE_SECONDARY, custom_id=f"alert:{alert.id}:action:later"),
        )
    return embed, buttons


def _generic_embed(alert, payload: dict) -> tuple[EmbedSpec, tuple[ButtonSpec, ...]]:
    embed = EmbedSpec(
        title=alert.title,
        description=payload.get("message") or payload.get("detail"),
        color=SEVERITY_COLORS.get(alert.severity, SEVERITY_COLORS["info"]),
        fields=tuple(
            EmbedField(k, str(v)) for k, v in payload.items()
            if k not in ("message", "detail")
        ),
        footer=_footer(alert.created_at),
    )
    return embed, ()


def render_alert(alert) -> RenderedAlert:
    """Construit le ``RenderedAlert`` pour une alerte ORM."""
    payload = alert.payload or {}
    if alert.alert_type == "buy":
        embed, buttons = _buy_embed(alert, payload)
    elif alert.alert_type in ("palier_up", "palier_down"):
        embed, buttons = _palier_embed(alert, payload)
    else:  # tech_error et autres : embed sans bouton
        embed, buttons = _generic_embed(alert, payload)
    return RenderedAlert(channel_key=channel_for(alert.alert_type), embed=embed, buttons=buttons)
