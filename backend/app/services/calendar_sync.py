"""Job ``calendar-sync`` — auto-remplit ``releases`` depuis les sources marché.

Upsert idempotent des dates de sortie de sets (TCGdex/PPT). N'écrase JAMAIS une
entrée curée à la main : ne gère que les lignes ``source_note`` préfixées
``auto:``. Cadence basse (les sets bougent peu).
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.marketdata.sources import build_sources
from app.models import Release

logger = logging.getLogger("services.calendar_sync")

_AUTO_PREFIX = "auto:"


def run_calendar_sync(db: Session, *, sources: dict | None = None) -> dict:
    if not bool(get_setting("marketdata_enabled", default=False)):
        return {"summary": "moat désactivé (marketdata_enabled=false)"}

    sources = sources if sources is not None else build_sources()
    release_sources = {c: s for c, s in sources.items() if "releases" in s.capabilities}
    stats = {"received": 0, "inserted": 0, "updated": 0}

    for code, source in release_sources.items():
        for rel in source.list_releases():
            if not rel.set_name or rel.release_date is None:
                continue
            stats["received"] += 1
            note = f"{_AUTO_PREFIX}{code}"
            existing = db.scalar(
                select(Release).where(Release.set_name == rel.set_name,
                                      Release.product_name == rel.set_name,
                                      Release.source_note.like(f"{_AUTO_PREFIX}%"))
            )
            if existing is None:
                db.add(Release(set_name=rel.set_name, product_name=rel.set_name,
                               product_type=rel.product_type, release_date=rel.release_date,
                               preorder_date=rel.preorder_date, source_note=note))
                stats["inserted"] += 1
            else:
                existing.release_date = rel.release_date
                if rel.preorder_date is not None:
                    existing.preorder_date = rel.preorder_date
                existing.source_note = note
                stats["updated"] += 1
    db.commit()
    stats["summary"] = (f"{stats['received']} reçus / {stats['inserted']} ajoutés "
                        f"/ {stats['updated']} maj")
    return stats
