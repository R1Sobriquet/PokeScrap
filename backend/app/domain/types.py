"""DTO du moteur (dataclasses immuables).

Tout ce que les fonctions pures de ``domain/`` reçoivent ou renvoient. Aucun
import d'ORM, de DB ou de réseau : ce module ne dépend que de la stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# --------------------------------------------------------------- entrées
@dataclass(frozen=True)
class TierBand:
    """Un palier : bande de capital ``[capital_min, capital_max)`` + garde cash."""

    tier_number: int
    capital_min: float
    capital_max: float | None
    cash_min_pct: float


@dataclass(frozen=True)
class PortfolioState:
    cash_active: float
    capital_invested: float
    cash_locked: float = 0.0

    @property
    def cash_total(self) -> float:
        return self.cash_active + self.cash_locked

    @property
    def operational_capital(self) -> float:
        # Capital opérationnel au coût = cash actif + capital investi (au coût).
        return self.cash_active + self.capital_invested


@dataclass(frozen=True)
class DetectedProduct:
    product_id: int
    qty: int
    confidence: float
    is_illustration_rare: bool = False


@dataclass(frozen=True)
class PriceInfo:
    """Prix et stats d'un produit, dans la devise de valorisation (USD en US)."""

    price: float | None
    avg_7d: float | None = None
    avg_30d: float | None = None
    sale_count: int | None = None
    approx_sale_count: bool = False


@dataclass(frozen=True)
class ListingInput:
    acquisition_cost_total: float
    estimated_total_cards: int
    detected_products: tuple[DetectedProduct, ...] = ()


@dataclass(frozen=True)
class ValuationParams:
    """Constantes de valorisation (issues de ``settings``)."""

    min_match_confidence: float
    default_sell_platform: str
    bulk_value_per_card: float
    vinted_fee_rate: float
    lot_confidence_haircut: float
    fee_rates: dict
    ir_lot_value_share: float
    fx: float = 1.0  # 1.0 en mode EU ; fx_usd_eur en mode prototype US


# --------------------------------------------------------------- sorties
@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str | None = None
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BuyDecision:
    passes: bool
    hard_block: bool
    ratio_pct: float | None
    resale_value: float
    reason: str | None = None


@dataclass(frozen=True)
class FilterResult:
    passes: bool
    flags: dict


@dataclass(frozen=True)
class TierTransition:
    direction: str  # 'up' | 'down'
    target_tier: int
    auto: bool
    requires_confirm: bool


@dataclass(frozen=True)
class PEAccumulationResult:
    fire: bool
    trigger_count: int
    triggers: tuple[str, ...]


# --------------------------------------------------------------- vente (S5)
@dataclass(frozen=True)
class SellPosition:
    """État d'une position vu par le moteur de vente."""

    quantity: int
    avg_cost: float
    stage_capital_secured: bool = False
    stage_structured: bool = False
    stage_forced: bool = False


@dataclass(frozen=True)
class SellDecision:
    action: str  # voir constantes selling.*
    qty_to_sell: int = 0
    speculative_reserve_qty: int = 0
    stages_to_set: tuple[str, ...] = ()
    keeps_wick: bool = False
    severity: str = "warning"
    reason: str | None = None
