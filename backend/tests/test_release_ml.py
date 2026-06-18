"""Tests du modèle ML Future Radar : entraînement réel (sklearn) → inférence.

On seede des produits + ``price_snapshots`` (scellé apprécie, single stagne) :
le modèle doit apprendre le signal et le repli heuristique tient sans modèle.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select

from app.ml.scorer import invalidate, load, score_release_ml, train
from app.models import MlModel, PriceSnapshot, Product


@dataclass
class Rel:
    product_name: str
    product_type: str
    release_date: dt.date | None = None
    preorder_date: dt.date | None = None
    source_note: str | None = None


def _seed(db, n=16):
    for i in range(n):
        sealed = i % 2 == 0
        name = f"{'ETB Coffret' if sealed else 'Pikachu'} set {i}"
        p = Product(product_type="sealed" if sealed else "single", name=name, language="EN")
        db.add(p)
        db.flush()
        base = 50.0 + i * 3
        # scellé : +20% ; single : -5% → ROI corrélé au type.
        recent = base * (1 + (0.20 if sealed else -0.05))
        db.add(PriceSnapshot(
            product_id=p.id, source="poketrace", currency="USD", grade_company="RAW",
            captured_at=dt.datetime(2026, 6, 1, 12, 0, 0),
            price_avg=base, avg_30d=base, avg_7d=recent, avg_1d=recent,
            price_high=recent * 1.1, price_low=base * 0.9, sale_count=10 + i,
        ))
    db.commit()


def test_train_persists_and_scores(db_session):
    invalidate()
    _seed(db_session, 16)
    res = train(db_session)
    assert res["status"] == "trained" and res["n_samples"] == 16
    assert "roi" in res["metrics"]

    row = db_session.scalar(select(MlModel).where(MlModel.name == "release_scorer"))
    assert row is not None and row.payload and row.n_samples == 16
    assert load(db_session) is not None

    s = score_release_ml(db_session, Rel("ETB Coffret UPC", "sealed",
                                         release_date=dt.date(2026, 9, 1), source_note="Annonce officielle."))
    assert s["model"] == "ml-v1"
    assert 30 <= s["hype"] <= 99
    assert 20 <= s["confidence"] <= 99
    assert 25 <= s["popularity"] <= 98
    assert isinstance(s["roi"], int)


def test_learns_type_signal(db_session):
    invalidate()
    _seed(db_session, 18)
    train(db_session)
    sealed = score_release_ml(db_session, Rel("ETB Coffret", "sealed"))
    single = score_release_ml(db_session, Rel("Pikachu V", "single"))
    # le scellé (apprécie à l'entraînement) doit obtenir un ROI >= au single.
    assert sealed["roi"] >= single["roi"]


def test_insufficient_data_keeps_heuristic(db_session):
    invalidate()
    _seed(db_session, 5)  # < MIN_SAMPLES
    res = train(db_session)
    assert res["status"] == "insufficient_data"
    assert score_release_ml(db_session, Rel("X", "sealed")) is None


def test_confidence_rises_with_release_data(db_session):
    invalidate()
    _seed(db_session, 14)
    train(db_session)
    bare = score_release_ml(db_session, Rel("Set", "sealed"))
    rich = score_release_ml(db_session, Rel("Set", "sealed", release_date=dt.date(2026, 9, 1),
                                            preorder_date=dt.date(2026, 7, 1),
                                            source_note="Confirmé par dépôt d'impression."))
    assert rich["confidence"] > bare["confidence"]
