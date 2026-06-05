"""Tests domaine : signal d'accumulation PE (pur)."""

from __future__ import annotations

from app.domain.pe_signal import pe_accumulation_signal


def test_fires_at_threshold():
    r = pe_accumulation_signal(singles_rising=True, reprint_ended=True, min_triggers=2)
    assert r.fire
    assert r.trigger_count == 2
    assert set(r.triggers) == {"singles_rising", "reprint_ended"}


def test_below_threshold_does_not_fire():
    r = pe_accumulation_signal(singles_rising=True, min_triggers=2)
    assert not r.fire
    assert r.trigger_count == 1


def test_all_triggers():
    r = pe_accumulation_signal(
        singles_rising=True, sealed_rising=True,
        reprint_ended=True, stock_declining=True, min_triggers=2,
    )
    assert r.fire
    assert r.trigger_count == 4
