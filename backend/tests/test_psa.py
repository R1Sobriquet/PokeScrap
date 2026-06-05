"""Tests adapter PSA : parsing, OAuth/token cache, upsert psa_certs."""

from __future__ import annotations

import httpx
from sqlalchemy import func, select

from app.adapters.psa import PSACertProvider, PSAClient, parse_cert
from app.models import PsaCert
from app.services.psa_service import verify_and_persist_cert
from tests.fakes import FakeCertProvider

RAW_CERT = {
    "cert_number": "12345678",
    "grade": "10",
    "grade_label": "GEM MT 10",
    "is_valid": True,
    "pop_data": {"psa10": 1234, "psa9": 5678},
}


def test_parse_cert():
    parsed = parse_cert(RAW_CERT)
    assert parsed["grade"] == "10"
    assert parsed["grade_label"] == "GEM MT 10"
    assert parsed["is_valid"] is True
    assert parsed["pop_data"] == {"psa10": 1234, "psa9": 5678}
    assert parsed["raw"] == RAW_CERT


def test_verify_and_persist_upserts(db_session):
    provider = FakeCertProvider(parse_cert(RAW_CERT))

    verify_and_persist_cert(db_session, "12345678", provider=provider)
    cert = db_session.scalar(select(PsaCert).where(PsaCert.cert_number == "12345678"))
    assert cert.grade == "10"
    assert cert.is_valid == 1
    assert cert.pop_data == {"psa10": 1234, "psa9": 5678}
    assert cert.verified_at is not None

    # Réexécution → upsert, pas de doublon.
    verify_and_persist_cert(db_session, "12345678", provider=provider)
    count = db_session.scalar(select(func.count()).select_from(PsaCert))
    assert count == 1


def test_psa_client_oauth_and_token_cache():
    token_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/token"):
            token_calls["n"] += 1
            return httpx.Response(200, json={"access_token": "tok-123", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer tok-123"
        return httpx.Response(200, json=RAW_CERT)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = PSAClient("http://psa.test/publicapi", "user", "pass", http_client=http)
    provider = PSACertProvider(client=client)

    first = provider.verify_cert("12345678")
    second = provider.verify_cert("12345678")

    assert first["grade"] == "10"
    assert second["grade"] == "10"
    assert token_calls["n"] == 1  # token mis en cache, un seul échange OAuth
