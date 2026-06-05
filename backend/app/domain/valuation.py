"""Valorisation de lot & devise (réf. S3) — fonctions pures."""

from __future__ import annotations

from app.domain.types import ListingInput, PriceInfo, ValuationParams


def fee_rate(platform: str, fee_rates: dict) -> float:
    return float(fee_rates.get(platform, 0.0))


def net_value(gross: float, platform: str, *, fee_rates: dict) -> float:
    """Valeur nette de commission plateforme."""
    return gross * (1 - fee_rate(platform, fee_rates) / 100.0)


def to_eur(value: float, fx: float) -> float:
    """Conversion proxy USD→EUR (``fx`` = 1.0 en mode EU)."""
    return value * fx


def _identified(listing: ListingInput, min_match_confidence: float):
    return [p for p in listing.detected_products if p.confidence >= min_match_confidence]


def _net_unit_eur(info: PriceInfo, params: ValuationParams) -> float | None:
    if info is None or info.price is None:
        return None
    price_eur = to_eur(info.price, params.fx)
    return net_value(price_eur, params.default_sell_platform, fee_rates=params.fee_rates)


def estimate_lot_resale_net(
    listing: ListingInput,
    prices: dict[int, PriceInfo],
    params: ValuationParams,
) -> float:
    """Valeur de revente nette estimée d'un lot mixte (identifié + vrac).

    Net de frais, vrac valorisé au tarif plancher (net de Vinted), le tout
    minoré par le haircut prudentiel.
    """
    value = 0.0
    for p in _identified(listing, params.min_match_confidence):
        unit = _net_unit_eur(prices.get(p.product_id), params)
        if unit is not None:
            value += unit * p.qty

    identified_qty = sum(p.qty for p in _identified(listing, params.min_match_confidence))
    bulk = max(0, listing.estimated_total_cards - identified_qty)
    value += bulk * params.bulk_value_per_card * (1 - params.vinted_fee_rate / 100.0)

    return value * params.lot_confidence_haircut


def is_IR_lot(
    listing: ListingInput,
    prices: dict[int, PriceInfo],
    params: ValuationParams,
) -> bool:
    """Vrai si la valeur des Illustration Rares ≥ ``ir_lot_value_share``% du total."""
    total = 0.0
    ir = 0.0
    for p in _identified(listing, params.min_match_confidence):
        unit = _net_unit_eur(prices.get(p.product_id), params)
        if unit is None:
            continue
        v = unit * p.qty
        total += v
        if p.is_illustration_rare:
            ir += v
    if total <= 0:
        return False
    return ir >= (params.ir_lot_value_share / 100.0) * total
