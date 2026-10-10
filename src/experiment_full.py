"""experiment_full.py: Condition A (full coverage), both methods side by side.

Combines the cached predictions of phylo_baseline.py and ml_classifiers.py
(run those first) into one table with one row per query, after checking that
NJ and ML were tested on exactly the same queries.

Output: results/tables/condition_A.csv

Run from the repo root:
    python src/experiment_full.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED_DIR, TABLES_DIR  # noqa: E402


def to_wide(nj, ml, truth):
    """One row per query: truth, then NJ's answer, then each ML variant's answer.

    nj:    query_id, predicted_species, predicted_genus, ref_species_in_clade
    ml:    model, k, query_id, predicted_species, confidence, flagged_unknown
    truth: query_id, true_species, true_genus, query_type
    """
    assert set(nj.query_id) == set(truth.query_id), "NJ queries differ from the split"
    for (model, k), g in ml.groupby(["model", "k"]):
        assert set(g.query_id) == set(truth.query_id), f"{model} k={k} queries differ"

    wide = truth.merge(
        nj[["query_id", "predicted_species", "predicted_genus", "ref_species_in_clade"]]
        .rename(columns=lambda c: c if c == "query_id" else f"nj_{c}"), on="query_id")
    for (model, k), g in ml.groupby(["model", "k"], sort=False):
        prefix = f"{model}_k{k}_"
        wide = wide.merge(
            g[["query_id", "predicted_species", "confidence", "flagged_unknown"]
              + [c for c in g.columns if c.startswith("flagged_at_")]]
            .rename(columns=lambda c: c if c == "query_id" else prefix + c), on="query_id")
    return wide


def main():
    meta = pd.read_csv(PROCESSED_DIR / "metadata.csv")
    genus_of = dict(zip(meta.species, meta.genus))
    split = pd.read_csv(PROCESSED_DIR / "split_A.csv")
    test = split[split.set == "test"]
    truth = pd.DataFrame({"query_id": test.seq_id, "true_species": test.species,
                          "true_genus": test.species.map(genus_of), "query_type": "known"})

    nj = pd.read_csv(TABLES_DIR / "nj_predictions_A.csv")
    ml = pd.read_csv(TABLES_DIR / "ml_predictions_A.csv")
    wide = to_wide(nj, ml, truth)
    wide.to_csv(TABLES_DIR / "condition_A.csv", index=False)

    print(f"Condition A: {len(wide)} queries, same set for NJ and all 4 ML variants")
    print(f"  {'method':8s} {'correct species':>15s}")
    print(f"  {'nj':8s} {(wide.nj_predicted_species == wide.true_species).mean():15.1%}")
    for col in [c for c in wide.columns if c.endswith("_predicted_species") and not c.startswith("nj")]:
        name = col.replace("_predicted_species", "")
        print(f"  {name:8s} {(wide[col] == wide.true_species).mean():15.1%}")
    print(f"Wrote {TABLES_DIR / 'condition_A.csv'}")


if __name__ == "__main__":
    main()
