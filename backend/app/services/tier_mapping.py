"""Mapping tier PokeTrace → colonnes ``price_snapshots``.

Tiers bruts → ``grade_company='RAW'``, ``condition_code`` correspondant.
Tiers gradés (``PSA_10``, ``BGS_9.5``, ``CGC_10``…) → ``grade_company`` = société,
``grade`` = note, ``condition_code=NULL``.
"""

from __future__ import annotations

from typing import NamedTuple

#: Tiers bruts PokeTrace → code condition du schéma.
RAW_CONDITIONS: dict[str, str] = {
    "NEAR_MINT": "NM",
    "LIGHTLY_PLAYED": "LP",
    "MODERATELY_PLAYED": "MP",
    "HEAVILY_PLAYED": "HP",
    "DAMAGED": "DMG",
}

#: Sociétés de gradation reconnues (``grade_company`` du schéma).
GRADED_COMPANIES: frozenset[str] = frozenset(
    {"PSA", "BGS", "CGC", "SGC", "ACE", "TAG"}
)


class TierMapping(NamedTuple):
    grade_company: str
    grade: str | None
    condition_code: str | None

    @property
    def is_raw(self) -> bool:
        return self.grade_company == "RAW"


def map_tier(tier: str) -> TierMapping | None:
    """Convertit un nom de tier PokeTrace. Renvoie ``None`` si non reconnu."""
    key = tier.strip().upper()
    if key in RAW_CONDITIONS:
        return TierMapping("RAW", None, RAW_CONDITIONS[key])
    if "_" in key:
        company, _, grade = key.partition("_")
        if company in GRADED_COMPANIES and grade:
            return TierMapping(company, grade, None)
    return None
