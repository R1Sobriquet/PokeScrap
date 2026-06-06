#!/usr/bin/env python3
"""Smoke-test réel de l'adapter PSA (Tâche 0 Jalon 7).

  * Si des creds PSA sont présents (.env : ``PSA_API_TOKEN`` **ou**
    ``PSA_API_USERNAME``/``PSA_API_PASSWORD``) : appelle ``verify_cert`` sur un
    numéro connu (``PSA_SMOKE_CERT``, défaut fourni) et imprime
    « champ API → colonne psa_certs ».
  * Sinon : skip propre (exit 0).

Usage : ``python scripts/smoke_psa.py``
"""

from __future__ import annotations

import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:  # pragma: no cover
    pass


def main() -> int:
    token = os.getenv("PSA_API_TOKEN", "").strip()
    user = os.getenv("PSA_API_USERNAME", "").strip()
    password = os.getenv("PSA_API_PASSWORD", "").strip()
    if not token and not (user and password):
        print("[skip] Creds PSA absents (PSA_API_TOKEN ou USERNAME/PASSWORD) — smoke-test ignoré.")
        return 0

    base_url = os.getenv("PSA_BASE_URL", "https://api.psacard.com/publicapi")
    cert_number = os.getenv("PSA_SMOKE_CERT", "49543631")  # numéro public d'exemple

    from app.adapters.psa import PSAClient, PSACertProvider

    client = PSAClient(base_url, user, password, token=token)
    provider = PSACertProvider(client=client)

    print(f"[1/1] GET {base_url}/cert/GetByCertNumber/{cert_number}")
    parsed = provider.verify_cert(cert_number)

    mapping = [
        ("CardGrade/Grade", "grade", parsed.get("grade")),
        ("GradeDescription", "grade_label", parsed.get("grade_label")),
        ("IsValid", "is_valid", parsed.get("is_valid")),
        ("TotalPopulation/…", "pop_data", parsed.get("pop_data")),
    ]
    width = max(len(a) for a, _, _ in mapping)
    print(f"{'champ API':<{width}}  →  {'colonne psa_certs':<18}  valeur")
    print("-" * (width + 40))
    for api_field, col, value in mapping:
        print(f"{api_field:<{width}}  →  {col:<18}  {value!r}")

    assert "grade" in parsed and "is_valid" in parsed, "forme de réponse inattendue"
    print("\n[OK] verify_cert a renvoyé une forme exploitable par psa_certs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
