"""Signaux de sous-valorisation & score de CLASSEMENT (fonctions pures, zéro I/O).

⚠️ IMPORTANT — Le score CLASSE des candidats à VÉRIFIER par un humain ; il NE
PRÉDIT PAS un prix futur et ne déclenche AUCUN achat. C'est un outil de tri d'une
short-list, rien de plus. Sous un seuil de liquidité, un candidat est exclu même
« pas cher » (garde-fou anti-illiquide, appliqué à la sélection).

Composantes (toutes normalisées ~[0,1]) et pondérations :
    score = ( 0.35·near_low + 0.20·drawdown_sma + 0.20·bottoming
            + 0.15·cross_lang + 0.10·liquidity )
            × tier_multiplier(popularity) × catalyst_bonus(catalyseur < horizon)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

# Pondérations du score (documentées, stables).
W_NEAR_LOW = 0.35
W_DRAWDOWN = 0.20
W_BOTTOMING = 0.20
W_CROSS_LANG = 0.15
W_LIQUIDITY = 0.10

# Multiplicateurs de popularité (signal « soft » éditable à la main).
TIER_MULTIPLIER = {"S": 1.30, "A": 1.15, "B": 1.00, "C": 0.85}
NO_TIER_MULTIPLIER = 1.00

# Catalyseur : bonus si l'événement est à moins de ``CATALYST_HORIZON_DAYS`` jours.
CATALYST_HORIZON_DAYS = 90
CATALYST_MAX_BONUS = 0.20

# Liquidité : point milieu de saturation (n/(n+midpoint)).
LIQUIDITY_MIDPOINT = 8.0


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def near_low(price: float | None, min_180: float | None) -> float | None:
    """Proximité du plancher 180 j : 1 au plancher, → 0 en s'en éloignant."""
    if price is None or min_180 is None or min_180 <= 0:
        return None
    return 1.0 - clamp01((price - min_180) / min_180)


def drawdown_sma(price: float | None, sma90: float | None) -> float:
    """Décote sous la moyenne 90 j : max(0, (sma90 − prix)/sma90)."""
    if price is None or not sma90 or sma90 <= 0:
        return 0.0
    return clamp01(max(0.0, (sma90 - price) / sma90))


def momentum(price: float | None, price_prev: float | None) -> float:
    """Variation relative (prix − prix_préc)/prix_préc, 0 si incalculable."""
    if price is None or not price_prev or price_prev <= 0:
        return 0.0
    return (price - price_prev) / price_prev


def bottoming(sma_short: float | None, sma_long: float | None, mom_7d: float | None) -> float:
    """Sortie de creux : momentum 7–14 j POSITIF avec SMA courte > SMA longue.

    Nul tant que la tendance courte n'a pas repassé la longue (pas encore de
    retournement) ; sinon proportionnel au momentum (20 % en 7 j → 1.0).
    """
    if sma_short is None or not sma_long or sma_long <= 0:
        return 0.0
    if sma_short <= sma_long:
        return 0.0
    if mom_7d is None or mom_7d <= 0:
        return 0.0
    return clamp01(mom_7d * 5.0)


def cross_lang(prices_by_lang: Mapping[str, float | None], hist_median_spread: float | None) -> float:
    """Arbitrage inter-langue : écart EN/JP/FR courant vs médiane historique.

    Écart relatif = (max − min)/min sur les prix des langues disponibles pour le
    MÊME card_id. Rapporté à 2× la médiane historique du spread (→ 1.0).
    """
    vals = [float(p) for p in prices_by_lang.values() if p]
    if len(vals) < 2:
        return 0.0
    lo, hi = min(vals), max(vals)
    if lo <= 0:
        return 0.0
    spread = (hi - lo) / lo
    if hist_median_spread and hist_median_spread > 0:
        return clamp01(spread / (hist_median_spread * 2.0))
    return clamp01(spread)


def liquidity(active_listings: int | None, watchers: int | None,
              midpoint: float = LIQUIDITY_MIDPOINT) -> float:
    """Proxy offre+demande, saturant : n/(n+midpoint) ∈ [0,1)."""
    n = (active_listings or 0) + (watchers or 0)
    if n <= 0:
        return 0.0
    return n / (n + midpoint)


def tier_multiplier(tier: str | None) -> float:
    return TIER_MULTIPLIER.get(tier or "", NO_TIER_MULTIPLIER)


def catalyst_bonus(days_to_event: int | None, horizon: int = CATALYST_HORIZON_DAYS) -> float:
    """1.0 hors horizon ; jusqu'à 1+CATALYST_MAX_BONUS à l'imminence de l'événement."""
    if days_to_event is None or days_to_event < 0 or days_to_event > horizon:
        return 1.0
    return 1.0 + CATALYST_MAX_BONUS * (1.0 - days_to_event / horizon)


def composite_score(
    *,
    near_low_v: float | None,
    drawdown_v: float | None,
    bottoming_v: float | None,
    cross_lang_v: float | None,
    liquidity_v: float | None,
    tier_mult: float = NO_TIER_MULTIPLIER,
    catalyst: float = 1.0,
) -> float:
    """Agrège les composantes pondérées puis applique tier & catalyseur."""
    base = (
        W_NEAR_LOW * (near_low_v or 0.0)
        + W_DRAWDOWN * (drawdown_v or 0.0)
        + W_BOTTOMING * (bottoming_v or 0.0)
        + W_CROSS_LANG * (cross_lang_v or 0.0)
        + W_LIQUIDITY * (liquidity_v or 0.0)
    )
    return base * tier_mult * catalyst


def budget_band(price: float | None) -> str | None:
    """Tranche budget cible : <10 € / 10–20 € / ≤50 € ; ``None`` au-delà de 50 €."""
    if price is None:
        return None
    if price < 10:
        return "lt10"
    if price <= 20:
        return "10_20"
    if price <= 50:
        return "lte50"
    return None


def sma(values: Sequence[float]) -> float | None:
    """Moyenne simple, ``None`` si vide."""
    vals = [float(v) for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def median(values: Sequence[float]) -> float | None:
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2
