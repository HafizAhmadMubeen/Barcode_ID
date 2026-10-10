"""replicates.py: re-run the whole experiment with other seeds (robustness check).

The main results use SEED 42 and are never touched here. For each seed in
config.REPLICATE_SEEDS this script draws a new Condition A split, a new set of
held-out species (same rule: one per multi-species genus), retrains every
model with that seed, and runs both conditions. If the conclusion only holds
for seed 42, it was a lucky split.

Output per seed, in results/replicates/seed_<N>/:
    split_A.csv, heldout_species.txt, split_B.csv
    nj_tree_A.nwk, nj_tree_B.nwk          (cached)
    condition_A.csv, condition_B.csv      same format as the main results
    models/                               (git-ignored)

Takes ~10 minutes per seed (two NJ trees). Run from the repo root:
    python src/replicates.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED_DIR, REPLICATE_SEEDS, RESULTS_DIR  # noqa: E402
from experiment_full import to_wide  # noqa: E402
from ml_classifiers import run_ml  # noqa: E402
from phylo_baseline import run_nj  # noqa: E402
from splits import choose_heldout, make_split_A, make_split_B  # noqa: E402

REPLICATES_DIR = RESULTS_DIR / "replicates"


def truth_table(queries, genus_of, query_type):
    """The true answer for each query, in the format to_wide() expects."""
    return pd.DataFrame({"query_id": queries.seq_id, "true_species": queries.species,
                         "true_genus": queries.species.map(genus_of), "query_type": query_type})


def run_condition(name, split, train_set, out_dir, genus_of, seed, cache_inputs):
    """Run NJ and ML on one split and write condition_<name>.csv."""
    train = split[split.set == train_set]
    queries = split[split.set != train_set]
    query_type = queries.set.map({"test": "known", "test_known": "known", "test_unknown": "unknown"})
    nj, _, _ = run_nj(train, queries, out_dir / f"nj_tree_{name}.nwk", cache_inputs)
    ml, _, _ = run_ml(list(train.seq_id), train.species, list(queries.seq_id),
                      out_dir / "models" / name, seed=seed)
    wide = to_wide(nj, ml, truth_table(queries, genus_of, query_type))
    wide.to_csv(out_dir / f"condition_{name}.csv", index=False)
    return wide


def main():
    meta = pd.read_csv(PROCESSED_DIR / "metadata.csv")
    genus_of = dict(zip(meta.species, meta.genus))

    for seed in REPLICATE_SEEDS:
        out_dir = REPLICATES_DIR / f"seed_{seed}"
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== seed {seed} ===")

        # Splits for this seed (made once, like the main ones).
        path_A, path_H, path_B = (out_dir / "split_A.csv", out_dir / "heldout_species.txt",
                                  out_dir / "split_B.csv")
        if not path_A.exists():
            make_split_A(meta, seed).to_csv(path_A, index=False)
        split_A = pd.read_csv(path_A)
        if not path_H.exists():
            path_H.write_text("\n".join(choose_heldout(meta, seed)) + "\n", encoding="utf-8")
        heldout = path_H.read_text(encoding="utf-8").split("\n")[:-1]
        if not path_B.exists():
            make_split_B(split_A, heldout).to_csv(path_B, index=False)
        split_B = pd.read_csv(path_B)
        assert not set(heldout) & set(split_B[split_B.set == "train"].species)
        print("held-out:", ", ".join(heldout))

        a = run_condition("A", split_A, "train", out_dir, genus_of, seed, [path_A])
        b = run_condition("B", split_B, "train", out_dir, genus_of, seed, [path_B, path_H])
        print(f"A: NJ {(a.nj_predicted_species == a.true_species).mean():.1%}, "
              f"kNN k6 {(a.knn_k6_predicted_species == a.true_species).mean():.1%}, "
              f"RF k6 {(a.rf_k6_predicted_species == a.true_species).mean():.1%}")
        unk = b[b.query_type == "unknown"]
        print(f"B unknown ({len(unk)}): NJ names a species {(unk.nj_predicted_species != 'ambiguous').mean():.1%}, "
              f"kNN k6 flagged {unk.knn_k6_flagged_unknown.mean():.1%}, "
              f"RF k6 flagged {unk.rf_k6_flagged_unknown.mean():.1%}")


if __name__ == "__main__":
    main()
