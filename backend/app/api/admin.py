"""Endpoints d'action & réglages du dashboard (protégés JWT).

Réutilisent **les mêmes services** que le CLI et les interactions Discord — une
seule source de vérité pour les mutations. Aucune logique métier ici.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.security import get_current_user, require_admin
from app.config import get_setting, invalidate_setting
from app.db import get_db
from app.models import (
    BuyAttempt,
    BuyRule,
    OfferStoreAvailability,
    Release,
    RetailOffer,
    RetailStockEvent,
    Retailer,
    Setting,
    StoreLocation,
    TrackedSet,
    Watchlist,
)
from app.services import jobs as jobs_service
from app.services.interactions import handle_palier_confirm
from app.services.liquidation_service import intake_lot, promote_to_position, segment_lot
from app.services.portfolio import record_deposit

router = APIRouter(tags=["admin"], dependencies=[Depends(get_current_user)])

# Bascule Free → Pro (atomique). Effet au prochain run de job.
_PRO_VALUES = {
    "poketrace_plan": "pro",
    "valuation_market": "EU",
    "valuation_marketplace": "cardmarket",
    "feature_grading_enabled": "true",
    "feature_history_full": "true",
    "poketrace_daily_limit": "10000",
    "poketrace_min_interval_ms": "333",
}
_FREE_VALUES = {
    "poketrace_plan": "free",
    "valuation_market": "US",
    "valuation_marketplace": "tcgplayer",
    "feature_grading_enabled": "false",
    "feature_history_full": "false",
    "poketrace_daily_limit": "250",
    "poketrace_min_interval_ms": "2000",
}


@router.get("/settings")
def list_settings(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "key": s.setting_key, "value": s.setting_value,
            "value_type": s.value_type, "description": s.description,
        }
        for s in db.scalars(select(Setting).order_by(Setting.setting_key)).all()
    ]


class SettingUpdate(BaseModel):
    value: str


@router.put("/settings/{key}", dependencies=[Depends(require_admin)])
def update_setting(key: str, payload: SettingUpdate, db: Session = Depends(get_db)) -> dict:
    setting = db.scalar(select(Setting).where(Setting.setting_key == key))
    if setting is None:
        raise HTTPException(status_code=404, detail="Réglage inconnu")
    setting.setting_value = str(payload.value)
    db.commit()
    invalidate_setting(key)  # le cache get_setting est recalculé à la prochaine lecture
    return {"key": key, "value": setting.setting_value, "value_type": setting.value_type}


class SwitchPro(BaseModel):
    to_pro: bool = True


@router.post("/settings/switch-pro", dependencies=[Depends(require_admin)])
def switch_pro(payload: SwitchPro, db: Session = Depends(get_db)) -> dict:
    values = _PRO_VALUES if payload.to_pro else _FREE_VALUES
    updated = {}
    for key, value in values.items():  # transaction unique
        setting = db.scalar(select(Setting).where(Setting.setting_key == key))
        if setting is None:
            db.add(Setting(setting_key=key, setting_value=value, value_type="string"))
        else:
            setting.setting_value = value
        updated[key] = value
    db.commit()
    invalidate_setting()  # invalide tout le cache
    return {"mode": "pro" if payload.to_pro else "free", "updated": updated,
            "note": "Prend effet au prochain run de job."}


class DepositIn(BaseModel):
    amount: float


@router.post("/deposit")
def deposit(payload: DepositIn, db: Session = Depends(get_db)) -> dict:
    tx = record_deposit(db, payload.amount)
    return {"transaction_id": tx.id, "amount": payload.amount}


class IntakeIn(BaseModel):
    lot_id: int


@router.post("/intake")
def intake(payload: IntakeIn, db: Session = Depends(get_db)) -> dict:
    return intake_lot(db, payload.lot_id)


@router.post("/lots/{lot_id}/segment")
def segment(lot_id: int, db: Session = Depends(get_db)) -> dict:
    return segment_lot(db, lot_id)


@router.post("/lot-items/{item_id}/promote")
def promote(item_id: int, db: Session = Depends(get_db)) -> dict:
    return promote_to_position(db, item_id)


@router.post("/alerts/{alert_id}/confirm")
def confirm_alert(alert_id: int, db: Session = Depends(get_db)) -> dict:
    return handle_palier_confirm(db, alert_id)


# ----------------------------------------------- jobs de pilotage à la demande
def _job_run_dict(r) -> dict:
    return {
        "id": r.id, "job_name": r.job_name, "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "summary": (r.result_json or {}).get("summary") if r.result_json else None,
        "error_text": r.error_text,
    }


@router.post("/admin/jobs/{job_name}/run", dependencies=[Depends(require_admin)])
def run_job(job_name: str, background: BackgroundTasks, db: Session = Depends(get_db)) -> dict:
    """Démarre un job en arrière-plan (réponse immédiate). 409 si déjà en cours."""
    if job_name not in jobs_service.JOBS:
        raise HTTPException(status_code=404, detail="Job inconnu")
    run_id = jobs_service.start_job(db, job_name)
    if run_id is None:
        raise HTTPException(status_code=409, detail="Ce job est déjà en cours")
    background.add_task(jobs_service.execute_job, job_name, run_id)
    return {"job_run_id": run_id, "job_name": job_name, "status": "running"}


@router.get("/admin/jobs/recent", dependencies=[Depends(require_admin)])
def jobs_recent(db: Session = Depends(get_db)) -> dict:
    from app.models import MlModel

    runs = [_job_run_dict(r) for r in jobs_service.recent_runs(db)]
    watchlist_count = db.scalar(
        select(func.count()).select_from(Watchlist).where(Watchlist.is_active == 1)
    ) or 0
    ml = db.scalar(select(MlModel).where(MlModel.name == "release_scorer"))
    ml_model = None
    if ml is not None:
        ml_model = {"n_samples": ml.n_samples, "metrics": ml.metrics,
                    "trained_at": ml.trained_at.isoformat() if ml.trained_at else None}
    return {
        "jobs": list(jobs_service.JOBS),
        "runs": runs,
        "watchlist_count": int(watchlist_count),
        "poketrace_daily_limit": int(float(get_setting("poketrace_daily_limit", default=250))),
        "ml_model": ml_model,
    }


class WatchlistUpdate(BaseModel):
    tier: str | None = None
    keywords: str | None = None
    is_trinity: bool | None = None
    is_illustration_rare: bool | None = None
    is_active: bool | None = None


@router.get("/tracked-sets")
def list_tracked_sets(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "id": t.id, "set_slug": t.set_slug, "name": t.name,
            "is_active": bool(t.is_active), "min_value_eur": float(t.min_value_eur),
            "include_single": bool(t.include_single), "include_sealed": bool(t.include_sealed),
            "included_families": t.included_families,
        }
        for t in db.scalars(select(TrackedSet).order_by(TrackedSet.name)).all()
    ]


class TrackedSetUpdate(BaseModel):
    is_active: bool | None = None
    min_value_eur: float | None = None
    include_single: bool | None = None
    include_sealed: bool | None = None
    name: str | None = None


@router.put("/tracked-sets/{set_id}")
def update_tracked_set(set_id: int, payload: TrackedSetUpdate, db: Session = Depends(get_db)) -> dict:
    ts = db.get(TrackedSet, set_id)
    if ts is None:
        raise HTTPException(status_code=404, detail="Set suivi inconnu")
    if payload.is_active is not None:
        ts.is_active = 1 if payload.is_active else 0
    if payload.min_value_eur is not None:
        ts.min_value_eur = payload.min_value_eur
    if payload.include_single is not None:
        ts.include_single = 1 if payload.include_single else 0
    if payload.include_sealed is not None:
        ts.include_sealed = 1 if payload.include_sealed else 0
    if payload.name is not None:
        ts.name = payload.name
    db.commit()
    return {"id": set_id, "status": "ok"}


class TrackedSetIn(BaseModel):
    set_slug: str
    name: str
    min_value_eur: float = 0.0
    include_single: bool = True
    include_sealed: bool = True


@router.post("/tracked-sets")
def create_tracked_set(payload: TrackedSetIn, db: Session = Depends(get_db)) -> dict:
    slug = (payload.set_slug or "").strip()
    if not slug:
        raise HTTPException(status_code=400, detail="Le slug est requis")
    if payload.min_value_eur < 0:
        raise HTTPException(status_code=400, detail="La valeur min doit être >= 0")
    if db.scalar(select(TrackedSet).where(TrackedSet.set_slug == slug)):
        raise HTTPException(status_code=409, detail="Set déjà suivi")
    ts = TrackedSet(set_slug=slug, name=payload.name or slug, is_active=1,
                    min_value_eur=payload.min_value_eur,
                    include_single=1 if payload.include_single else 0,
                    include_sealed=1 if payload.include_sealed else 0)
    db.add(ts)
    db.commit()
    return {"id": ts.id, "status": "ok"}


@router.delete("/tracked-sets/{set_id}")
def delete_tracked_set(set_id: int, db: Session = Depends(get_db)) -> dict:
    ts = db.get(TrackedSet, set_id)
    if ts is None:
        raise HTTPException(status_code=404, detail="Set suivi inconnu")
    db.delete(ts)
    db.commit()
    return {"id": set_id, "status": "deleted"}


class WatchlistAddIn(BaseModel):
    search: str
    name: str | None = None
    set: str | None = None
    card_number: str | None = None
    language: str | None = None
    product_type: str = "single"
    tier: str = "B"
    is_trinity: bool = False
    is_illustration_rare: bool = False
    keywords: str | None = None


@router.post("/watchlist")
def add_watchlist(payload: WatchlistAddIn, db: Session = Depends(get_db)) -> dict:
    """Création manuelle (recherche PokeTrace + upsert), source='manual'."""
    from app.config import get_setting
    from app.services.catalog_seed import add_manual_watchlist

    res = add_manual_watchlist(
        db, search=payload.search,
        market=str(get_setting("valuation_market", default="US")),
        name=payload.name, set=payload.set, card_number=payload.card_number,
        language=payload.language, product_type=payload.product_type, tier=payload.tier,
        is_trinity=payload.is_trinity, is_illustration_rare=payload.is_illustration_rare,
        keywords=payload.keywords,
    )
    if res["status"] == "empty_search":
        raise HTTPException(status_code=400, detail=res["message"])
    if res["status"] == "not_found":
        raise HTTPException(status_code=404, detail=res["message"])
    return res


@router.put("/watchlist/{product_id}")
def update_watchlist(product_id: int, payload: WatchlistUpdate, db: Session = Depends(get_db)) -> dict:
    """Édition de la watchlist (donnée de config, pas de décision métier)."""
    watch = db.scalar(select(Watchlist).where(Watchlist.product_id == product_id))
    if watch is None:
        raise HTTPException(status_code=404, detail="Produit hors watchlist")
    if payload.tier is not None:
        watch.tier = payload.tier
    if payload.keywords is not None:
        watch.keywords = payload.keywords
    if payload.is_trinity is not None:
        watch.is_trinity = 1 if payload.is_trinity else 0
    if payload.is_illustration_rare is not None:
        watch.is_illustration_rare = 1 if payload.is_illustration_rare else 0
    if payload.is_active is not None:
        watch.is_active = 1 if payload.is_active else 0
    db.commit()
    return {"product_id": product_id, "status": "ok"}


# ===================================================== PokéStock FR (veille restock)
from urllib.parse import urlparse  # noqa: E402

from app.retail import politeness  # noqa: E402
from app.retail.domain import Retailer as RetailerDC  # noqa: E402
from app.retail.fetch import HttpRetailSource, RetailBlocked  # noqa: E402


def _utcnow():
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)


def _retailer_dict(r: Retailer, db: Session) -> dict:
    now = _utcnow()
    # Latence in-pipeline moyenne (détection→alerte) sur les events récents.
    avg_latency = db.scalar(
        select(func.avg(RetailStockEvent.detected_to_alert_ms))
        .select_from(RetailStockEvent).join(RetailOffer, RetailStockEvent.offer_id == RetailOffer.id)
        .where(RetailOffer.retailer_id == r.id, RetailStockEvent.detected_to_alert_ms.is_not(None))
    )
    return {
        "id": r.id, "code": r.code, "name": r.name,
        "base_url": r.base_url, "sitemap_url": r.sitemap_url,
        "availability_endpoint": bool(r.availability_url_template),
        "is_active": bool(r.is_active),
        "enabled": bool(get_setting(f"retail_{r.code}_enabled", default=False)),
        "error_count": politeness.retailer_error_count(db, r.code),
        "circuit_open": politeness.is_retailer_blocked(db, r.code, now),
        "avg_latency_ms": int(avg_latency) if avg_latency is not None else None,
        "offers": db.scalar(
            select(func.count()).select_from(RetailOffer).where(RetailOffer.retailer_id == r.id)
        ) or 0,
    }


@router.get("/retail/retailers")
def list_retailers(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Retailer).order_by(Retailer.name)).all()
    return [_retailer_dict(r, db) for r in rows]


class RetailerUpdate(BaseModel):
    is_active: bool | None = None
    sitemap_url: str | None = None
    availability_url_template: str | None = None
    reset_circuit: bool | None = None


@router.put("/retail/retailers/{retailer_id}", dependencies=[Depends(require_admin)])
def update_retailer(retailer_id: int, payload: RetailerUpdate, db: Session = Depends(get_db)) -> dict:
    r = db.get(Retailer, retailer_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Détaillant inconnu")
    if payload.is_active is not None:
        r.is_active = 1 if payload.is_active else 0
    if payload.sitemap_url is not None:
        r.sitemap_url = payload.sitemap_url.strip() or None
    if payload.availability_url_template is not None:
        r.availability_url_template = payload.availability_url_template.strip() or None
    if payload.reset_circuit:
        politeness.clear_retailer_errors(db, r.code)
    db.commit()
    return _retailer_dict(r, db)


def _offer_dict(o: RetailOffer, retailer_name: str | None = None, flip: dict | None = None) -> dict:
    return {
        "id": o.id, "retailer_id": o.retailer_id, "retailer": retailer_name,
        "url": o.url, "title": o.title, "image_url": o.image_url, "product_type": o.product_type,
        "stock_state": o.current_stock_state,
        "price": float(o.current_price) if o.current_price is not None else None,
        "currency": o.currency, "is_watched": bool(o.is_watched),
        "watch_tier": o.watch_tier, "product_id": o.product_id,
        "last_checked_at": o.last_checked_at.isoformat() if o.last_checked_at else None,
        "last_changed_at": o.last_changed_at.isoformat() if o.last_changed_at else None,
        **(flip or {}),
    }


@router.get("/retail/opportunities")
def retail_opportunities(in_stock: bool = True, db: Session = Depends(get_db)) -> list[dict]:
    """Flip Radar : offres watchées classées par flip net (marché vs MSRP)."""
    from app.services.flip_radar import scan_opportunities

    return scan_opportunities(db, in_stock_only=in_stock)


@router.get("/retail/offers")
def list_offers(watched: bool = True, db: Session = Depends(get_db)) -> list[dict]:
    from app.services.flip_value import flip_for_offer

    names = {r.id: r.name for r in db.scalars(select(Retailer)).all()}
    fx = float(get_setting("fx_usd_eur", default=0.92))
    market = str(get_setting("valuation_market", default="US"))
    stmt = select(RetailOffer)
    if watched:
        stmt = stmt.where(RetailOffer.is_watched == 1)
    stmt = stmt.order_by(RetailOffer.last_changed_at.desc().nullslast(), RetailOffer.id.desc())
    return [_offer_dict(o, names.get(o.retailer_id), flip_for_offer(db, o, fx=fx, market=market))
            for o in db.scalars(stmt).all()]


class OfferWatchUpdate(BaseModel):
    is_watched: bool | None = None
    watch_tier: str | None = None


_TIERS = {"hot", "normal", "cold"}


@router.put("/retail/offers/{offer_id}")
def update_offer(offer_id: int, payload: OfferWatchUpdate, db: Session = Depends(get_db)) -> dict:
    o = db.get(RetailOffer, offer_id)
    if o is None:
        raise HTTPException(status_code=404, detail="Offre inconnue")
    if payload.is_watched is not None:
        o.is_watched = 1 if payload.is_watched else 0
    if payload.watch_tier is not None:
        if payload.watch_tier not in _TIERS:
            raise HTTPException(status_code=400, detail="Tier invalide (hot|normal|cold)")
        o.watch_tier = payload.watch_tier
    db.commit()
    return {"id": offer_id, "is_watched": bool(o.is_watched), "watch_tier": o.watch_tier, "status": "ok"}


@router.post("/retail/offers/{offer_id}/recheck")
def recheck_offer_now(offer_id: int, background: BackgroundTasks,
                      db: Session = Depends(get_db)) -> dict:
    """Déclencheur de re-check immédiat (manuel/communautaire), hors cadence tier."""
    from app.services.retail_jobs import recheck_offer

    return recheck_offer(db, offer_id)


# --------------------------------------------------- Phase B : magasins
@router.get("/retail/stores")
def list_stores(db: Session = Depends(get_db)) -> list[dict]:
    names = {r.id: r.name for r in db.scalars(select(Retailer)).all()}
    rows = db.scalars(select(StoreLocation).order_by(StoreLocation.retailer_id, StoreLocation.name)).all()
    return [{
        "id": s.id, "retailer_id": s.retailer_id, "retailer": names.get(s.retailer_id),
        "store_code": s.store_code, "name": s.name, "city": s.city, "postal": s.postal,
        "is_watched": bool(s.is_watched),
    } for s in rows]


class StoreUpdate(BaseModel):
    is_watched: bool


@router.put("/retail/stores/{store_id}")
def update_store(store_id: int, payload: StoreUpdate, db: Session = Depends(get_db)) -> dict:
    s = db.get(StoreLocation, store_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Magasin inconnu")
    s.is_watched = 1 if payload.is_watched else 0
    db.commit()
    return {"id": store_id, "is_watched": bool(s.is_watched), "status": "ok"}


# --------------------------------------------------- Phase C : achat assisté
def _rule_dict(r: BuyRule) -> dict:
    return {
        "id": r.id, "scope": r.scope, "scope_value": r.scope_value,
        "retailer_id": r.retailer_id, "max_price": float(r.max_price),
        "max_quantity": r.max_quantity, "is_enabled": bool(r.is_enabled),
    }


@router.get("/buy-rules")
def list_buy_rules(db: Session = Depends(get_db)) -> list[dict]:
    return [_rule_dict(r) for r in db.scalars(select(BuyRule).order_by(BuyRule.id.desc())).all()]


class BuyRuleIn(BaseModel):
    scope: str = "offer"
    scope_value: str
    retailer_id: int | None = None
    max_price: float
    max_quantity: int = 1
    is_enabled: bool = False


@router.post("/buy-rules")
def create_buy_rule(payload: BuyRuleIn, db: Session = Depends(get_db)) -> dict:
    if payload.scope not in ("offer", "product_type"):
        raise HTTPException(status_code=400, detail="scope invalide (offer|product_type)")
    if payload.max_price <= 0 or payload.max_quantity < 1:
        raise HTTPException(status_code=400, detail="Plafond prix > 0 et quantité ≥ 1 requis")
    r = BuyRule(scope=payload.scope, scope_value=str(payload.scope_value).strip(),
                retailer_id=payload.retailer_id, max_price=payload.max_price,
                max_quantity=payload.max_quantity, is_enabled=1 if payload.is_enabled else 0)
    db.add(r)
    db.commit()
    return _rule_dict(r)


class BuyRuleUpdate(BaseModel):
    max_price: float | None = None
    max_quantity: int | None = None
    is_enabled: bool | None = None


@router.put("/buy-rules/{rule_id}")
def update_buy_rule(rule_id: int, payload: BuyRuleUpdate, db: Session = Depends(get_db)) -> dict:
    r = db.get(BuyRule, rule_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Règle inconnue")
    if payload.max_price is not None:
        if payload.max_price <= 0:
            raise HTTPException(status_code=400, detail="Plafond prix > 0 requis")
        r.max_price = payload.max_price
    if payload.max_quantity is not None:
        r.max_quantity = max(1, payload.max_quantity)
    if payload.is_enabled is not None:
        r.is_enabled = 1 if payload.is_enabled else 0
    db.commit()
    return _rule_dict(r)


@router.delete("/buy-rules/{rule_id}")
def delete_buy_rule(rule_id: int, db: Session = Depends(get_db)) -> dict:
    r = db.get(BuyRule, rule_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Règle inconnue")
    db.delete(r)
    db.commit()
    return {"id": rule_id, "status": "deleted"}


@router.get("/buy-attempts")
def list_buy_attempts(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(BuyAttempt).order_by(BuyAttempt.id.desc()).limit(100)).all()
    return [{
        "id": a.id, "offer_id": a.offer_id, "channel": a.channel, "status": a.status,
        "cart_url": a.cart_url, "reason": a.reason,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in rows]


@router.post("/retail/offers/{offer_id}/buy")
def assisted_buy_now(offer_id: int, db: Session = Depends(get_db)) -> dict:
    """Déclenche l'achat ASSISTÉ d'une offre (allow-list + garde-fous). Jamais de paiement."""
    from app.services.assisted_buy import attempt_buy

    offer = db.get(RetailOffer, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offre inconnue")
    retailer = db.get(Retailer, offer.retailer_id)
    return attempt_buy(db, offer=offer, retailer=retailer)


@router.get("/retail/store-availability")
def store_availability(offer_id: int | None = None, db: Session = Depends(get_db)) -> list[dict]:
    """Dispo par (offre, magasin) — vue de l'écran magasins."""
    stores = {s.id: s for s in db.scalars(select(StoreLocation)).all()}
    offers = {o.id: o for o in db.scalars(select(RetailOffer)).all()}
    stmt = select(OfferStoreAvailability)
    if offer_id is not None:
        stmt = stmt.where(OfferStoreAvailability.offer_id == offer_id)
    out = []
    for a in db.scalars(stmt.order_by(OfferStoreAvailability.last_changed_at.desc().nullslast())).all():
        st = stores.get(a.store_id)
        of = offers.get(a.offer_id)
        out.append({
            "offer_id": a.offer_id, "store_id": a.store_id,
            "title": of.title if of else None,
            "store": st.name if st else None, "city": st.city if st else None,
            "availability_state": a.availability_state,
            "price": float(a.price) if a.price is not None else None,
            "last_changed_at": a.last_changed_at.isoformat() if a.last_changed_at else None,
        })
    return out


