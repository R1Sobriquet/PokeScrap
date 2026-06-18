"""Entraînement / persistance / inférence du modèle Future Radar.

Trois régressseurs (gradient boosting) prédisent ``roi`` / ``popularity`` /
``hype`` à partir des features produit ; la sortie brute est ramenée en score
0-100 via les quantiles d'entraînement (P10/P90). La ``confidence`` est calculée
à part (complétude des données de la sortie + support du dataset).

scikit-learn / numpy / joblib sont importés PARESSEUSEMENT (au train/predict) :
le reste de l'app n'en dépend pas au chargement. Le bundle est persisté en base
(``ml_models``) et caché en mémoire par ``trained_at``.
"""

from __future__ import annotations

import datetime as dt
import io
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.dataset import TARGETS, build_training_rows
from app.ml.features import FEATURE_NAMES, extract_features
from app.models import MlModel

logger = logging.getLogger("ml.scorer")

MODEL_NAME = "release_scorer"
MIN_SAMPLES = 12  # en-deçà : on n'entraîne pas (fallback heuristique)

_CACHE: dict = {"trained_at": None, "bundle": None}


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _clamp(v: float, lo: int, hi: int) -> int:
    return int(max(lo, min(hi, round(v))))


def _dumps(obj) -> bytes:
    import joblib

    buf = io.BytesIO()
    joblib.dump(obj, buf)
    return buf.getvalue()


def _loads(blob: bytes):
    import joblib

    return joblib.load(io.BytesIO(blob))


# --------------------------------------------------------------- entraînement
def train(db: Session) -> dict:
    """Entraîne et persiste le modèle. Renvoie un résumé (statut + métriques)."""
    X, y = build_training_rows(db)
    n = len(X)
    if n < MIN_SAMPLES:
        return {"status": "insufficient_data", "n_samples": n,
                "summary": f"données insuffisantes (n={n}, min {MIN_SAMPLES}) — heuristique conservée"}

    import numpy as np
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import KFold, cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    Xa = np.asarray(X, dtype=float)
    n_splits = max(2, min(5, n // 4))
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=0)

    def _new_model():
        return make_pipeline(
            StandardScaler(),
            GradientBoostingRegressor(random_state=0, n_estimators=150,
                                      max_depth=2, learning_rate=0.05, subsample=0.9),
        )

    models, quantiles, metrics = {}, {}, {}
    for tgt in TARGETS:
        ya = np.asarray(y[tgt], dtype=float)
        # Métriques CROSS-VALIDÉES (held-out) — pas de R² in-sample optimiste.
        cv_r2 = float(np.mean(cross_val_score(_new_model(), Xa, ya, cv=kf, scoring="r2")))
        cv_mae = float(-np.mean(cross_val_score(_new_model(), Xa, ya, cv=kf,
                                                scoring="neg_mean_absolute_error")))
        model = _new_model()
        model.fit(Xa, ya)  # modèle final sur tout le jeu
        models[tgt] = model
        quantiles[tgt] = (float(np.percentile(ya, 10)), float(np.percentile(ya, 90)))
        metrics[tgt] = {"cv_r2": round(cv_r2, 3), "cv_mae": round(cv_mae, 2)}

    metrics["cv_folds"] = n_splits
    bundle = {"models": models, "feature_names": FEATURE_NAMES,
              "quantiles": quantiles, "n_samples": n}
    _persist(db, _dumps(bundle), n, metrics)
    invalidate()
    logger.info("Modèle release_scorer entraîné (n=%s, CV=%s).", n, metrics)
    summary = " ".join(f"{t} R²cv={metrics[t]['cv_r2']}" for t in TARGETS)
    return {"status": "trained", "n_samples": n, "metrics": metrics,
            "summary": f"modèle entraîné (n={n}, {n_splits}-fold CV · {summary})"}


def run_train_release_model(db: Session) -> dict:
    """Runner de job (registre ``JOBS``)."""
    return train(db)


def _persist(db: Session, payload: bytes, n: int, metrics: dict) -> None:
    row = db.scalar(select(MlModel).where(MlModel.name == MODEL_NAME))
    if row is None:
        row = MlModel(name=MODEL_NAME)
        db.add(row)
    row.payload = payload
    row.n_samples = n
    row.metrics = metrics
    row.trained_at = _utcnow()
    db.commit()


# --------------------------------------------------------------- inférence
def invalidate() -> None:
    _CACHE["trained_at"] = None
    _CACHE["bundle"] = None


def load(db: Session):
    """Charge le bundle (caché par ``trained_at``) ; ``None`` si non entraîné."""
    row = db.scalar(select(MlModel).where(MlModel.name == MODEL_NAME))
    if row is None or not row.payload:
        invalidate()
        return None
    if _CACHE["bundle"] is not None and _CACHE["trained_at"] == row.trained_at:
        return _CACHE["bundle"]
    bundle = _loads(row.payload)
    _CACHE["trained_at"] = row.trained_at
    _CACHE["bundle"] = bundle
    return bundle


def _scale(val: float, lo: float, hi: float, out_lo: int, out_hi: int) -> float:
    if hi <= lo:
        return (out_lo + out_hi) / 2
    return out_lo + (val - lo) / (hi - lo) * (out_hi - out_lo)


def predict(bundle, features: list[float]) -> dict:
    import numpy as np

    Xa = np.asarray([features], dtype=float)
    raw = {tgt: float(model.predict(Xa)[0]) for tgt, model in bundle["models"].items()}
    qh = bundle["quantiles"]["hype"]
    qp = bundle["quantiles"]["popularity"]
    return {
        "hype": _clamp(_scale(raw["hype"], qh[0], qh[1], 30, 99), 30, 99),
        "popularity": _clamp(_scale(raw["popularity"], qp[0], qp[1], 25, 98), 25, 98),
        "roi": _clamp(raw["roi"], -50, 300),
        "raw": {k: round(v, 2) for k, v in raw.items()},
    }


def _confidence(release, n_samples: int) -> int:
    """Confiance = complétude des données de la sortie + support du dataset."""
    c = 38.0
    if getattr(release, "release_date", None) is not None:
        c += 20
    if getattr(release, "preorder_date", None) is not None:
        c += 12
    note = (getattr(release, "source_note", None) or "").strip()
    if len(note) > 10:
        c += 12
    c += min(17.0, n_samples / 4.0)  # plus de données d'entraînement → plus de confiance
    return _clamp(c, 20, 99)


def score_release_ml(db: Session, release) -> dict | None:
    """Scores ML d'une sortie, ou ``None`` si aucun modèle entraîné."""
    bundle = load(db)
    if bundle is None:
        return None
    feats = extract_features(
        product_type=getattr(release, "product_type", None),
        name=getattr(release, "product_name", None),
        language="EN",
    )
    p = predict(bundle, feats)
    return {
        "hype": p["hype"],
        "confidence": _confidence(release, bundle.get("n_samples", 0)),
        "popularity": p["popularity"],
        "roi": p["roi"],
        "model": "ml-v1",
    }
