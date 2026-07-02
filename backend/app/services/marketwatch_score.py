"""Recalcul quotidien des signaux ``daily_signals`` depuis l'historique.

Pour chaque (card_id, langue) présent sur les 180 derniers jours, on construit une
série journalière (médiane des sources) et on dérive les composantes
(``domain.marketwatch_signals``) puis le score de CLASSEMENT. Upsert idempotent
par (card_id, language, computed_at).

⚠️ Le score classe des candidats à VÉRIFIER — il ne prédit pas et ne déclenche
aucun achat. La sélection (digest) applique en plus un plancher de liquidité et
la priorité de langue EN > JP > FR.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict
from decimal import Decimal
from urllib.parse import quote_plus

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.domain import marketwatch_signals as sig
from app.models import CardPriceSnapshot, CatalystEvent, DailySignal, PopularityTier, TcgdexCard

logger = logging.getLogger("services.marketwatch_score")

HISTORY_DAYS = 180
_LANG_PRIORITY = {"EN": 0, "JP": 1, "FR": 2}
_DEFAULT_BUY_URL = "https://www.cardmarket.com/en/Pokemon/Products/Search?searchString={query}"


def _q(x: float | None) -> Decimal | None:
    return Decimal(str(round(x, 4))) if x is not None else None


def _daily_median_series(rows) -> dict[tuple[str, str], dict[dt.date, float]]:
    """(card_id, language) → {jour: médiane des prix des sources ce jour}."""
    buckets: dict[tuple[str, str], dict[dt.date, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        buckets[(r.card_id, r.language)][r.captured_at].append(float(r.price_eur))
    out: dict[tuple[str, str], dict[dt.date, float]] = {}
    for key, per_day in buckets.items():
        out[key] = {d: sig.median(v) for d, v in per_day.items()}
    return out


def _liquidity_by_card(rows) -> dict[str, tuple[int | None, int | None]]:
    """card_id → (active_listings, watchers) du snapshot eBay actif le plus récent."""
    best: dict[str, tuple[dt.date, int | None, int | None]] = {}
    for r in rows:
        if r.source != "ebay_active":
            continue
        cur = best.get(r.card_id)
        if cur is None or r.captured_at > cur[0]:
            best[r.card_id] = (r.captured_at, r.active_listings, r.watchers)
    return {cid: (a, w) for cid, (_d, a, w) in best.items()}


def _window_mean(series: dict[dt.date, float], today: dt.date, days: int) -> float | None:
    cutoff = today - dt.timedelta(days=days)
    return sig.sma([v for d, v in series.items() if d >= cutoff])


def _value_days_ago(series: dict[dt.date, float], today: dt.date, days: int) -> float | None:
    """Valeur au jour le plus proche AVANT ``today - days`` (proxy prix passé)."""
    target = today - dt.timedelta(days=days)
    older = [(d, v) for d, v in series.items() if d <= target]
    if not older:
        return None
    return max(older, key=lambda dv: dv[0])[1]


def _cross_lang_by_card(series: dict[tuple[str, str], dict[dt.date, float]]) -> dict[str, float]:
    """card_id → composante cross-langue (courant vs médiane historique du spread)."""
    by_card: dict[str, dict[str, dict[dt.date, float]]] = defaultdict(dict)
    for (cid, lang), s in series.items():
        by_card[cid][lang] = s
    out: dict[str, float] = {}
    for cid, langs in by_card.items():
        if len(langs) < 2:
            out[cid] = 0.0
            continue
        latest = {lang: s[max(s)] for lang, s in langs.items() if s}
        # spreads historiques : par jour où ≥2 langues cotent.
        all_days: set[dt.date] = set()
        for s in langs.values():
            all_days.update(s.keys())
        hist_spreads = []
        for d in all_days:
            day_prices = [s[d] for s in langs.values() if d in s]
            if len(day_prices) >= 2:
                lo, hi = min(day_prices), max(day_prices)
                if lo > 0:
                    hist_spreads.append((hi - lo) / lo)
        out[cid] = sig.cross_lang(latest, sig.median(hist_spreads))
    return out


def _tiers(db: Session) -> tuple[dict[str, str], dict[str, str]]:
    by_card, by_pokemon = {}, {}
    for t in db.scalars(select(PopularityTier)).all():
        if t.card_id:
            by_card[t.card_id] = t.tier
        if t.pokemon:
            by_pokemon[t.pokemon.lower()] = t.tier
    return by_card, by_pokemon


def _catalyst_days(events: list[CatalystEvent], today: dt.date,
                   card: TcgdexCard | None) -> int | None:
    """Jours jusqu'au prochain catalyseur pertinent (global/set/pokemon)."""
    scopes = {"global"}
    if card is not None:
        if card.set_id:
            scopes.add(f"set:{card.set_id}")
        if card.pokemon:
            scopes.add(f"pokemon:{card.pokemon}")
    best: int | None = None
    for ev in events:
        if ev.scope not in scopes:
            continue
        days = (ev.event_date - today).days
        if days < 0:
            continue
        best = days if best is None else min(best, days)
    return best


