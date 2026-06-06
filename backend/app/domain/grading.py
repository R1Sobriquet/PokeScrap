"""Grading (réf. S8, Module A) — fonctions pures.

Comparateur d'opportunité (espérance pondérée par les probabilités de grade) et
verdict d'authenticité. Honnêteté intégrée : coût élevé, capital immobilisé, et le
pop report **surestime** les hauts grades (biais de survie) → défaut conservateur.
"""

from __future__ import annotations

from app.domain.types import GradingResult
from app.domain.valuation import net_value

# Verdicts d'authenticité.
SLAB_HARD_BLOCK = "hard_block"
SLAB_WARN = "warn"


def grade_probability(pop: dict | None, *, source: str, default: dict) -> dict:
    """Probabilités {'10','9','le8'} : pop_report si résoluble, sinon défaut.

    Le pop report brut surestime les hauts grades ; on ne s'en sert que s'il est
    clairement résoluble, sinon on retombe sur le défaut conservateur.
    """
    if source != "pop_report" or not pop:
        return dict(default)
    try:
        n10 = float(pop.get("10", pop.get("psa10", 0)) or 0)
        n9 = float(pop.get("9", pop.get("psa9", 0)) or 0)
        n_le8 = float(pop.get("le8", 0) or 0)
        if n_le8 == 0:  # somme des grades <= 8 si détaillés
            n_le8 = sum(float(pop.get(str(g), 0) or 0) for g in range(1, 9))
        total = n10 + n9 + n_le8
        if total <= 0:
            return dict(default)
        return {"10": n10 / total, "9": n9 / total, "le8": n_le8 / total}
    except (TypeError, ValueError):
        return dict(default)


def grading_uplift(
    *,
    price_nm: float | None,
    price_psa10: float | None,
    price_psa9: float | None,
    probability: dict,
    grading_cost: float,
    fee_rates: dict,
    sell_platform: str,
    min_uplift_eur: float,
    min_uplift_pct: float,
    min_card_value: float,
) -> GradingResult:
    """Espérance pondérée − valeur brute − coût ; recommandé si seuils franchis."""
    raw = net_value(price_nm or 0.0, sell_platform, fee_rates=fee_rates)
    net10 = net_value(price_psa10 or 0.0, sell_platform, fee_rates=fee_rates)
    net9 = net_value(price_psa9 or 0.0, sell_platform, fee_rates=fee_rates)

    expected = probability["10"] * net10 + probability["9"] * net9 + probability["le8"] * raw
    uplift = expected - raw - grading_cost
    uplift_pct = (uplift / raw * 100.0) if raw > 0 else 0.0

    is_recommended = (
        uplift >= min_uplift_eur
        and uplift_pct >= min_uplift_pct
        and raw >= min_card_value
    )
    return GradingResult(
        raw_net=round(raw, 2),
        expected_net=round(expected, 2),
        grading_cost=round(grading_cost, 2),
        uplift=round(uplift, 2),
        uplift_pct=round(uplift_pct, 2),
        grade_probability=probability,
        is_recommended=is_recommended,
    )


def slab_verdict(is_valid: bool) -> tuple[str, str]:
    """Verdict d'authenticité — jamais « authentique garanti ».

    Cert invalide → HARD_BLOCK ; cert valide → WARN (inspection physique requise,
    car des contrefaçons réutilisent de vrais numéros).
    """
    if not is_valid:
        return SLAB_HARD_BLOCK, "cert_invalid"
    return SLAB_WARN, "cert_valid_inspect"
