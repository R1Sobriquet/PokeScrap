"""Liquidation & segmentation (réf. S6, Module B) — fonctions pures.

Le cœur du jalon : reconditionnement vrac « sans doublons » — aucun lot ne
contient deux exemplaires d'une même carte. Garanti satisfiable par le choix de
``n ≥ max_copies`` (le nombre d'exemplaires de la carte la plus dupliquée).
"""

from __future__ import annotations

import math
from collections import defaultdict

from app.domain.types import BulkBin, LiquidationCard

INDIVIDUAL = "individual"
BULK_THEME = "bulk_theme"


def classify_segmentation(
    product_id: int | None, net_value: float | None, *, individual_threshold: float
) -> str:
    """Carte non identifiée ou de faible valeur → vrac ; sinon individuelle."""
    if product_id is None or net_value is None or net_value < individual_threshold:
        return BULK_THEME
    return INDIVIDUAL


def route_individual(
    is_graded: bool, net_value: float, *, individual_ebay_threshold: float
) -> str:
    """Routage d'une pièce individuelle : gradé → ebay ; ≥ seuil → ebay ; sinon cardmarket."""
    if is_graded:
        return "ebay"
    if net_value >= individual_ebay_threshold:
        return "ebay"
    return "cardmarket"


def build_bulk_lots(
    identified: list[LiquidationCard],
    unidentified_count: int = 0,
    *,
    strategy: str = "set",
    min_theme: int,
    target: int,
    min_size: int,
    max_size: int,
) -> list[BulkBin]:
    """Construit des lots vrac sans doublon par thème + lots « mêlés » génériques."""
    groups: dict[str, list[LiquidationCard]] = defaultdict(list)
    for card in identified:
        groups[card.theme].append(card)

    # Fusionne en « mixte » les thèmes trop petits pour un lot dédié.
    merged: dict[str, list[LiquidationCard]] = defaultdict(list)
    for theme, cards in groups.items():
        if sum(c.qty for c in cards) < min_theme:
            merged["mixte"].extend(cards)
        else:
            merged[theme].extend(cards)

    bins: list[BulkBin] = []
    for theme in sorted(merged):
        cards = merged[theme]
        total = sum(c.qty for c in cards)
        if total == 0:
            continue
        max_copies = max(c.qty for c in cards)
        # n garantit le « sans doublon » satisfiable et vise la taille cible.
        n = max(math.ceil(total / target), max_copies, 1)
        bucket: list[list[int]] = [[] for _ in range(n)]
        sizes = [0] * n

        # Les cartes les plus dupliquées d'abord (plus contraignantes).
        for card in sorted(cards, key=lambda c: -c.qty):
            # Choisit qty bacs, les plus petits, NE contenant PAS déjà la carte.
            chosen = []
            for i in sorted(range(n), key=lambda j: sizes[j]):
                if card.product_id not in bucket[i]:
                    chosen.append(i)
                    if len(chosen) == card.qty:
                        break
            for i in chosen:
                bucket[i].append(card.product_id)
                sizes[i] += 1

        for k, prods in enumerate((b for b in bucket if b), start=1):
            bins.append(BulkBin(f"Vrac {theme} #{k}", tuple(prods), len(prods)))

    # Lots « mêlés » non dédoublonnables (cartes non identifiées).
    if unidentified_count > 0:
        n = max(math.ceil(unidentified_count / target), 1)
        base, rem = divmod(unidentified_count, n)
        for k in range(1, n + 1):
            size = base + (1 if k <= rem else 0)
            if size > 0:
                bins.append(BulkBin(f"Vrac mêlé #{k}", (), size))

    return bins
