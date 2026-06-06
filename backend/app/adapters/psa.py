"""Adapter PSA (``CertProvider``) — vérification d'authenticité (gratuite).

Auth (cf. docs/jalon7_preflight.md) : la PSA Public API réelle utilise un **token
statique** d'API (généré dans le compte), passé en ``Authorization: Bearer``. On
le supporte via ``PSA_API_TOKEN``. Le flux *OAuth2 password grant* (spec Jalon 2)
reste en repli si seuls username/password sont fournis.

Endpoint réel : ``GET {base}/cert/GetByCertNumber/{cert}`` → objet ``PSACert``
(champs PascalCase : ``CertNumber``, ``CardGrade``, ``GradeDescription``,
``IsValid``, ``TotalPopulation``, ``PopulationHigher``, ``SpecID``…).
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Callable

import httpx

from app.adapters.ports import CertProvider
from app.config import get_settings

logger = logging.getLogger("adapters.psa")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class PSAClient:
    """Client HTTP PSA : token statique (réel) ou password grant (repli)."""

    def __init__(
        self,
        base_url: str,
        username: str = "",
        password: str = "",
        *,
        token: str = "",
        http_client: httpx.Client | None = None,
        now: Callable[[], dt.datetime] = _utcnow,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._static_token = token
        self._http = http_client or httpx.Client(timeout=20.0)
        self._now = now
        self._token: str | None = None
        self._expires_at: dt.datetime | None = None

    def _ensure_token(self) -> str:
        # Cas réel : token statique d'API, aucun échange nécessaire.
        if self._static_token:
            return self._static_token
        # Repli (spec Jalon 2) : OAuth2 password grant, mis en cache.
        if self._token and self._expires_at and self._now() < self._expires_at:
            return self._token
        resp = self._http.post(
            f"{self._base}/oauth/token",
            data={
                "grant_type": "password",
                "username": self._username,
                "password": self._password,
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        ttl = int(payload.get("expires_in", 3600)) - 60  # marge anti-expiration
        self._expires_at = self._now() + dt.timedelta(seconds=max(ttl, 0))
        return self._token

    def get_cert(self, cert_number: str) -> dict[str, Any]:
        token = self._ensure_token()
        resp = self._http.get(
            f"{self._base}/cert/GetByCertNumber/{cert_number}",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()


def parse_cert(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalise une réponse cert PSA (PascalCase réel + repli minuscules)."""
    cert = raw.get("PSACert") or raw.get("cert") or raw
    grade = cert.get("grade") or cert.get("CardGrade") or cert.get("Grade")
    grade_label = cert.get("grade_label") or cert.get("GradeDescription") or cert.get("gradeLabel")

    is_valid = cert.get("is_valid")
    if is_valid is None:
        is_valid = cert.get("IsValid")
    if is_valid is None:
        is_valid = bool(grade)

    pop_data = cert.get("pop_data") or cert.get("popData") or cert.get("population")
    if pop_data is None:
        pop_fields = {
            k: cert[k]
            for k in ("TotalPopulation", "PopulationHigher", "SpecID", "SpecNumber")
            if k in cert
        }
        pop_data = pop_fields or None

    return {
        "grade": str(grade) if grade is not None else None,
        "grade_label": grade_label,
        "is_valid": bool(is_valid),
        "pop_data": pop_data,
        "raw": raw,
    }


class PSACertProvider(CertProvider):
    """Implémentation ``CertProvider`` adossée à ``PSAClient``."""

    def __init__(self, client: PSAClient | None = None) -> None:
        if client is None:
            settings = get_settings()
            client = PSAClient(
                settings.psa_base_url,
                settings.psa_api_username,
                settings.psa_api_password,
                token=settings.psa_api_token,
            )
        self._client = client

    def verify_cert(self, cert_number: str) -> dict[str, Any]:
        raw = self._client.get_cert(cert_number)
        return parse_cert(raw)
