"""Jobs de pilotage à la demande — registre + exécution avec état (``job_runs``).

Une SEULE source de vérité : le CLI (``app.cli``) et les endpoints REST appellent
les mêmes runners ``JOBS[name](db) -> dict``. Exécution en arrière-plan possible
(``execute_job`` ouvre sa propre session), avec garde anti-concurrence (un seul
run ``running`` par job).
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import JobRun
from app.services.ingestion import ingest_watchlist_prices
from app.services.kpi_snapshot import run_kpi_snapshot
from app.services.movers import compute_top_movers
from app.services.retail_jobs import (
    run_backfill_images,
    run_check_restocks,
    run_detect_new_skus,
    run_refresh_prices,
)
from app.services.runtime_settings import ensure_runtime_settings
from app.services.selling_service import evaluate_position_sales
from app.services.tracked_sets import ensure_default_tracked_sets, sync_tracked_sets

logger = logging.getLogger("services.jobs")

RUNNING, DONE, ERROR = "running", "done", "error"


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


# ------------------------------------------------------------------ runners
def _run_sync_tracked_sets(db: Session) -> dict:
    ensure_default_tracked_sets(db)
    s = sync_tracked_sets(db)
    rej = s.get("rejected", {})
    s["summary"] = (f"{s.get('added', 0)} ajoutés / {rej.get('sous_min_value', 0)} sous le seuil "
                    f"/ {s.get('received', 0)} reçus")
    return s


def _run_refresh_prices(db: Session) -> dict:
    n = ingest_watchlist_prices(db)
    return {"snapshots": n, "summary": f"{n} snapshots écrits"}


def _run_scan_movers(db: Session) -> dict:
    movers = compute_top_movers(db)
    return {"top_movers": len(movers), "movers": movers[:10], "summary": f"{len(movers)} top movers"}


def _run_evaluate_sales(db: Session) -> dict:
    r = evaluate_position_sales(db)
    r["summary"] = f"{r.get('sell', 0)} alertes vente / {r.get('reminder', 0)} rappels"
    return r


def _run_kpi_snapshot(db: Session) -> dict:
    r = run_kpi_snapshot(db)
    r["summary"] = f"snapshot {r.get('snapshot_date', '?')}"
    return r


def _run_train_release_model(db: Session) -> dict:
    from app.ml.scorer import run_train_release_model

    return run_train_release_model(db)


def _run_market_snapshot(db: Session) -> dict:
    from app.services.market_snapshot import run_market_snapshot

    return run_market_snapshot(db)


def _run_calendar_sync(db: Session) -> dict:
    from app.services.calendar_sync import run_calendar_sync

    return run_calendar_sync(db)


def _run_match_products(db: Session) -> dict:
    from app.services.product_matching import run_match_products

    return run_match_products(db)


def _run_source_health_check(db: Session) -> dict:
    from app.services.source_health import check_sources

    return check_sources(db)


def _run_flip_radar(db: Session) -> dict:
    from app.services.flip_radar import run_flip_radar

    return run_flip_radar(db)


def _run_check_store_stock(db: Session) -> dict:
    from app.services.retail_store_jobs import run_check_store_stock

    return run_check_store_stock(db)


def _run_marketwatch_sync_registry(db: Session) -> dict:
    from app.marketwatch.registry import sync_registry

    return sync_registry(db)


def _run_marketwatch_ingest(db: Session) -> dict:
    from app.services.marketwatch_ingest import run_ingest

    return run_ingest(db)


def _run_marketwatch_score(db: Session) -> dict:
    from app.services.marketwatch_score import run_score

    return run_score(db)


def _run_marketwatch_digest(db: Session) -> dict:
    from app.services.marketwatch_digest import run_digest

    return run_digest(db, dry_run=False)


JOBS = {
    "sync-tracked-sets": _run_sync_tracked_sets,
    "refresh-prices": _run_refresh_prices,
    "scan-movers": _run_scan_movers,
    "evaluate-sales": _run_evaluate_sales,
    "kpi-snapshot": _run_kpi_snapshot,
    # PokéStock FR — veille restock (réutilisent job_runs + le panel)
    "retail-check-restocks": run_check_restocks,
    "retail-detect-new-skus": run_detect_new_skus,
    "retail-refresh-prices": run_refresh_prices,
    "retail-backfill-images": run_backfill_images,
    # Future Radar — (ré)entraînement du modèle ML de scoring des sorties.
    "train-release-model": _run_train_release_model,
    # Moat de données marché — snapshots, calendrier, matching, moniteur santé.
    "market-snapshot-daily": _run_market_snapshot,
    "calendar-sync": _run_calendar_sync,
    "match-products": _run_match_products,
    "source-health-check": _run_source_health_check,
    "flip-radar-scan": _run_flip_radar,
    "retail-check-store-stock": _run_check_store_stock,
    # Market Intelligence — registre TCGdex, ingestion, signaux, digest hebdo.
    "marketwatch-sync-registry": _run_marketwatch_sync_registry,
    "marketwatch-ingest": _run_marketwatch_ingest,
    "marketwatch-score": _run_marketwatch_score,
    "marketwatch-digest": _run_marketwatch_digest,
}


# ------------------------------------------------------------------- état
def is_running(db: Session, job_name: str) -> bool:
    return db.scalar(
        select(JobRun.id).where(JobRun.job_name == job_name, JobRun.status == RUNNING)
    ) is not None


def start_job(db: Session, job_name: str) -> int | None:
    """Crée un run ``running`` ; renvoie son id, ou ``None`` si déjà en cours."""
    if job_name not in JOBS:
        raise KeyError(job_name)
    if is_running(db, job_name):
        return None
    run = JobRun(job_name=job_name, status=RUNNING, started_at=_utcnow())
    db.add(run)
    db.commit()
    return run.id


def execute_job(job_name: str, run_id: int) -> None:
    """Exécute le runner (session propre) et met à jour l'état du run."""
    from app.db import SessionLocal  # résolu à l'appel (respecte le patch de test)

    try:
        with SessionLocal() as db:
            ensure_runtime_settings(db)
            result = JOBS[job_name](db)
            run = db.get(JobRun, run_id)
            if run is not None:
                run.status = DONE
                run.finished_at = _utcnow()
                run.result_json = result
                db.commit()
        logger.info("job '%s' terminé : %s", job_name, (result or {}).get("summary"))
    except Exception as exc:  # noqa: BLE001 - on isole et on persiste l'erreur
        logger.exception("job '%s' en échec", job_name)
        with SessionLocal() as db:
            run = db.get(JobRun, run_id)
            if run is not None:
                run.status = ERROR
                run.finished_at = _utcnow()
                run.error_text = str(exc)[:2000]
                db.commit()


def run_job_sync(db: Session, job_name: str) -> dict:
    """Variante synchrone pour le CLI : exécute et renvoie le résumé."""
    if job_name not in JOBS:
        raise KeyError(job_name)
    ensure_runtime_settings(db)
    return JOBS[job_name](db)


def recent_runs(db: Session, *, limit: int = 25) -> list[JobRun]:
    return list(db.scalars(select(JobRun).order_by(JobRun.id.desc()).limit(limit)).all())