@router.delete("/retail/offers/{offer_id}")
def delete_offer(offer_id: int, db: Session = Depends(get_db)) -> dict:
    o = db.get(RetailOffer, offer_id)
    if o is None:
        raise HTTPException(status_code=404, detail="Offre inconnue")
    db.delete(o)
    db.commit()
    return {"id": offer_id, "status": "deleted"}


class OfferAddIn(BaseModel):
    url: str
    retailer_code: str | None = None


def _match_retailer(db: Session, url: str, code: str | None) -> Retailer | None:
    if code:
        return db.scalar(select(Retailer).where(Retailer.code == code))
    host = (urlparse(url).hostname or "").lower()
    for r in db.scalars(select(Retailer)).all():
        rhost = (urlparse(r.base_url or "").hostname or "").lower()
        if rhost and (rhost in host or host in rhost):
            return r
    return None


@router.post("/retail/offers")
def add_offer(payload: OfferAddIn, db: Session = Depends(get_db)) -> dict:
    """Ajoute une offre à la veille par URL (fetch best-effort immédiat, non bloquant)."""
    url = (payload.url or "").strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL invalide")
    retailer = _match_retailer(db, url, payload.retailer_code)
    if retailer is None:
        raise HTTPException(status_code=400, detail="Détaillant introuvable pour cette URL (préciser retailer_code)")
    existing = db.scalar(select(RetailOffer).where(RetailOffer.url == url))
    if existing is not None:
        existing.is_watched = 1
        db.commit()
        return {"id": existing.id, "status": "already_exists", "watched": True}

    offer = RetailOffer(retailer_id=retailer.id, url=url[:512],
                        current_stock_state="unknown", is_watched=1)
    db.add(offer)
    db.flush()
    # Fetch best-effort : ne casse jamais l'ajout (politesse : un seul GET).
    note = "ajoutée (état à rafraîchir par le job)"
    try:
        source = HttpRetailSource(RetailerDC(retailer.code, retailer.name, retailer.base_url))
        snap = source.fetch_offer(url)
        offer.current_stock_state = snap.stock_state
        if snap.price is not None:
            offer.current_price = snap.price
        if snap.title:
            offer.title = snap.title[:255]
        if snap.image:
            offer.image_url = snap.image[:512]
        offer.last_checked_at = _utcnow()
        if snap.stock_state in ("in_stock", "preorder", "out_of_stock"):
            db.add(RetailStockEvent(offer_id=offer.id, from_state="unknown",
                                    to_state=snap.stock_state, price=snap.price,
                                    detected_at=_utcnow()))
        note = f"ajoutée (état {snap.stock_state})"
    except RetailBlocked:
        note = "ajoutée (détaillant a bloqué le fetch immédiat)"
    except Exception:  # noqa: BLE001
        note = "ajoutée (fetch immédiat indisponible)"
    db.commit()
    return {"id": offer.id, "status": "ok", "stock_state": offer.current_stock_state, "note": note}


