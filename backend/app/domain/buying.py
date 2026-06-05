"""Règle des 50 %, garde-fou IR, et scoring d'opportunité (réf. S3) — pur."""

from __future__ import annotations

from app.domain.types import BuyDecision, ListingInput, PriceInfo, ValuationParams
from app.domain.valuation import estimate_lot_resale_net, is_IR_lot

#: Facteurs de palier watchlist pour le scoring.
TIER_FACTORS = {"S++": 1.0, "S": 0.8, "A": 0.6, "B": 0.4, "C": 0.2}


def evaluate_buy(
    listing: ListingInput,
    prices: dict[int, PriceInfo],
    params: ValuationParams,
    *,
    fifty_rule_threshold_pct: float,
    ir_min_discount_pct: float,
) -> BuyDecision:
    """Décision d'achat : règle des 50 % nette + garde-fou IR (plancher absolu).

    - ``passes`` si ``ratio <= fifty_rule_threshold_pct`` (coût/revente nette).
    - **HARD_BLOCK** (``ir_absolute_floor``) si lot IR et ``ratio > 100 −
      ir_min_discount_pct`` : bloque même un override manuel.
    """
    resale = estimate_lot_resale_net(listing, prices, params)
    if resale <= 0:
        return BuyDecision(
            passes=False, hard_block=False, ratio_pct=None, resale_value=0.0,
            reason="no_resale_value",
        )

    ratio = listing.acquisition_cost_total / resale * 100.0
    ir_floor = 100.0 - ir_min_discount_pct
    hard_block = is_IR_lot(listing, prices, params) and ratio > ir_floor
    passes = (ratio <= fifty_rule_threshold_pct) and not hard_block

    if hard_block:
        reason = "ir_absolute_floor"
    elif not passes:
        reason = "ratio_above_threshold"
    else:
        reason = None

    return BuyDecision(
        passes=passes,
        hard_block=hard_block,
        ratio_pct=round(ratio, 2),
        resale_value=round(resale, 2),
        reason=reason,
    )


def liquidity_factor(sale_count: int | None, midpoint: float) -> float:
    """Saturation douce dans [0, 1) : ``s / (s + midpoint)``."""
    s = sale_count or 0
    if s <= 0:
        return 0.0
    return s / (s + midpoint)


def tier_factor(tier: str) -> float:
    return TIER_FACTORS.get(tier, TIER_FACTORS["B"])


def opportunity_score(
    *,
    ratio_pct: float,
    threshold_pct: float,
    priority_coef: float,
    sale_count: int | None,
    tier: str,
    w_margin: float,
    w_liquidity: float,
    w_tier: float,
    liquidity_midpoint: float,
) -> float:
    """Score d'opportunité : marge + liquidité (pondérée priorité) + palier."""
    margin = (threshold_pct - ratio_pct) / threshold_pct if threshold_pct else 0.0
    liq = priority_coef * liquidity_factor(sale_count, liquidity_midpoint)
    return w_margin * margin + w_liquidity * liq + w_tier * tier_factor(tier)
