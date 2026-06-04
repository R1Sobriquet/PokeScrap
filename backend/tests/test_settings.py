"""Tests du registre métier ``get_setting`` (typage + cache)."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.config import get_setting


def _insert(engine, key, value, value_type):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO settings (setting_key, setting_value, value_type) "
                "VALUES (:k, :v, :t)"
            ),
            {"k": key, "v": value, "t": value_type},
        )


def test_decimal_seed_returns_50(sqlite_engine):
    _insert(sqlite_engine, "fifty_rule_threshold_pct", "50", "decimal")
    assert get_setting("fifty_rule_threshold_pct") == 50


def test_bool_coercion(sqlite_engine):
    _insert(sqlite_engine, "valuation_net_of_fees", "true", "bool")
    assert get_setting("valuation_net_of_fees") is True


def test_int_coercion(sqlite_engine):
    _insert(sqlite_engine, "tier_sustain_snapshots", "3", "int")
    assert get_setting("tier_sustain_snapshots") == 3


def test_json_coercion(sqlite_engine):
    _insert(sqlite_engine, "grade_prob_default", '{"10": 0.30}', "json")
    assert get_setting("grade_prob_default") == {"10": 0.30}


def test_missing_key_raises(sqlite_engine):
    with pytest.raises(KeyError):
        get_setting("does_not_exist")


def test_missing_key_default(sqlite_engine):
    assert get_setting("does_not_exist", default="fallback") == "fallback"
