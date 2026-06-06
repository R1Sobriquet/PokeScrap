"""Comptabilité — calculs purs (réf. S7).

Cascade de trésorerie, verrouillage 30/70, KPIs, provision fiscale. Aucune I/O :
les services lisent la base et passent des nombres/listes ici.
"""

from __future__ import annotations


def lock_increment(
    profit: float,
    *,
    reinvest_lock_pct: float,
    lock_only_positive: bool = True,
) -> float:
    """Part de bénéfice à verrouiller (30/70). Jamais négative."""
    if profit <= 0:
        return 0.0 if lock_only_positive else 0.0
    return reinvest_lock_pct / 100.0 * profit


def cash_active(cash_total: float, cash_locked: float) -> float:
    """Cash actif = cash total − cash verrouillé (provision informative non déduite)."""
    return cash_total - cash_locked


def operational_capital(cash_active_value: float, capital_invested: float) -> float:
    return cash_active_value + capital_invested


def realized_profit_net(
    sell_pairs: list[tuple[float, float]],
    isolated_fees: float = 0.0,
) -> float:
    """Σ(net_amount − cost_basis) sur les ventes − Σ frais isolés."""
    return sum(net - cost for net, cost in sell_pairs) - isolated_fees


def capital_rotation_rate(cogs_sold: float, avg_capital_invested: float) -> float | None:
    """Rotation = COGS vendus sur la période / capital investi moyen."""
    if avg_capital_invested <= 0:
        return None
    return cogs_sold / avg_capital_invested


def tax_provision(turnover_cumulative: float, tax_provision_pct: float) -> float:
    return turnover_cumulative * tax_provision_pct / 100.0


def total_portfolio_value(cash_total: float, market_values: list[float]) -> float:
    return cash_total + sum(market_values)
