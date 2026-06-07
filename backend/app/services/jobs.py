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


JOBS = {
    "sync-tracked-sets": _run_sync_tracked_sets,
    "refresh-prices": _run_refresh_prices,
    "scan-movers": _run_scan_movers,
    "evaluate-sales": _run_evaluate_sales,
    "kpi-snapshot": _run_kpi_snapshot,
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
