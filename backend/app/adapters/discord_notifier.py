"""Adapter Discord (Notifier) — STUB Jalon 1."""

from __future__ import annotations

from typing import Any

from app.adapters.ports import Notifier


class DiscordNotifier(Notifier):
    def notify(self, channel: str, message: str, **kwargs: Any) -> Any:
        raise NotImplementedError("jalon 2")
