"""Modèle ORM ``psa_certs``."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, BigIntPK


class PsaCert(Base):
    __tablename__ = "psa_certs"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    cert_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    grade_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_valid: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    pop_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
