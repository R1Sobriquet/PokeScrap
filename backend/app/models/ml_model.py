"""Modèle ORM ``ml_models`` — artefacts de modèles entraînés (sérialisés).

Le payload est le bundle joblib (modèles sklearn + scaler + quantiles + noms de
features). Inférence rapide hors-ligne : on charge depuis la base et on cache par
``trained_at``. Une ligne par modèle nommé (ex. ``release_scorer``).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class MlModel(Base):
    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    payload: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    n_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trained_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
