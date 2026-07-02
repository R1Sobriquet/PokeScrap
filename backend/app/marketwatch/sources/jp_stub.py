"""Source JP — stub best-effort (Cardmarket couvre mal le japonais).

TODO: brancher une vraie source JP (PPT si elle expose le marché JP, sinon un
fournisseur dédié). En attendant, ``fetch()`` renvoie ``[]`` — le pipeline n'est
jamais bloqué par l'absence de données JP, et le signal cross-langue s'en passe.
"""

from __future__ import annotations

import logging

from app.marketwatch.domain import CardSnapshot
from app.marketwatch.ports import CardPriceSource

logger = logging.getLogger("marketwatch.jp")


class JpStubSource(CardPriceSource):
    code = "ppt"  # placeholder ; à requalifier quand une vraie source JP existe

    def fetch(self) -> list[CardSnapshot]:
        logger.info("source JP non implémentée (stub) — 0 snapshot.")
        return []