# --------------------------------------------------------------- deal analyzer
class AnalyzeIn(BaseModel):
    url: str


@router.post("/retail/analyze")
def analyze_deal(payload: AnalyzeIn, db: Session = Depends(get_db)) -> dict:
    """Note une annonce (prix annoncé vs prix marché PokeTrace) → verdict."""
    from app.services.deal_analyzer import analyze_listing

    result = analyze_listing(db, payload.url)
    if result.get("status") == "invalid_url":
        raise HTTPException(status_code=400, detail=result.get("message", "URL invalide"))
    return result


# --------------------------------------------------------------- releases (calendrier)
def _release_dict(r: Release, db: Session) -> dict:
    """Scores : modèle ML s'il est entraîné, sinon repli sur l'heuristique."""
    from app.ml.scorer import score_release_ml
    from app.services.release_scoring import score_release

    scores = score_release_ml(db, r) or score_release(r)
    return {
        "id": r.id, "set_name": r.set_name, "product_name": r.product_name,
        "product_type": r.product_type,
        "release_date": r.release_date.isoformat() if r.release_date else None,
        "preorder_date": r.preorder_date.isoformat() if r.preorder_date else None,
        "source_note": r.source_note,
        "scores": scores,
    }


@router.get("/releases")
def list_releases(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Release).order_by(Release.release_date.asc().nullslast())).all()
    return [_release_dict(r, db) for r in rows]


