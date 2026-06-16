"""Notifier composite : diffuse une même alerte vers plusieurs canaux.

Permet d'ajouter Telegram en **fan-out** du Discord existant sans modifier le
dispatcher (qui ne connaît qu'un seul ``Notifier``). Chaque enfant décide seul
s'il relaie (ex. Telegram ignore les canaux arbitrage). Une panne d'un canal
n'empêche pas les autres.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from app.adapters.ports import Notifier

logger = logging.getLogger("adapters.composite_notifier")


class CompositeNotifier(Notifier):
    def __init__(self, children: Iterable[Notifier]):
        self._children = [c for c in children if c is not None]

    def send(self, channel_key: str, embed: Any, buttons: Any = (), *, ping: bool = False) -> Any:
        results = []
        for child in self._children:
            try:
                results.append(child.send(channel_key, embed, buttons, ping=ping))
            except Exception:  # noqa: BLE001 - isolation : un canal KO n'arrête pas les autres
                logger.exception("Échec d'un notifier enfant (%s).", type(child).__name__)
                results.append(None)
        return results
