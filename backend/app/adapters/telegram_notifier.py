"""Adapter Telegram du port ``Notifier`` (Bot API ``sendMessage``, parse_mode=HTML).

Fan-out indépendant du canal Discord : n'agit que sur le canal logique
``"restock"`` (les alertes arbitrage existantes ne partent jamais sur Telegram).
Activable via le setting ``telegram_enabled`` ; secrets (``TELEGRAM_BOT_TOKEN`` /
``TELEGRAM_CHAT_ID``) dans ``.env``, jamais en base. No-op propre si non configuré.
"""

from __future__ import annotations

import html
import logging
from collections.abc import Callable
from typing import Any

import httpx

from app.adapters.ports import Notifier
from app.config import get_setting
from app.notifications.specs import EmbedSpec

logger = logging.getLogger("adapters.telegram_notifier")

#: Canaux logiques relayés vers Telegram (les autres restent Discord-only).
TELEGRAM_CHANNELS = {"restock", "health"}

#: ``poster(token, payload) -> None`` — injectable en test.
Poster = Callable[[str, dict], None]


def _httpx_post(token: str, payload: dict) -> None:
    httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=payload,
        timeout=15.0,
    ).raise_for_status()


def render_html(embed: EmbedSpec) -> str:
    """Traduit une spec neutre en message HTML Telegram (titre, champs, lien)."""
    lines: list[str] = []
    if embed.title:
        lines.append(f"<b>{html.escape(embed.title)}</b>")
    if embed.description:
        lines.append(html.escape(embed.description))
    for f in embed.fields:
        lines.append(f"{html.escape(str(f.name))} : {html.escape(str(f.value))}")
    if embed.url:
        lines.append(f'<a href="{html.escape(embed.url, quote=True)}">Voir le produit</a>')
    if embed.footer:
        lines.append(f"<i>{html.escape(embed.footer)}</i>")
    return "\n".join(lines)


class TelegramNotifier(Notifier):
    """Notifier Telegram (no-op si désactivé / non configuré)."""

    def __init__(self, token: str | None, chat_id: str | None, *,
                 is_enabled: Callable[[], bool] | None = None, poster: Poster | None = None):
        self._token = token or ""
        self._chat_id = chat_id or ""
        self._is_enabled = is_enabled or (lambda: bool(get_setting("telegram_enabled", default=False)))
        self._post = poster or _httpx_post

    @property
    def configured(self) -> bool:
        return bool(self._token and self._chat_id)

    def send(self, channel_key: str, embed: Any, buttons: Any = (), *, ping: bool = False) -> Any:
        if channel_key not in TELEGRAM_CHANNELS:
            return None  # canaux arbitrage : Discord uniquement
        if not self._is_enabled():
            return None
        if not self.configured:
            logger.warning("Telegram activé mais TOKEN/CHAT_ID absents — message ignoré.")
            return None
        payload = {
            "chat_id": self._chat_id,
            "text": render_html(embed),
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        try:
            self._post(self._token, payload)
        except Exception:  # noqa: BLE001 - une panne Telegram ne casse pas le dispatch
            logger.exception("Échec d'envoi Telegram.")
            return None
        return True
