"""Logs structurés JSON + redaction des secrets.

Aucune clé/token ne doit apparaître en clair dans les logs : le formateur
remplace toute occurrence d'un secret connu (lu depuis ``.env``) par ``***``.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os


def redact(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s and s in text:
            text = text.replace(s, "***")
    return text


class JsonFormatter(logging.Formatter):
    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        self._secrets = [s for s in (secrets or []) if s]

    def format(self, record: logging.LogRecord) -> str:
        msg = redact(record.getMessage(), self._secrets)
        payload = {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": msg,
        }
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info), self._secrets)
        return json.dumps(payload, ensure_ascii=False)


def collect_secrets() -> list[str]:
    """Valeurs sensibles à masquer (jamais loggées en clair)."""
    from app.config import get_settings

    s = get_settings()
    return [
        s.jwt_secret, s.db_password, s.admin_password,
        s.poketrace_api_key, s.psa_api_password, s.psa_api_token,
        os.getenv("DISCORD_BOT_TOKEN", ""), os.getenv("DB_ROOT_PASSWORD", ""),
        os.getenv("BACKUP_ENCRYPTION_KEY", ""),
    ]


def setup_logging(level: str | None = None, *, redact_secrets: bool | None = None) -> None:
    """Configure le root logger en JSON, niveau ``LOG_LEVEL``, secrets masqués."""
    lvl = (level or os.getenv("LOG_LEVEL", "info")).upper()
    if redact_secrets is None:
        redact_secrets = os.getenv("LOG_REDACT_SECRETS", "true").lower() != "false"
    secrets = collect_secrets() if redact_secrets else []
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(secrets))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, lvl, logging.INFO))
