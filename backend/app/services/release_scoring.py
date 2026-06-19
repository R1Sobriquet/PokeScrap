"""Future Radar — modèle de scores HEURISTIQUE v1 (déterministe, sans I/O).

Calcule hype / confiance / popularité / ROI potentiel d'une sortie à partir de ses
seules données curées (type produit, dates, note source). Heuristique assumée — un
vrai modèle prédictif (signaux communautaires, dépôts d'impression, supply chain)
le remplacera ; les sorties exposent ``scores`` pour que le front cesse d'inventer
des valeurs côté client.
"""

from __future__ import annotations

import datetime as dt

# Poids de rareté/désirabilité par type de produit (sous-chaîne, minuscule).
_TYPE_WEIGHTS = (
    (("upc", "ultra premium"), 0.95),
    (("coffret", "elite trainer", "etb"), 0.82),
    (("display", "booster box"), 0.85),
    (("bundle", "tin", "blister"), 0.68),
    (("booster",), 0.6),
)
_DEFAULT_WEIGHT = 0.5


def _clamp(v: float, lo: int, hi: int) -> int:
    return int(max(lo, min(hi, round(v))))


def _type_weight(product_type: str | None, product_name: str | None) -> float:
    blob = f"{product_type or ''} {product_name or ''}".lower()
    for needles, weight in _TYPE_WEIGHTS:
        if any(n in blob for n in needles):
            return weight
    return _DEFAULT_WEIGHT


def _days_until(date: dt.date | None, today: dt.date) -> int | None:
    if date is None:
        return None
    return (date - today).days


def score_release(release, *, today: dt.date | None = None) -> dict:
    """Renvoie ``{hype, confidence, popularity, roi, heuristic: True}`` (0-100, roi %)."""
    today = today or dt.date.today()
    weight = _type_weight(getattr(release, "product_type", None), getattr(release, "product_name", None))
    rd = getattr(release, "release_date", None)
    pd = getattr(release, "preorder_date", None)
    note = (getattr(release, "source_note", None) or "").strip()

    days = _days_until(rd, today)
    preorder_open = pd is not None and pd <= today and (rd is None or rd >= today)

    # Confiance : d'autant plus haute que la sortie est datée/sourcée.
    confidence = 40.0
    if rd is not None:
        confidence += 25
    if pd is not None:
        confidence += 15
    if len(note) > 10:
        confidence += 15
    if days is not None and 0 <= days <= 120:
        confidence += 5

    # Hype : poids du type + proximité de la sortie + précommande ouverte.
    hype = 30 + weight * 27
    if days is None:
        hype += 6
    elif days < 0:
        hype += 5
    elif days <= 30:
        hype += 30
    elif days <= 60:
        hype += 22
    elif days <= 120:
        hype += 14
    else:
        hype += 6
    if preorder_open:
        hype += 8

    # Popularité estimée : portée grand public du type produit.
    popularity = 25 + weight * 67

    # ROI potentiel (%) : rareté + fenêtre d'appréciation (plus loin = plus haut).
    roi = weight * 120
    if days is None:
        roi += 20
    elif days > 120:
        roi += 40
    elif days >= 60:
        roi += 25
    else:
        roi += 10

    return {
        "hype": _clamp(hype, 30, 99),
        "confidence": _clamp(confidence, 20, 99),
        "popularity": _clamp(popularity, 25, 98),
        "roi": _clamp(roi, 30, 240),
        "heuristic": True,
    }