class ReleaseIn(BaseModel):
    product_name: str
    set_name: str | None = None
    product_type: str | None = None
    release_date: str | None = None
    preorder_date: str | None = None
    source_note: str | None = None


def _parse_date(value: str | None):
    import datetime as _dt

    if not value:
        return None
    try:
        return _dt.date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Date invalide (AAAA-MM-JJ)") from exc


@router.post("/releases", dependencies=[Depends(require_admin)])
def create_release(payload: ReleaseIn, db: Session = Depends(get_db)) -> dict:
    if not (payload.product_name or "").strip():
        raise HTTPException(status_code=400, detail="Le nom du produit est requis")
    r = Release(
        product_name=payload.product_name.strip(),
        set_name=payload.set_name, product_type=payload.product_type,
        release_date=_parse_date(payload.release_date),
        preorder_date=_parse_date(payload.preorder_date),
        source_note=payload.source_note,
    )
    db.add(r)
    db.commit()
    return _release_dict(r, db)


@router.put("/releases/{release_id}", dependencies=[Depends(require_admin)])
def update_release(release_id: int, payload: ReleaseIn, db: Session = Depends(get_db)) -> dict:
    r = db.get(Release, release_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Sortie inconnue")
    r.product_name = payload.product_name.strip() or r.product_name
    r.set_name = payload.set_name
    r.product_type = payload.product_type
    r.release_date = _parse_date(payload.release_date)
    r.preorder_date = _parse_date(payload.preorder_date)
    r.source_note = payload.source_note
    db.commit()
    return _release_dict(r, db)


@router.delete("/releases/{release_id}", dependencies=[Depends(require_admin)])
def delete_release(release_id: int, db: Session = Depends(get_db)) -> dict:
    r = db.get(Release, release_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Sortie inconnue")
    db.delete(r)
    db.commit()
    return {"id": release_id, "status": "deleted"}
