"""ml_classifiers.py: k-NN and Random Forest on k-mer features (Condition A).

Models (settings chosen in Phase 3 by cross-validation on training data only):
    k-NN:          5 neighbours, closer neighbours weigh more (weights="distance")
    Random Forest: 500 trees, class_weight="balanced" (rare species weigh more)
Each is trained on k=4 and on k=6 features, so there are four model variants.

"Unknown" rule (decided in Phase 3):
    The threshold is set so that 95% of known-species queries are accepted.
    It is calibrated on the TRAINING data only, using cross-validation
    (train on half, score the other half, repeated), never on test data.
      Random Forest: flag "unknown" if the top class probability is below
                     the 5th percentile seen for known-species queries.
      k-NN:          flag "unknown" if the distance to the nearest training
                     sequence is above the 95th percentile seen for
                     known-species queries.

Input:  data/processed/kmer_k4.npy, kmer_k6.npy, kmer_ids.txt, split_A.csv
Output: results/models/<model>_k<k>.joblib      (git-ignored, re-created by this script)
        results/tables/ml_thresholds.csv         the four calibrated thresholds
        results/tables/ml_predictions_A.csv      one row per (model, k, query)
        results/tables/ml_timing_A.csv

Run from the repo root:
    python src/ml_classifiers.py
"""
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.neighbors import KNeighborsClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (  # noqa: E402
    KMER_SIZES, PROCESSED_DIR, RESULTS_DIR, SEED, TABLES_DIR, UNKNOWN_ACCEPT_RATE,
)

MODELS_DIR = RESULTS_DIR / "models"
UNKNOWN = "unknown"


def make_model(name):
    """A fresh, unfitted model with the settings chosen in Phase 3."""
    if name == "knn":
        return KNeighborsClassifier(n_neighbors=5, weights="distance")
    return RandomForestClassifier(n_estimators=500, class_weight="balanced",
                                  random_state=SEED, n_jobs=-1)


def confidence(model, name, X):
    """Confidence score per query: higher always means 'more sure'.

    RF: top class probability. k-NN: minus the distance to the nearest training
    sequence (negated so that, like RF, a higher score means more confident).
    """
    if name == "knn":
        return -model.kneighbors(X, n_neighbors=1)[0][:, 0]
    return model.predict_proba(X).max(axis=1)


def calibrate_threshold(name, X, y):
    """Confidence cut-off that accepts UNKNOWN_ACCEPT_RATE of known-species queries.

    Uses only training data: 2-fold stratified CV (some species have just 2
    training sequences), repeated 5 times, pooling the held-out scores.
    """
    cv = RepeatedStratifiedKFold(n_splits=2, n_repeats=5, random_state=SEED)
    scores = []
    for fit_idx, score_idx in cv.split(X, y):
        model = make_model(name).fit(X[fit_idx], y[fit_idx])
        scores.extend(confidence(model, name, X[score_idx]))
    return float(np.percentile(scores, 100 * (1 - UNKNOWN_ACCEPT_RATE)))


def main():
    ids = (PROCESSED_DIR / "kmer_ids.txt").read_text(encoding="utf-8").split()
    split = pd.read_csv(PROCESSED_DIR / "split_A.csv").set_index("seq_id").loc[ids]
    is_train = (split.set == "train").to_numpy()
    y_train = split.species.to_numpy()[is_train]
    test_ids = np.array(ids)[~is_train]
    y_test = split.species.to_numpy()[~is_train]
    assert not set(test_ids) & set(np.array(ids)[is_train]), "test sequence in training"

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    predictions, thresholds, timing = [], [], []

    for k in KMER_SIZES:
        X = np.load(PROCESSED_DIR / f"kmer_k{k}.npy")
        X_train, X_test = X[is_train], X[~is_train]
        for name in ("knn", "rf"):
            threshold = calibrate_threshold(name, X_train, y_train)

            start = time.time()
            model = make_model(name).fit(X_train, y_train)
            fit_seconds = time.time() - start
            joblib.dump(model, MODELS_DIR / f"{name}_k{k}.joblib")

            start = time.time()
            predicted = model.predict(X_test)
            conf = confidence(model, name, X_test)
            predict_seconds = time.time() - start

            flagged = conf < threshold
            predictions.append(pd.DataFrame({
                "model": name, "k": k, "query_id": test_ids, "true_species": y_test,
                "predicted_species": predicted,                       # always a known species
                "confidence": np.round(conf, 4),
                "flagged_unknown": flagged,
                "predicted_with_unknown": np.where(flagged, UNKNOWN, predicted),
                "correct": predicted == y_test,
            }))
            # Shown as a positive distance for k-NN so it reads naturally.
            shown = -threshold if name == "knn" else threshold
            thresholds.append({"model": name, "k": k,
                               "score": "nearest_distance_max" if name == "knn" else "top_probability_min",
                               "threshold": round(shown, 4), "accept_rate": UNKNOWN_ACCEPT_RATE})
            timing.append({"model": name, "k": k, "fit_seconds": round(fit_seconds, 2),
                           "predict_seconds_total": round(predict_seconds, 3),
                           "predict_ms_per_query": round(1000 * predict_seconds / len(test_ids), 3)})

    preds = pd.concat(predictions, ignore_index=True)
    preds.to_csv(TABLES_DIR / "ml_predictions_A.csv", index=False)
    pd.DataFrame(thresholds).to_csv(TABLES_DIR / "ml_thresholds.csv", index=False)
    pd.DataFrame(timing).to_csv(TABLES_DIR / "ml_timing_A.csv", index=False)

    n_species = len(set(y_train))
    print(f"Condition A, ML ({len(test_ids)} queries, {n_species} species; "
          f"random guessing = {1 / n_species:.1%})\n")
    print(f"{'model':6s} {'k':>2s}  {'accuracy':>8s}  {'flagged unknown':>15s}  "
          f"{'threshold':>22s}  {'ms/query':>8s}")
    for (name, k), g in preds.groupby(["model", "k"], sort=False):
        t = next(t for t in thresholds if t["model"] == name and t["k"] == k)
        ms = next(t for t in timing if t["model"] == name and t["k"] == k)["predict_ms_per_query"]
        print(f"{name:6s} {k:2d}  {g.correct.mean():8.1%}  {g.flagged_unknown.mean():15.1%}  "
              f"{t['score'] + ' ' + str(t['threshold']):>22s}  {ms:8.3f}")


if __name__ == "__main__":
    main()
