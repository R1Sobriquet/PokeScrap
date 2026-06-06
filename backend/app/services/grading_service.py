"""Module A — authenticité (gratuite, tous modes) & comparateur grading (Pro).

``verify_slab`` marche partout. ``run_grading_scan`` est gated derrière
``feature_grading_enabled`` (no-op propre en mode Free). Métier pur dans
``domain.grading`` ; ici on lit les prix et on persiste.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.domain.grading import grade_probability, grading_uplift, slab_verdict
from app.models import Alert, GradingOpportunity, Position, Product, PsaCert, Watchlist
from app.services.prices import get_latest_price
from app.services.psa_service import verify_and_persist_cert

logger = logging.getLogger("services.grading")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _f(v, default=0.0) -> float:
    return float(v) if v is not None else default


def _fee_rates() -> dict:
    return {
        "cardmarket": _f(get_setting("fee_rate_cardmarket", default=5.0)),
        "ebay": _f(get_setting("fee_rate_ebay", default=12.0)),
        "vinted": _f(get_setting("fee_rate_vinted", default=0.0)),
    }


def verify_slab(db: Session, cert_number: str, *, provider=None) -> dict:
    """Vérifie un slab (gratuit, tous modes). Invalide → HARD_BLOCK ; valide → WARN.

    Ne garantit JAMAIS l'authenticité : au mieux « cohérent, à inspecter ».
    """
    cert = verify_and_persist_cert(db, cert_number, provider=provider)
    decision, reason = slab_verdict(bool(cert.is_valid))
    return {
        "decision": decision,
        "reason": reason,
        "is_valid": bool(cert.is_valid),
        "grade": cert.grade,
        "message": "Cert invalide — achat bloqué." if decision == "hard_block"
        else "Cert valide ✔ — inspection physique requise (contrefaçons possibles).",
    }


def _candidate_product_ids(db: Session) -> list[int]:
    pos_ids = db.scalars(
        select(Position.product_id).where(Position.quantity > 0, Position.grade_company == "RAW")
    ).all()
    watch_ids = db.scalars(select(Watchlist.product_id).where(Watchlist.is_active == 1)).all()
    return list(dict.fromkeys([*pos_ids, *watch_ids]))


def _upsert_opportunity(db: Session, product_id: int, result, now: dt.datetime) -> None:
    opp = db.scalar(select(GradingOpportunity).where(GradingOpportunity.product_id == product_id))
    if opp is None:
        opp = GradingOpportunity(product_id=product_id)
        db.add(opp)
    opp.raw_value = result.raw_net
    opp.expected_net_weighted = result.expected_net
    opp.grading_cost = result.grading_cost
    opp.grade_probability = result.grade_probability
    opp.is_recommended = 1 if result.is_recommended else 0
    opp.computed_at = now


def run_grading_scan(db: Session, *, now: dt.datetime | None = None) -> dict:
    """Scan grading hebdo — NO-OP propre hors mode Pro."""
    if not bool(get_setting("feature_grading_enabled", default=False)):
        logger.info("grading_scan différé : mode Free")
        return {"status": "skipped", "reason": "feature_grading_disabled"}

    now = now or _utcnow()
    market = str(get_setting("valuation_market", default="US"))
    fx = _f(get_setting("fx_usd_eur", default=0.92)) if market == "US" else 1.0
    fee_rates = _fee_rates()
    sell_platform = str(get_setting("graded_route", default="ebay"))
    grading_cost = _f(get_setting("grading_psa_fee_eur", default=80)) + _f(
        get_setting("grading_logistics_eur", default=40)
    )
    min_card_value = _f(get_setting("grading_min_card_value", default=100))
    min_uplift_eur = _f(get_setting("grading_min_uplift_eur", default=50))
    min_uplift_pct = _f(get_setting("grading_min_uplift_pct", default=50))
    prob_source = str(get_setting("grade_prob_source", default="pop_report"))
    prob_default = get_setting("grade_prob_default", default={"10": 0.30, "9": 0.45, "le8": 0.25})

    scanned = recommended = 0
    for product_id in _candidate_product_ids(db):
        nm = get_latest_price(db, product_id, market=market)
        if nm is None or nm.price_avg is None:
            continue
        psa10 = get_latest_price(db, product_id, grade_company="PSA", grade="10", condition=None, market=market)
        psa9 = get_latest_price(db, product_id, grade_company="PSA", grade="9", condition=None, market=market)

        cert = db.scalar(select(PsaCert).where(PsaCert.product_id == product_id))
        prob = grade_probability(cert.pop_data if cert else None, source=prob_source, default=prob_default)

        result = grading_uplift(
            price_nm=_f(nm.price_avg) * fx,
            price_psa10=_f(psa10.price_avg) * fx if psa10 and psa10.price_avg is not None else 0.0,
            price_psa9=_f(psa9.price_avg) * fx if psa9 and psa9.price_avg is not None else 0.0,
            probability=prob,
            grading_cost=grading_cost,
            fee_rates=fee_rates,
            sell_platform=sell_platform,
            min_uplift_eur=min_uplift_eur,
            min_uplift_pct=min_uplift_pct,
            min_card_value=min_card_value,
        )
        _upsert_opportunity(db, product_id, result, now)
        scanned += 1

        if result.is_recommended:
            recommended += 1
            db.add(Alert(
                alert_type="grading", severity="info", status="pending", product_id=product_id,
                title=f"Grading recommandé (+{result.uplift:.0f}€)",
                payload={
                    "uplift": result.uplift, "uplift_pct": result.uplift_pct,
                    "raw_net": result.raw_net, "expected_net": result.expected_net,
                    "grading_cost": result.grading_cost,
                    "grade_probability": result.grade_probability,
                    "caveats": "Coût élevé (PSA + logistique), capital immobilisé plusieurs mois ; "
                               "le pop report surestime les hauts grades (biais de survie).",
                },
            ))
    db.commit()
    logger.info("grading_scan : %s évalués, %s recommandés.", scanned, recommended)
    return {"status": "ok", "scanned": scanned, "recommended": recommended}
