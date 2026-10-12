"""bcm.py: "best close match" distance baseline (improvement #2).

The classic distance rule from the barcoding literature (Meier et al. 2006,
Systematic Biology 55:715-728), with no tree and no machine learning:

    Find the training sequence(s) with the smallest K2P distance to the query.
    If that distance is above the cut-off            -> "unknown"
    else if all equally-close matches are one species -> that species
    else                                              -> "ambiguous"

Main cut-off (Meier's rule): the distance below which 95% of within-species
pairs in the TRAINING set fall. Also reported, for sensitivity:
    accept 90/95/99%  calibrated like the ML models (cross-validation within
                      training, accept that share of known-species queries)
    fixed 2%          a common barcoding rule of thumb (K2P 0.02)

It uses the same alignment and K2P distances as the NJ tree. This tests whether
k-NN's safety comes from machine learning or simply from having a distance cut-off.

Output (Condition A): results/tables/bcm_predictions_A.csv, bcm_thresholds.csv
(Condition B and the replicates call run_bcm() from their own scripts.)

Run from the repo root:
    python src/bcm.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from Bio import SeqIO
from sklearn.model_selection import RepeatedStratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (  # noqa: E402
    PROCESSED_DIR, SEED, SENSITIVITY_ACCEPT_RATES, TABLES_DIR,
)
from distances import k2p_matrix  # noqa: E402

ALIGNED = PROCESSED_DIR / "aligned.fasta"
DIST_CACHE = PROCESSED_DIR / "k2p_matrix.npy"     # git-ignored (*.npy), rebuilt in ~10 s
FIXED_CUTOFF = 0.02
MEIER_QUANTILE = 0.95
TIE = 1e-9                                         # distances this close count as a tie


def load_distances():
    """K2P matrix for all aligned sequences (cached), and each ID's row number."""
    ids = [r.id for r in SeqIO.parse(ALIGNED, "fasta")]
    if DIST_CACHE.exists() and DIST_CACHE.stat().st_mtime > ALIGNED.stat().st_mtime:
        D = np.load(DIST_CACHE)
    else:
        aligned = {r.id: str(r.seq) for r in SeqIO.parse(ALIGNED, "fasta")}
        D = k2p_matrix([aligned[i] for i in ids])
        np.save(DIST_CACHE, D)
    return D, {seq_id: i for i, seq_id in enumerate(ids)}


def best_match(D_sub, train_species):
    """For each query row of D_sub: (species or 'ambiguous', nearest distance)."""
    answers, nearest = [], []
    for row in D_sub:
        d = row.min()
        tied = {train_species[j] for j in np.where(row <= d + TIE)[0]}
        answers.append(tied.pop() if len(tied) == 1 else "ambiguous")
        nearest.append(d)
    return answers, np.array(nearest)


def meier_cutoff(D_train, species):
    """Distance below which MEIER_QUANTILE of within-species training pairs fall."""
    same = (species[:, None] == species[None, :]) & np.triu(np.ones_like(D_train, dtype=bool), k=1)
    return float(np.quantile(D_train[same], MEIER_QUANTILE))


def calibrated_cutoffs(D_train, species, seed):
    """Cut-offs that accept each SENSITIVITY_ACCEPT_RATES share of known queries.

    Same procedure as the ML models: 2-fold stratified CV repeated 5 times on
    training data; the score is the nearest-match distance.
    """
    cv = RepeatedStratifiedKFold(n_splits=2, n_repeats=5, random_state=seed)
    scores = []
    for fit_idx, score_idx in cv.split(D_train, species):
        scores.extend(D_train[np.ix_(score_idx, fit_idx)].min(axis=1))
    return {rate: float(np.percentile(scores, 100 * rate)) for rate in SENSITIVITY_ACCEPT_RATES}


def run_bcm(train, queries, seed=SEED):
    """Best-close-match predictions for the queries; returns (predictions, cutoffs).

    train, queries: DataFrames with seq_id and species (query species unused).
    """
    D, row = load_distances()
    t_rows = np.array([row[i] for i in train.seq_id])
    q_rows = np.array([row[i] for i in queries.seq_id])
    assert not set(train.seq_id) & set(queries.seq_id), "query sequence in training"
    species = train.species.to_numpy()

    D_train = D[np.ix_(t_rows, t_rows)]
    cutoffs = {"meier": meier_cutoff(D_train, species), "fixed_2": FIXED_CUTOFF}
    cutoffs.update({f"at_{round(r * 100)}": c for r, c in calibrated_cutoffs(D_train, species, seed).items()})

    answers, nearest = best_match(D[np.ix_(q_rows, t_rows)], species)
    preds = pd.DataFrame({"query_id": list(queries.seq_id), "predicted_species": answers,
                          "nearest_distance": nearest.round(5) + 0.0})   # + 0.0 turns -0.0 into 0.0
    preds["flagged_unknown"] = nearest > cutoffs["meier"]           # main rule
    for name, cut in cutoffs.items():
        if name != "meier":
            preds[f"flagged_{name}"] = nearest > cut
    return preds, cutoffs


def main():
    split = pd.read_csv(PROCESSED_DIR / "split_A.csv")
    train, test = split[split.set == "train"], split[split.set == "test"]
    preds, cutoffs = run_bcm(train, test)
    preds.insert(1, "true_species", list(test.species))
    preds["correct"] = preds.predicted_species == preds.true_species
    preds.to_csv(TABLES_DIR / "bcm_predictions_A.csv", index=False)
    pd.DataFrame([{"rule": k, "cutoff_k2p": round(v, 5)} for k, v in cutoffs.items()]).to_csv(
        TABLES_DIR / "bcm_thresholds.csv", index=False)

    n = len(preds)
    with_cut = preds.predicted_species.where(~preds.flagged_unknown, "unknown")
    print(f"Best close match, Condition A ({n} queries)")
    print("  cut-offs (K2P): " + ", ".join(f"{k} {v:.4f}" for k, v in cutoffs.items()))
    print(f"  no cut-off  : correct {preds.correct.mean():.1%}, ambiguous "
          f"{(preds.predicted_species == 'ambiguous').mean():.1%}")
    print(f"  Meier cut   : correct {(with_cut == preds.true_species).mean():.1%}, "
          f"flagged unknown {preds.flagged_unknown.mean():.1%}")


if __name__ == "__main__":
    main()
