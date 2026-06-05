"""MOTEUR DE RÈGLES — fonctions pures, zéro I/O.

Tout le métier des jalons suivants (règle des 50 %, filtres anti-pump/anti-FOMO,
moteur de vente 25/50/25, scoring d'opportunité, paliers, grading pondéré, KPIs…)
vivra ici.

Règle non négociable :

* **Fonctions pures, type-hintées.** Elles reçoivent des dataclasses / DTO et
  renvoient des décisions.
* **Aucun accès base, aucun réseau, aucune horloge cachée.** Tout ce dont une
  fonction a besoin lui est passé en argument (y compris les constantes lues via
  ``get_setting`` côté application, et l'instant courant si pertinent).

Cette discipline rend le moteur testable en isolation et indépendant des sources
de données (mode prototype US gratuit vs réel EU payant).

Jalon 3 : logique d'achat (paliers/cash, règle des 50 %, valorisation de lot,
filtres anti-erreurs, scoring, signal d'accumulation PE).
"""

from app.domain.buying import evaluate_buy, opportunity_score
from app.domain.filters import (
    anti_pump_block,
    fomo_block,
    illiquidity_block,
    passes_S4,
)
from app.domain.pe_signal import pe_accumulation_signal
from app.domain.tiers import (
    OBJECTIVE_REACHED,
    PRE_TIER,
    can_buy,
    cash_min_pct,
    evaluate_tier_transition,
    resolve_current_tier,
)
from app.domain.valuation import estimate_lot_resale_net, is_IR_lot, net_value
from app.domain import types

__all__ = [
    "types",
    # tiers & cash
    "resolve_current_tier",
    "cash_min_pct",
    "can_buy",
    "evaluate_tier_transition",
    "PRE_TIER",
    "OBJECTIVE_REACHED",
    # valuation & 50%
    "net_value",
    "estimate_lot_resale_net",
    "is_IR_lot",
    "evaluate_buy",
    "opportunity_score",
    # filters
    "anti_pump_block",
    "illiquidity_block",
    "fomo_block",
    "passes_S4",
    # PE
    "pe_accumulation_signal",
]
