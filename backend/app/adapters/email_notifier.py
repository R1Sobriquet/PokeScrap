"""Envoi d'emails transactionnels (vérification de compte, reset password).

SMTP configuré par ``.env`` (``SMTP_HOST/PORT/USER/PASSWORD/FROM``). Sans
``SMTP_HOST`` (dev/tests), repli **console** : le contenu est loggé — le jeton
reste utilisable en copiant le lien depuis les logs. Jamais bloquant : une
erreur SMTP est loggée, l'appelant décide quoi faire (l'inscription n'échoue pas).
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("adapters.email")


def _smtp_conf() -> dict:
    return {
        "host": os.getenv("SMTP_HOST", ""),
        "port": int(os.getenv("SMTP_PORT", "587") or 587),
        "user": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "sender": os.getenv("SMTP_FROM", "PokéAlpha <no-reply@localhost>"),
        "starttls": (os.getenv("SMTP_STARTTLS", "true").lower() != "false"),
    }


def send_email(to: str, subject: str, body: str) -> bool:
    """Envoie un email texte. Renvoie ``True`` si remis au serveur SMTP."""
    conf = _smtp_conf()
    if not conf["host"]:  # repli console (dev / tests)
        logger.info("EMAIL (console) → %s | %s\n%s", to, subject, body)
        return True
    try:
        msg = EmailMessage()
        msg["From"] = conf["sender"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(conf["host"], conf["port"], timeout=15) as smtp:
            if conf["starttls"]:
                smtp.starttls()
            if conf["user"]:
                smtp.login(conf["user"], conf["password"])
            smtp.send_message(msg)
        return True
    except Exception:  # noqa: BLE001 - l'email ne doit jamais casser le flux appelant
        logger.exception("Envoi email impossible vers %s (%s).", to, subject)
        return False
