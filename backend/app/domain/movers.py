"""Top movers (radar de momentum) — fonctions pures.

Hausse confirmée par le volume : à hausse égale, plus gros volume = plus haut.
En dessous d'un volume minimal → ``None`` (anti-bruit, on ignore). Ce radar
SIGNALE, il ne dit pas « achète » : aucun court-circuit des garde-fous d'achat.
"""

from __future__ import annotations


def momentum_rise(avg_7d: float | None, avg_30d: float | None) -> float | None:
    """Hausse relative (avg_7d − avg_30d)/avg_30d, ou ``None`` si non calculable."""
    if avg_7d is None or not avg_30d or avg_30d <= 0:
        return None
    return (avg_7d - avg_30d) / avg_30d


def mover_score(
    avg_7d: float | None,
    avg_30d: float | None,
    volume: int | None,
    *,
    min_volume: int,
    liquidity_midpoint: float = 5.0,
) -> float | None:
    """Score = hausse pondérée par la liquidité. ``None`` si volume insuffisant."""
    rise = momentum_rise(avg_7d, avg_30d)
    if rise is None:
        return None
    v = volume or 0
    if v < min_volume:
        return None  # volume trop faible → ignoré
    return rise * (v / (v + liquidity_midpoint))
