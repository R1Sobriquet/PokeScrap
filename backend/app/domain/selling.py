"""Moteur de vente (réf. S5) — fonctions pures, zéro I/O.

Hiérarchie de conflits **figée** : FORCÉ (terminal, prioritaire) > CAPITAL (x2,
avant le structuré) > STRUCTURÉ (25/50/25, sur le résidu). L'idempotence est
portée par les drapeaux ``stage_*`` : chaque étape ne se déclenche qu'une fois.

Le multiple ``m = valeur_marché_unitaire / avg_cost``. Les ``stage_*`` ne sont
**jamais** posés ici : c'est l'exécution (modal) qui les pose, après vente.
"""

from __future__ import annotations

import math

from app.domain.types import SellDecision, SellPosition

# Actions
NO_ACTION = "no_action"
SECURE_CAPITAL = "secure_capital"
STRUCTURED_25_50_25 = "structured_25_50_25"
FORCED_DERISK = "forced_derisk"

# alert_type associé à chaque action
ACTION_ALERT_TYPE = {
    SECURE_CAPITAL: "sell_x2",
    STRUCTURED_25_50_25: "sell_25_50_25",
    FORCED_DERISK: "sell_forced",
}


def _pct(quantity: int, pct: float) -> int:
    return int(round(quantity * pct / 100.0))


def _capital_qty(quantity: int, m: float) -> int:
    """Quantité à vendre pour récupérer le capital initial : ceil(qty / m)."""
    if m <= 0:
        return 0
    return min(quantity, math.ceil(quantity / m))


def speculation_signal(
    *,
    speculation_flag: bool,
    volume_spike_pct: float,
    speculation_volume_spike_pct: float,
    m: float,
    parabolic_multiple: float,
) -> bool:
    """Flag manuel OU (pic de volume ET multiple parabolique)."""
    if speculation_flag:
        return True
    return volume_spike_pct >= speculation_volume_spike_pct and m >= parabolic_multiple


def sell_engine(
    pos: SellPosition,
    m: float,
    spec_signal: bool,
    *,
    parabolic_multiple: float,
    double_multiple: float,
    explosion_multiple: float,
    forced_sell_pct: float,
    partial_sell_pct: float,
    speculative_reserve_pct: float,
) -> SellDecision:
    """Décide la prochaine étape de vente d'une position selon la hiérarchie S5."""
    # 1) FORCÉ — terminal, prioritaire (parabolique ou spéculation).
    if (m >= parabolic_multiple or spec_signal) and not pos.stage_forced:
        stages = ["forced"]
        qty_capital = 0
        if not pos.stage_capital_secured:
            qty_capital = _capital_qty(pos.quantity, m)
            stages.insert(0, "capital_secured")
        residual = pos.quantity - qty_capital
        forced_qty = _pct(residual, forced_sell_pct)
        # ne liquide jamais tout : on garde au moins une mèche d'une unité.
        if forced_qty >= residual:
            forced_qty = max(residual - 1, 0)
        return SellDecision(
            action=FORCED_DERISK,
            qty_to_sell=qty_capital + forced_qty,
            stages_to_set=tuple(stages),
            keeps_wick=True,
            severity="critical",
            reason="parabolic" if m >= parabolic_multiple else "speculation",
        )

    # 2) CAPITAL (x2) — impératif, AVANT le structuré.
    if m >= double_multiple and not pos.stage_capital_secured:
        return SellDecision(
            action=SECURE_CAPITAL,
            qty_to_sell=_capital_qty(pos.quantity, m),
            stages_to_set=("capital_secured",),
            severity="critical",
            reason="double",
        )

    # 3) STRUCTURÉ (25/50/25) — sur le RÉSIDU, après sécurisation.
    if m >= explosion_multiple and pos.stage_capital_secured and not pos.stage_structured:
        residual = pos.quantity
        sell_qty = _pct(residual, partial_sell_pct)
        reserve_qty = _pct(residual, speculative_reserve_pct)
        return SellDecision(
            action=STRUCTURED_25_50_25,
            qty_to_sell=sell_qty,
            speculative_reserve_qty=reserve_qty,
            stages_to_set=("structured",),
            severity="warning",
            reason="explosion",
        )

    return SellDecision(action=NO_ACTION)


def discipline_reminder(
    *,
    mv_unit: float,
    avg_cost: float,
    target_sell_price: float | None,
    default_profit_target: float,
    stage_active: bool,
) -> bool:
    """Rappel doux (``sell_reminder``) si l'objectif est atteint et qu'aucun stage
    dur S5 n'est actif sur la position."""
    if stage_active:
        return False
    target = target_sell_price if target_sell_price else avg_cost * default_profit_target
    return mv_unit >= target
