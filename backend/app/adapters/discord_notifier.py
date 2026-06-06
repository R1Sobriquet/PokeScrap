"""Adapter Discord du port ``Notifier``.

Traduit les specs neutres (``EmbedSpec``/``ButtonSpec``) en ``discord.Embed`` /
``discord.ui.View`` et poste dans le bon salon. Importe discord.py : n'est chargé
qu'à l'exécution dans le process bot (jamais dans les tests backend).
"""

from __future__ import annotations

import asyncio
import logging

import discord

from app.adapters.ports import Notifier
from app.notifications.specs import (
    STYLE_DANGER,
    STYLE_LINK,
    STYLE_PRIMARY,
    STYLE_SECONDARY,
    ButtonSpec,
    EmbedSpec,
)

logger = logging.getLogger("adapters.discord_notifier")

_STYLE_MAP = {
    STYLE_PRIMARY: discord.ButtonStyle.primary,
    STYLE_SECONDARY: discord.ButtonStyle.secondary,
    STYLE_DANGER: discord.ButtonStyle.danger,
    STYLE_LINK: discord.ButtonStyle.link,
}


def build_embed(spec: EmbedSpec) -> discord.Embed:
    embed = discord.Embed(title=spec.title, description=spec.description, color=spec.color)
    if spec.url:
        embed.url = spec.url
    for f in spec.fields:
        embed.add_field(name=f.name, value=f.value, inline=f.inline)
    if spec.footer:
        embed.set_footer(text=spec.footer)
    return embed


def build_view(buttons: tuple[ButtonSpec, ...]) -> discord.ui.View | None:
    if not buttons:
        return None
    view = discord.ui.View(timeout=None)  # persistant : les clics arrivent via on_interaction
    for b in buttons:
        style = _STYLE_MAP.get(b.style, discord.ButtonStyle.secondary)
        if b.style == STYLE_LINK:
            view.add_item(discord.ui.Button(label=b.label, style=style, url=b.url))
        else:
            view.add_item(discord.ui.Button(label=b.label, style=style, custom_id=b.custom_id))
    return view


class DiscordNotifier(Notifier):
    """Notifier concret adossé à un ``discord.Client`` connecté."""

    def __init__(self, client: discord.Client, channel_ids: dict[str, int], ping_user_id: str | None = None):
        self._client = client
        self._channels = channel_ids  # 'achats'/'ventes'/'portefeuille'/'systeme' -> id
        self._ping_user_id = ping_user_id

    def _resolve(self, channel_key: str):
        channel_id = self._channels.get(channel_key) or self._channels.get("systeme")
        if not channel_id:
            return None
        return self._client.get_channel(int(channel_id))

    async def _send_async(self, channel_key: str, embed: EmbedSpec, buttons, ping: bool):
        channel = self._resolve(channel_key)
        if channel is None:
            logger.warning("Salon introuvable pour %s — message non envoyé.", channel_key)
            return None
        content = f"<@{self._ping_user_id}>" if ping and self._ping_user_id else None
        view = build_view(tuple(buttons))
        kwargs = {"embed": build_embed(embed)}
        if content:
            kwargs["content"] = content
        if view is not None:
            kwargs["view"] = view
        return await channel.send(**kwargs)

    def send(self, channel_key: str, embed: EmbedSpec, buttons=(), *, ping: bool = False):
        """Sync (port) → planifie l'envoi sur la loop du bot et attend le résultat.

        Le dispatcher tourne dans un thread (``asyncio.to_thread``) ; on rejoint la
        loop du client via ``run_coroutine_threadsafe``.
        """
        future = asyncio.run_coroutine_threadsafe(
            self._send_async(channel_key, embed, tuple(buttons), ping), self._client.loop
        )
        return future.result(timeout=30)
