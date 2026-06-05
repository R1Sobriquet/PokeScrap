"""Filtres anti-erreurs (réf. S4) — fonctions pures.

S'appliquent aux « value drivers » du lot (le produit qui porte la valeur).
"""

from __future__ import annotations

from app.domain.types import FilterResult


def anti_pump_block(
    avg_7d: float | None,
    avg_30d: float | None,
    *,
    pump_rise_pct: float,
    had_recent_correction: bool = False,
) -> bool:
    """Bloque si hausse 7j/30j ≥ seuil et pas de correction récente."""
    if not avg_7d or not avg_30d or avg_30d <= 0:
        return False
    rise = avg_7d / avg_30d - 1
    return rise >= pump_rise_pct / 100.0 and not had_recent_correction


def illiquidity_block(
    sale_count: int | None,
    approx_sale_count: bool,
    *,
    min_sale_count: int,
    illiquid_approx_multiplier: int,
) -> bool:
    """Bloque si volume de ventes insuffisant (exigence x si volume approximatif)."""
    sc = sale_count or 0
    required = min_sale_count * (illiquid_approx_multiplier if approx_sale_count else 1)
    return sc < required


def fomo_block(
    *,
    fomo_freeze: bool,
    fomo_scope: str = "global",
    in_scope: bool = True,
    trends_enabled: bool = False,
    trends_spike: bool = False,
) -> bool:
    """Bloque si gel FOMO (global ou ciblé sur le set) ou pic Trends."""
    if fomo_freeze and (fomo_scope == "global" or in_scope):
        return True
    if trends_enabled and trends_spike:
        return True
    return False


def passes_S4(
    *,
    avg_7d: float | None,
    avg_30d: float | None,
    sale_count: int | None,
    approx_sale_count: bool,
    pump_rise_pct: float,
    min_sale_count: int,
    illiquid_approx_multiplier: int,
    fomo_freeze: bool,
    fomo_scope: str = "global",
    in_scope: bool = True,
    trends_enabled: bool = False,
    trends_spike: bool = False,
    had_recent_correction: bool = False,
) -> FilterResult:
    """Agrège les trois filtres et renvoie ``filter_flags`` + verdict global."""
    flags = {
        "anti_pump": anti_pump_block(
            avg_7d, avg_30d,
            pump_rise_pct=pump_rise_pct,
            had_recent_correction=had_recent_correction,
        ),
        "illiquid": illiquidity_block(
            sale_count, approx_sale_count,
            min_sale_count=min_sale_count,
            illiquid_approx_multiplier=illiquid_approx_multiplier,
        ),
        "fomo": fomo_block(
            fomo_freeze=fomo_freeze,
            fomo_scope=fomo_scope,
            in_scope=in_scope,
            trends_enabled=trends_enabled,
            trends_spike=trends_spike,
        ),
    }
    return FilterResult(passes=not any(flags.values()), flags=flags)
