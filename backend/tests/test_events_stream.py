"""Tests du flux SSE /events/stream (auth + instantané + refus sans token)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.security import create_access_token
from app.main import app


def test_stream_requires_valid_token(sqlite_engine):
    client = TestClient(app)
    r = client.get("/events/stream", params={"token": "bidon", "once": True})
    assert r.status_code == 401


def test_stream_emits_hello_snapshot(sqlite_engine):
    token = create_access_token("erwann")
    client = TestClient(app)
    r = client.get("/events/stream", params={"token": token, "once": True})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "event: hello" in r.text
    assert "data:" in r.text
