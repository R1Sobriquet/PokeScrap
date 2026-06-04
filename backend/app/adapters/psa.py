"""Adapter PSA (CertProvider) — STUB Jalon 1."""

from __future__ import annotations

from typing import Any

from app.adapters.ports import CertProvider


class PSACertProvider(CertProvider):
    def get_cert(self, cert_number: str, **kwargs: Any) -> Any:
        raise NotImplementedError("jalon 2")
