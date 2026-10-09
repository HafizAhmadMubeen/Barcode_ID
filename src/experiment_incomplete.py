"""experiment_incomplete.py: Condition B (incomplete coverage), both methods.

Some species (results/heldout_species.txt) are removed from training entirely.
Queries are all sequences of those species ("unknown": no correct species
answer exists) plus the Condition A test sequences of the other species ("known").

  NJ: a new tree of the Condition B training sequences + all queries, with the
      same smallest-clade rule as Phase 2 ("ambiguous" is its only abstention).
  ML: the same four variants, retrained on Condition B training data, with the
      "unknown" thresholds re-calibrated on that training data (same 95% rule).

Output: results/nj_tree_B.nwk                 (cached)
        results/models/condition_B/            (git-ignored)
        results/tables/condition_B.csv         one row per query, all methods
        results/tables/ml_thresholds_B.csv

Run from the repo root (after splits.py, features.py):
    python src/experiment_incomplete.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED_DIR, RESULTS_DIR, TABLES_DIR  # noqa: E402
from experiment_full import to_wide  # noqa: E402
from ml_classifiers import MODELS_DIR, run_ml  # noqa: E402
from phylo_baseline import AMBIGUOUS, run_nj  # noqa: E402

SPLIT_B = PROCESSED_DIR / "split_B.csv"
HELDOUT = RESULTS_DIR / "heldout_species.txt"
TREE_B = RESULTS_DIR / "nj_tree_B.nwk"
ML_VARIANTS = ["knn_k4", "rf_k4", "knn_k6", "rf_k6"]


def main():
    meta = pd.read_csv(PROCESSED_DIR / "metadata.csv")
    genus_of = dict(zip(meta.species, meta.genus))
    heldout = HELDOUT.read_text(encoding="utf-8").split("\n")[:-1]
    split = pd.read_csv(SPLIT_B)
    train = split[split.set == "train"]
    queries = split[split.set != "train"]

    # Leakage check: no held-out species anywhere in the training data.
    assert not set(heldout) & set(train.species), "held-out species in training"
    print(f"Held-out species ({len(heldout)}): {', '.join(heldout)}")
    print(f"Training: {len(train)} sequences, {train.species.nunique()} species | "
          f"queries: {(queries.set == 'test_known').sum()} known + "
          f"{(queries.set == 'test_unknown').sum()} unknown\n")

    nj, _, _ = run_nj(train, queries, TREE_B, [SPLIT_B, HELDOUT])
    ml, thresholds, _ = run_ml(list(train.seq_id), train.species, list(queries.seq_id),
                               MODELS_DIR / "condition_B")
    # Leakage check on the fitted models: no held-out species among their classes.
    assert not set(heldout) & set(ml.predicted_species), "a model predicted a held-out species"
    pd.DataFrame(thresholds).to_csv(TABLES_DIR / "ml_thresholds_B.csv", index=False)

    truth = pd.DataFrame({
        "query_id": queries.seq_id, "true_species": queries.species,
        "true_genus": queries.species.map(genus_of),
        "query_type": queries.set.str.replace("test_", "", regex=False)})
    wide = to_wide(nj, ml, truth)
    wide.to_csv(TABLES_DIR / "condition_B.csv", index=False)

    # --- Summary: unknown queries (held-out species) ---
    unk = wide[wide.query_type == "unknown"]
    print(f"UNKNOWN queries ({len(unk)}; a species answer is always wrong here)")
    print(f"  {'method':16s} {'names a species':>15s} {'abstains':>9s} {'correct genus':>13s}")
    named = unk.nj_predicted_species != AMBIGUOUS
    print(f"  {'nj':16s} {named.mean():15.1%} {(~named).mean():9.1%} "
          f"{(unk.nj_predicted_genus == unk.true_genus).mean():13.1%}")
    for v in ML_VARIANTS:
        genus_ok = unk[f"{v}_predicted_species"].str.split().str[0] == unk.true_genus
        flagged = unk[f"{v}_flagged_unknown"]
        print(f"  {v + ' (no thresh.)':16s} {1.0:15.1%} {0.0:9.1%} {genus_ok.mean():13.1%}")
        print(f"  {v + ' (threshold)':16s} {(~flagged).mean():15.1%} {flagged.mean():9.1%} "
              f"{(genus_ok & ~flagged).mean():13.1%}")

    # --- Summary: known queries ---
    kno = wide[wide.query_type == "known"]
    print(f"\nKNOWN queries ({len(kno)})")
    print(f"  {'method':8s} {'correct species':>15s} {'abstains':>9s}")
    print(f"  {'nj':8s} {(kno.nj_predicted_species == kno.true_species).mean():15.1%} "
          f"{(kno.nj_predicted_species == AMBIGUOUS).mean():9.1%}")
    for v in ML_VARIANTS:
        print(f"  {v:8s} {(kno[f'{v}_predicted_species'] == kno.true_species).mean():15.1%} "
              f"{kno[f'{v}_flagged_unknown'].mean():9.1%}")
    print(f"\nWrote {TABLES_DIR / 'condition_B.csv'}")


if __name__ == "__main__":
    main()
