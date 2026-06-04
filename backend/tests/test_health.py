"""Test de l'endpoint /health (connexion DB)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_ok(sqlite_engine):
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
