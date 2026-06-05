"""Service de lecture des prix — ``get_latest_price``.

C'est l'API que le moteur de règles consommera au Jalon 3 : il lit la base, ne
fait aucun I/O externe et ne décide rien.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.models import PriceSnapshot


def get_latest_price(
    db: Session,
    product_id: int,
    *,
    grade_company: str = "RAW",
    grade: str | None = None,
    condition: str | None = "NM",
    market: str | None = None,
) -> PriceSnapshot | None:
    """Renvoie le ``price_snapshots`` le plus récent du tier demandé, ou ``None``.

    Par défaut : tier brut Near Mint, sur le marché du réglage ``valuation_market``.
    Pour un tier gradé, passer ``grade_company``/``grade`` ; ``condition`` est
    alors ignorée (les lignes gradées ont ``condition_code = NULL``).
    """
    market = market or str(get_setting("valuation_market", default="US"))

    stmt = select(PriceSnapshot).where(
        PriceSnapshot.product_id == product_id,
        PriceSnapshot.source == "poketrace",
        PriceSnapshot.market == market,
        PriceSnapshot.grade_company == grade_company,
    )

    if grade is None:
        stmt = stmt.where(PriceSnapshot.grade.is_(None))
    else:
        stmt = stmt.where(PriceSnapshot.grade == grade)

    if grade_company == "RAW":
        stmt = stmt.where(PriceSnapshot.condition_code == condition)
    else:
        stmt = stmt.where(PriceSnapshot.condition_code.is_(None))

    stmt = stmt.order_by(PriceSnapshot.captured_at.desc()).limit(1)
    return db.scalar(stmt)
