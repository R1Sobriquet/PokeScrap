"""Endpoints d'action & réglages du dashboard (protégés JWT).

Réutilisent **les mêmes services** que le CLI et les interactions Discord — une
seule source de vérité pour les mutations. Aucune logique métier ici.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.security import get_current_user
from app.config import get_setting, invalidate_setting
from app.db import get_db
from app.models import Setting, TrackedSet, Watchlist
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


@router.put("/settings/{key}")
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


@router.post("/settings/switch-pro")
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


@router.post("/admin/jobs/{job_name}/run")
def run_job(job_name: str, background: BackgroundTasks, db: Session = Depends(get_db)) -> dict:
    """Démarre un job en arrière-plan (réponse immédiate). 409 si déjà en cours."""
    if job_name not in jobs_service.JOBS:
        raise HTTPException(status_code=404, detail="Job inconnu")
    run_id = jobs_service.start_job(db, job_name)
    if run_id is None:
        raise HTTPException(status_code=409, detail="Ce job est déjà en cours")
    background.add_task(jobs_service.execute_job, job_name, run_id)
    return {"job_run_id": run_id, "job_name": job_name, "status": "running"}


@router.get("/admin/jobs/recent")
def jobs_recent(db: Session = Depends(get_db)) -> dict:
    runs = [_job_run_dict(r) for r in jobs_service.recent_runs(db)]
    watchlist_count = db.scalar(
        select(func.count()).select_from(Watchlist).where(Watchlist.is_active == 1)
    ) or 0
    return {
        "jobs": list(jobs_service.JOBS),
        "runs": runs,
        "watchlist_count": int(watchlist_count),
        "poketrace_daily_limit": int(float(get_setting("poketrace_daily_limit", default=250))),
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
