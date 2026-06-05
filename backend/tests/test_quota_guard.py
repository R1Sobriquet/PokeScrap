"""Tests du garde-quota et du throttle de burst du client PokeTrace."""

from __future__ import annotations

import datetime as dt

import httpx
import pytest

from app.adapters.poketrace import PokeTraceClient, QuotaExceeded


def _client(handler, **kwargs):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    defaults = dict(daily_limit=1000, min_interval_ms=0, http_client=http)
    defaults.update(kwargs)
    return PokeTraceClient("http://api.test/v1", "key", **defaults)


def _ok(request):
    return httpx.Response(200, json={"ok": True})


def test_daily_limit_blocks():
    client = _client(_ok, daily_limit=2)
    client.get("/a")
    client.get("/b")
    with pytest.raises(QuotaExceeded):
        client.get("/c")
    assert client.requests_today == 2


def test_quota_resets_next_day():
    day = [dt.datetime(2026, 6, 5, tzinfo=dt.timezone.utc)]
    client = _client(_ok, daily_limit=1, now=lambda: day[0])
    client.get("/a")
    with pytest.raises(QuotaExceeded):
        client.get("/b")
    day[0] = dt.datetime(2026, 6, 6, tzinfo=dt.timezone.utc)  # nouveau jour UTC
    client.get("/c")  # le compteur est réinitialisé
    assert client.requests_today == 1


def test_burst_interval_throttles():
    clock = [0.0]
    sleeps: list[float] = []

    def mono() -> float:
        return clock[0]

    def slp(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    client = _client(_ok, min_interval_ms=2000, monotonic=mono, sleep=slp)
    client.get("/a")  # premier appel : pas d'attente
    client.get("/b")  # second : doit attendre ~2s

    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(2.0)


def test_429_triggers_backoff_then_succeeds():
    calls = {"n": 0}
    sleeps: list[float] = []

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"ok": True})

    client = _client(handler, sleep=lambda s: sleeps.append(s))
    result = client.get("/a")
    assert result == {"ok": True}
    assert calls["n"] == 2
    assert sleeps  # un backoff a eu lieu
