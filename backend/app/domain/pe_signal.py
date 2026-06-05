"""Signal d'accumulation Prismatic Evolutions (réf. S3.5) — fonction pure."""

from __future__ import annotations

from app.domain.types import PEAccumulationResult


def pe_accumulation_signal(
    *,
    singles_rising: bool,
    sealed_rising: bool | None = None,
    reprint_ended: bool = False,
    stock_declining: bool = False,
    min_triggers: int,
) -> PEAccumulationResult:
    """Compte les signaux concordants ; déclenche si ``>= min_triggers``.

    Signaux : hausse des singles (auto), hausse du scellé (auto si dispo), et les
    flags manuels ``pe_reprint_ended`` / ``pe_stock_declining``.
    """
    triggers: list[str] = []
    if singles_rising:
        triggers.append("singles_rising")
    if sealed_rising:
        triggers.append("sealed_rising")
    if reprint_ended:
        triggers.append("reprint_ended")
    if stock_declining:
        triggers.append("stock_declining")

    return PEAccumulationResult(
        fire=len(triggers) >= min_triggers,
        trigger_count=len(triggers),
        triggers=tuple(triggers),
    )
