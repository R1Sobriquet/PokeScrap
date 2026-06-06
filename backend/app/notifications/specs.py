"""Specs de notification neutres (aucune dépendance discord.py).

Le dispatcher et les services backend produisent ces objets ; seul l'adapter
``discord_notifier`` les traduit en ``discord.Embed`` / ``discord.ui.View``. Cela
garde la logique de dispatch testable sans Discord.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Couleurs par sévérité (entiers RGB, comme discord.Color).
COLOR_INFO = 0x2ECC71
COLOR_WARNING = 0xE67E22
COLOR_CRITICAL = 0xE74C3C

SEVERITY_COLORS = {
    "info": COLOR_INFO,
    "warning": COLOR_WARNING,
    "critical": COLOR_CRITICAL,
}

# Styles de bouton (mappés vers discord.ButtonStyle par l'adapter).
STYLE_PRIMARY = "primary"
STYLE_SECONDARY = "secondary"
STYLE_DANGER = "danger"
STYLE_LINK = "link"


@dataclass(frozen=True)
class EmbedField:
    name: str
    value: str
    inline: bool = True


@dataclass(frozen=True)
class EmbedSpec:
    title: str
    description: str | None
    color: int
    fields: tuple[EmbedField, ...] = ()
    footer: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class ButtonSpec:
    label: str
    style: str = STYLE_SECONDARY
    custom_id: str | None = None  # None pour un bouton lien
    url: str | None = None


@dataclass(frozen=True)
class RenderedAlert:
    channel_key: str  # 'achats' | 'ventes' | 'portefeuille' | 'systeme'
    embed: EmbedSpec
    buttons: tuple[ButtonSpec, ...] = ()
