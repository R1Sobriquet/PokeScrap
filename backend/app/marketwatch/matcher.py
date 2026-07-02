"""Matcher Cardmarket ``idProduct`` → ``card_id`` TCGdex (pur, testable).

Le point dur du pipeline : Cardmarket ne porte pas l'ID TCGdex. On rapproche un
produit Cardmarket (nom + numéro + extension) d'une carte du registre canonique
en s'appuyant sur les **noms multilingues** TCGdex (EN/FR/JP) et le **numéro de
carte**.

Stratégie (du plus sûr au plus souple), confiance ∈ [0,1] :
  1. numéro identique + similarité de nom forte  → ``set_number`` (haute conf.) ;
  2. nom quasi exact (numéro absent/incohérent)  → ``name`` (conf. moyenne).
Sous le seuil, on ne devine pas : ``None`` (le produit part en non-matché → log /
``match_review`` côté appelant). Fonctions PURES : aucune I/O, aucune dépendance DB.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from app.marketwatch.domain import CardmarketProduct, MatchResult, RegistryCard

# Seuils (réglables côté appelant si besoin).
NAME_SIM_STRONG = 0.80   # similarité de nom jugée fiable avec numéro concordant
NAME_SIM_NAMEONLY = 0.92  # similarité requise sans appui du numéro
AUTO_CONFIDENCE = 0.80    # au-dessus → match auto ; en dessous → non-matché

# Suffixes/qualificatifs de variante à ignorer pour comparer les noms.
_VARIANT_NOISE = {
    "reverse", "holo", "holofoil", "foil", "promo", "rev",
    "fullart", "full", "art", "rainbow", "secret", "alt", "alternate",
    "cosmos", "staff", "prerelease", "league",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_name(name: str | None) -> str:
    """Minuscule, sans accents, sans parenthèses ni ponctuation, espaces compactés."""
    if not name:
        return ""
    s = _strip_accents(str(name)).lower()
    s = re.sub(r"\([^)]*\)", " ", s)          # retire les '(reverse holo)' etc.
    s = re.sub(r"[^a-z0-9\s]", " ", s)         # ponctuation → espace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def name_tokens(name: str | None) -> frozenset[str]:
    """Jeton de comparaison : mots significatifs (bruit de variante retiré)."""
    toks = {t for t in normalize_name(name).split() if t and t not in _VARIANT_NOISE}
    return frozenset(toks)


def normalize_number(number: str | None) -> str:
    """Numéro de carte comparable : partie avant '/', zéros de tête retirés.

    ``'215/203'`` → ``'215'`` ; ``'012'`` → ``'12'`` ; ``'TG20/TG30'`` → ``'tg20'``.
    """
    if not number:
        return ""
    head = str(number).split("/")[0].strip().lower()
    head = re.sub(r"[^a-z0-9]", "", head)
    if head.isdigit():
        return str(int(head))  # retire les zéros de tête
    # alphanumérique (ex. 'tg20') : retire les zéros de tête du segment numérique
    m = re.match(r"([a-z]+)0*([0-9]+)$", head)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return head


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _best_name_sim(product_tokens: frozenset[str], card: RegistryCard) -> float:
    """Meilleure similarité du nom produit vs les noms multilingues de la carte."""
    best = 0.0
    for nm in card.names():
        best = max(best, _jaccard(product_tokens, name_tokens(nm)))
    return best


def match_cardmarket(
    product: CardmarketProduct,
    registry: Sequence[RegistryCard],
    *,
    name_strong: float = NAME_SIM_STRONG,
    name_only: float = NAME_SIM_NAMEONLY,
) -> MatchResult | None:
    """Rapproche un produit Cardmarket d'une carte du registre, ou ``None``.

    On privilégie le couple (numéro concordant + nom proche). À défaut de numéro
    exploitable, on exige une similarité de nom très élevée pour éviter les faux.
    """
    p_tokens = name_tokens(product.name)
    if not p_tokens:
        return None
    p_number = normalize_number(product.number)

    # 1) Numéro concordant → on cherche la meilleure similarité de nom parmi eux.
    if p_number:
        numbered = [c for c in registry if normalize_number(c.number) == p_number]
        best_card, best_sim = None, 0.0
        for c in numbered:
            sim = _best_name_sim(p_tokens, c)
            if sim > best_sim:
                best_card, best_sim = c, sim
        if best_card is not None and best_sim >= name_strong:
            # Confiance : tirée par la similarité, bornée à [name_strong, 0.99].
            conf = min(0.99, 0.80 + (best_sim - name_strong) * 0.9)
            return MatchResult(best_card.card_id, round(conf, 3), "set_number")

    # 2) Pas de numéro exploitable / pas de concordance → nom quasi exact, unique.
    scored = sorted(
        ((c, _best_name_sim(p_tokens, c)) for c in registry),
        key=lambda cs: cs[1], reverse=True,
    )
    if scored and scored[0][1] >= name_only:
        top_sim = scored[0][1]
        # Ambiguïté : deux cartes aussi proches → on refuse (pas de devinette).
        if len(scored) > 1 and abs(scored[1][1] - top_sim) < 1e-9:
            return None
        conf = min(0.95, 0.70 + (top_sim - name_only) * 1.5)
        return MatchResult(scored[0][0].card_id, round(conf, 3), "name")

    return None
