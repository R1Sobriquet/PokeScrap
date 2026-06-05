"""Paliers & garde-fou cash (réf. S2) — fonctions pures."""

from __future__ import annotations

from app.domain.types import Decision, PortfolioState, TierBand, TierTransition

PRE_TIER = "PRE_TIER"
OBJECTIVE_REACHED = "OBJECTIVE_REACHED"


def _lowest_min(tiers: list[TierBand]) -> float:
    return min(b.capital_min for b in tiers)


def _highest_max(tiers: list[TierBand]) -> float:
    maxes = [b.capital_max for b in tiers if b.capital_max is not None]
    return max(maxes) if maxes else float("inf")


def resolve_current_tier(capital: float, tiers: list[TierBand]) -> TierBand | str:
    """Résout le palier pour un capital. Bornes ``[min, max)``.

    < plus petit ``capital_min`` → ``PRE_TIER`` ; ≥ plus grand ``capital_max`` →
    ``OBJECTIVE_REACHED`` ; sinon le palier dont la bande contient le capital.
    """
    if capital < _lowest_min(tiers):
        return PRE_TIER
    if capital >= _highest_max(tiers):
        return OBJECTIVE_REACHED
    for band in sorted(tiers, key=lambda b: b.capital_min):
        upper = band.capital_max if band.capital_max is not None else float("inf")
        if band.capital_min <= capital < upper:
            return band
    return OBJECTIVE_REACHED


def cash_min_pct(
    capital: float,
    tier: TierBand | None,
    *,
    cash_min_below_150_pct: float,
    pre_tier_threshold: float = 150.0,
) -> float:
    """% de cash minimum : garde-fou renforcé sous le seuil pré-palier."""
    if capital < pre_tier_threshold or tier is None:
        return cash_min_below_150_pct
    return tier.cash_min_pct


def can_buy(cost: float, state: PortfolioState, *, cash_min_pct: float) -> Decision:
    """Autorise l'achat si le cash projeté reste au-dessus du plancher.

    ``floor = cash_min_pct% × operational_capital`` ; BLOCK (motif ``cash_min``) si
    ``cash_active − cost < floor``.
    """
    floor = cash_min_pct / 100.0 * state.operational_capital
    projected = state.cash_active - cost
    if projected < floor:
        return Decision(
            allowed=False,
            reason="cash_min",
            detail={
                "missing": round(floor - projected, 2),
                "floor": round(floor, 2),
                "projected_cash": round(projected, 2),
            },
        )
    return Decision(allowed=True, detail={"floor": round(floor, 2), "projected_cash": round(projected, 2)})


def _tier_rank(resolved: TierBand | str) -> int:
    if isinstance(resolved, TierBand):
        return resolved.tier_number
    return 0 if resolved == PRE_TIER else 999  # OBJECTIVE_REACHED au-dessus de tout


def evaluate_tier_transition(
    current_tier_number: int,
    capital_series: list[float],
    tiers: list[TierBand],
    *,
    sustain_snapshots: int,
    hysteresis_pct: float,
) -> TierTransition | None:
    """Promotion soutenue (confirm requise) ou rétrogradation auto (hystérésis).

    Renvoie ``None`` si l'historique est insuffisant ou si aucune transition
    soutenue n'est constatée sur les ``sustain_snapshots`` derniers points.
    """
    if len(capital_series) < sustain_snapshots:
        return None
    window = capital_series[-sustain_snapshots:]
    ranks = [_tier_rank(resolve_current_tier(c, tiers)) for c in window]

    # Promotion : tous les snapshots récents au-dessus du palier courant.
    if all(r > current_tier_number for r in ranks):
        return TierTransition(
            direction="up",
            target_tier=min(ranks),
            auto=False,
            requires_confirm=True,
        )

    # Rétrogradation : capital soutenu sous capital_min×(1−hysteresis).
    current_band = next((b for b in tiers if b.tier_number == current_tier_number), None)
    if current_band is not None:
        demote_floor = current_band.capital_min * (1 - hysteresis_pct / 100.0)
        if all(c < demote_floor for c in window):
            return TierTransition(
                direction="down",
                target_tier=max(current_tier_number - 1, 0),
                auto=True,
                requires_confirm=False,
            )

    return None
