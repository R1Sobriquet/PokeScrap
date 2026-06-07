"""Tests des jobs à la demande : run (running→done), concurrence, recent."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.security import hash_password
from app.config import get_settings
from app.main import app
from app.models import JobRun, Setting


@pytest.fixture()
def client(sqlite_engine, db_session):
    s = get_settings()
    db_session.add(Setting(setting_key="admin_password_hash",
                           setting_value=hash_password(s.admin_password), value_type="string"))
    db_session.commit()
    c = TestClient(app)
    token = c.post("/auth/login", json={"username": s.admin_username,
                                        "password": s.admin_password}).json()["access_token"]
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


def test_run_creates_job_then_done(client, db_session):
    # scan-movers tourne sur une base vide (watchlist vide → []), sans réseau.
    r = client.post("/admin/jobs/scan-movers/run")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
    assert body["job_run_id"]

    # BackgroundTasks exécuté par le TestClient → le run doit être 'done'.
    run = db_session.get(JobRun, body["job_run_id"])
    db_session.refresh(run)
    assert run.status == "done"
    assert run.finished_at is not None
    assert run.result_json and "summary" in run.result_json


def test_concurrent_run_refused(client, db_session):
    # Un run 'running' déjà présent → 409 poli.
    db_session.add(JobRun(job_name="refresh-prices", status="running",
                          started_at=dt.datetime(2026, 6, 5, 12, 0, 0)))
    db_session.commit()
    r = client.post("/admin/jobs/refresh-prices/run")
    assert r.status_code == 409


def test_unknown_job_404(client):
    assert client.post("/admin/jobs/does-not-exist/run").status_code == 404


def test_recent_returns_statuses_and_watchlist_count(client, db_session):
    db_session.add(JobRun(job_name="kpi-snapshot", status="done",
                          started_at=dt.datetime(2026, 6, 5, 11, 0, 0),
                          finished_at=dt.datetime(2026, 6, 5, 11, 1, 0),
                          result_json={"summary": "snapshot 2026-06-05"}))
    db_session.commit()

    body = client.get("/admin/jobs/recent").json()
    assert "sync-tracked-sets" in body["jobs"]
    assert any(run["job_name"] == "kpi-snapshot" and run["status"] == "done" for run in body["runs"])
    assert body["runs"][0]["summary"] is not None
    assert "watchlist_count" in body and "poketrace_daily_limit" in body


def test_run_without_token_401(sqlite_engine):
    assert TestClient(app).post("/admin/jobs/scan-movers/run").status_code == 401
