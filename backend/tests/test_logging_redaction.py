"""Tests de redaction des secrets dans les logs JSON."""

from __future__ import annotations

import json
import logging

from app.logging_config import JsonFormatter, redact


def test_redact_replaces_secret():
    assert redact("token=abc123 end", ["abc123"]) == "token=*** end"
    assert redact("rien", ["abc123"]) == "rien"
    assert redact("x", [""]) == "x"  # secret vide ignoré


def test_json_formatter_redacts_and_is_json():
    fmt = JsonFormatter(secrets=["supersecret"])
    record = logging.makeLogRecord(
        {"msg": "connexion key=supersecret ok", "name": "t", "levelname": "INFO", "levelno": 20}
    )
    out = fmt.format(record)
    parsed = json.loads(out)  # sortie bien JSON
    assert "supersecret" not in out
    assert "***" in parsed["msg"]
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "t"


def test_json_formatter_redacts_exception():
    fmt = JsonFormatter(secrets=["tok-XYZ"])
    try:
        raise ValueError("boom tok-XYZ")
    except ValueError:
        import sys
        record = logging.makeLogRecord(
            {"msg": "err", "name": "t", "levelname": "ERROR", "levelno": 40, "exc_info": sys.exc_info()}
        )
    out = fmt.format(record)
    assert "tok-XYZ" not in out