def run_score(db: Session, *, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    cutoff = today - dt.timedelta(days=HISTORY_DAYS)
    rows = db.scalars(
        select(CardPriceSnapshot).where(CardPriceSnapshot.captured_at >= cutoff)
    ).all()
    if not rows:
        return {"summary": "aucun snapshot récent — 0 signal", "signals": 0}

    series = _daily_median_series(rows)
    liq_by_card = _liquidity_by_card(rows)
    cross_by_card = _cross_lang_by_card(series)
    by_card_tier, by_pokemon_tier = _tiers(db)
    events = list(db.scalars(select(CatalystEvent)).all())
    cards = {c.card_id: c for c in db.scalars(select(TcgdexCard)).all()}
    buy_tpl = str(get_setting("marketwatch_buy_url_template", default="") or _DEFAULT_BUY_URL)

    written = 0
    for (card_id, language), s in series.items():
        if not s:
            continue
        latest_day = max(s)
        price = s[latest_day]
        min_180 = min(s.values())
        sma90 = _window_mean(s, today, 90)
        sma30 = _window_mean(s, today, 30)
        sma7 = _window_mean(s, today, 7)
        mom_7d = sig.momentum(price, _value_days_ago(s, today, 7))

        card = cards.get(card_id)
        tier = by_card_tier.get(card_id)
        if tier is None and card is not None and card.pokemon:
            tier = by_pokemon_tier.get(card.pokemon.lower())

        near = sig.near_low(price, min_180)
        draw = sig.drawdown_sma(price, sma90)
        bott = sig.bottoming(sma7, sma30, mom_7d)
        cross = cross_by_card.get(card_id, 0.0)
        active, watchers = liq_by_card.get(card_id, (None, None))
        liq = sig.liquidity(active, watchers)
        score = sig.composite_score(
            near_low_v=near, drawdown_v=draw, bottoming_v=bott, cross_lang_v=cross,
            liquidity_v=liq, tier_mult=sig.tier_multiplier(tier),
            catalyst=sig.catalyst_bonus(_catalyst_days(events, today, card)),
        )
        name = (card.name_en or card.name_fr or card.name_jp) if card else card_id
        buy_url = buy_tpl.format(query=quote_plus(name or card_id))
        _upsert(db, card_id, language, today, price=price, near=near, draw=draw,
                bott=bott, cross=cross, liq=liq, mom_7d=mom_7d, score=score,
                budget=sig.budget_band(price), buy_url=buy_url)
        written += 1

    db.commit()
    return {"summary": f"{written} signaux recalculés ({today})", "signals": written}


def _upsert(db: Session, card_id: str, language: str, day: dt.date, *, price, near,
            draw, bott, cross, liq, mom_7d, score, budget, buy_url) -> None:
    existing = db.scalar(
        select(DailySignal).where(
            DailySignal.card_id == card_id, DailySignal.language == language,
            DailySignal.computed_at == day,
        )
    )
    fields = dict(
        price_eur=_q(price), near_low=_q(near), drawdown_sma=_q(draw), bottoming=_q(bott),
        cross_lang=_q(cross), liquidity=_q(liq), momentum_7d=_q(mom_7d),
        score=_q(score) or Decimal("0"), budget_band=budget, buy_url=buy_url,
    )
    if existing is not None:
        for k, v in fields.items():
            setattr(existing, k, v)
        return
    db.add(DailySignal(card_id=card_id, language=language, computed_at=day, **fields))


def select_targets(db: Session, day: dt.date, *, min_liquidity: float | None = None,
                   limit_per_band: int = 8) -> dict[str, list[DailySignal]]:
    """Short-list pour le digest : plancher de liquidité + priorité EN>JP>FR + tranches.

    Une carte n'apparaît qu'une fois (langue de priorité la plus haute parmi ses
    lignes) ; on regroupe par tranche budget et on trie par score décroissant.
    """
    if min_liquidity is None:
        min_liquidity = float(get_setting("marketwatch_min_liquidity", default=0.0))
    rows = db.scalars(select(DailySignal).where(DailySignal.computed_at == day)).all()

    # 1 ligne par card_id : priorité de langue EN>JP>FR.
    best_by_card: dict[str, DailySignal] = {}
    for r in rows:
        cur = best_by_card.get(r.card_id)
        if cur is None or _LANG_PRIORITY.get(r.language, 9) < _LANG_PRIORITY.get(cur.language, 9):
            best_by_card[r.card_id] = r

    bands: dict[str, list[DailySignal]] = {"lt10": [], "10_20": [], "lte50": []}
    for r in best_by_card.values():
        if r.budget_band not in bands:
            continue  # hors tranches cibles (>50 €)
        if float(r.liquidity or 0) < min_liquidity:
            continue  # garde-fou anti-illiquide
        bands[r.budget_band].append(r)
    for band in bands.values():
        band.sort(key=lambda s: float(s.score or 0), reverse=True)
        del band[limit_per_band:]
    return bands
