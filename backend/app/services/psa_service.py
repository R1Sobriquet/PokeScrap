"""Service PSA : vérifie un certificat et l'upsert dans ``psa_certs``.

Appelé à la demande (sourcing/grading, jalons 6-7), jamais en boucle au Jalon 2.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.ports import CertProvider
from app.adapters.psa import PSACertProvider
from app.models import PsaCert

logger = logging.getLogger("services.psa")


def verify_and_persist_cert(
    db: Session,
    cert_number: str,
    *,
    provider: CertProvider | None = None,
) -> PsaCert:
    """Vérifie un cert via l'adapter PSA et upsert la ligne ``psa_certs``."""
    provider = provider or PSACertProvider()
    data = provider.verify_cert(cert_number)

    cert = db.scalar(select(PsaCert).where(PsaCert.cert_number == cert_number))
    if cert is None:
        cert = PsaCert(cert_number=cert_number)
        db.add(cert)

    cert.grade = data.get("grade")
    cert.grade_label = data.get("grade_label")
    cert.is_valid = 1 if data.get("is_valid") else 0
    cert.pop_data = data.get("pop_data")
    cert.raw_response = data.get("raw")
    cert.verified_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    db.commit()
    logger.info("Cert %s vérifié (grade=%s).", cert_number, cert.grade)
    return cert
