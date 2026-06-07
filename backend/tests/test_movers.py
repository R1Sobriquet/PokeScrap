"""Tests du radar top movers (momentum confirmé par le volume)."""

from __future__ import annotations

from app.domain.movers import momentum_rise, mover_score


def test_momentum_rise():
    assert momentum_rise(110, 100) == 0.1
    assert momentum_rise(110, 0) is None
    assert momentum_rise(None, 100) is None


def test_low_volume_is_ignored():
    # +50 % mais seulement 2 ventes < min_volume 5 → ignoré (anti-bruit).
    assert mover_score(150, 100, 2, min_volume=5) is None
    # volume suffisant → score calculé
    assert mover_score(150, 100, 50, min_volume=5) is not None


def test_higher_volume_ranks_higher_at_equal_rise():
    big = mover_score(150, 100, 200, min_volume=5)
    small = mover_score(150, 100, 6, min_volume=5)
    assert big > small  # à hausse égale, plus gros volume = plus haut


def test_bigger_rise_ranks_higher_at_equal_volume():
    strong = mover_score(200, 100, 50, min_volume=5)
    mild = mover_score(110, 100, 50, min_volume=5)
    assert strong > mild
