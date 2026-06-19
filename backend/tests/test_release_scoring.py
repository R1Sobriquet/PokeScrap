"""Tests du modèle heuristique Future Radar (déterministe, monotone)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.services.release_scoring import score_release


@dataclass
class Rel:
    product_name: str = "Booster"
    product_type: str | None = None
    release_date: dt.date | None = None
    preorder_date: dt.date | None = None
    source_note: str | None = None


TODAY = dt.date(2026, 6, 18)


def test_scores_in_range_and_deterministic():
    r = Rel(product_name="151 UPC", product_type="upc", release_date=dt.date(2026, 9, 1),
            source_note="Print filing leaked, strong demand expected.")
    a = score_release(r, today=TODAY)
    b = score_release(r, today=TODAY)
    assert a == b  # déterministe
    for k in ("hype", "confidence", "popularity"):
        assert 0 <= a[k] <= 100
    assert a["heuristic"] is True


def test_dated_sourced_more_confident_than_rumor():
    rumor = Rel(product_name="Mystery set")
    confirmed = Rel(product_name="Mystery set", release_date=dt.date(2026, 8, 1),
                    preorder_date=dt.date(2026, 6, 1), source_note="Officially announced today.")
    assert score_release(confirmed, today=TODAY)["confidence"] > score_release(rumor, today=TODAY)["confidence"]


def test_premium_type_scores_higher_hype_than_plain_booster():
    upc = Rel(product_name="X UPC", product_type="upc", release_date=dt.date(2026, 8, 1))
    booster = Rel(product_name="X booster", product_type="booster", release_date=dt.date(2026, 8, 1))
    assert score_release(upc, today=TODAY)["hype"] >= score_release(booster, today=TODAY)["hype"]


def test_imminent_release_more_hype_than_far_out():
    near = Rel(product_name="X etb", product_type="etb", release_date=dt.date(2026, 7, 1))
    far = Rel(product_name="X etb", product_type="etb", release_date=dt.date(2027, 6, 1))
    assert score_release(near, today=TODAY)["hype"] > score_release(far, today=TODAY)["hype"]
