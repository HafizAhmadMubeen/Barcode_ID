"""splits.py: create the train/test split shared by the NJ and ML methods.

Condition A (full coverage): split *within* each species, so every test species
also has training sequences. About 30% of each species' sequences become test
queries, with at least 1 test and at least 2 training sequences per species.
Dedup in data_cleaning.py guarantees no identical sequence of the same species
sits on both sides of the split.

Output: data/processed/split_A.csv   columns: seq_id, species, set ("train"/"test")

The file is written once and never regenerated: if it exists, it is only checked.
Delete it on purpose if the split must change.

(The Condition B split, with whole species held out, is added in Phase 4.)

Run from the repo root:
    python src/splits.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED_DIR, SEED, TEST_FRACTION_A  # noqa: E402

SPLIT_A = PROCESSED_DIR / "split_A.csv"


def make_split_A(meta):
    """Stratified within-species split with a fixed seed."""
    rng = np.random.default_rng(SEED)
    rows = []
    for species, group in meta.sort_values("seq_id").groupby("species"):
        ids = group.seq_id.to_numpy()
        rng.shuffle(ids)
        n_test = max(1, round(TEST_FRACTION_A * len(ids)))
        n_test = min(n_test, len(ids) - 2)          # keep at least 2 for training
        for i, seq_id in enumerate(ids):
            rows.append({"seq_id": seq_id, "species": species,
                         "set": "test" if i < n_test else "train"})
    return pd.DataFrame(rows)


def main():
    meta = pd.read_csv(PROCESSED_DIR / "metadata.csv")
    if SPLIT_A.exists():
        split = pd.read_csv(SPLIT_A)
        print(f"Using existing {SPLIT_A} (not regenerated)")
    else:
        split = make_split_A(meta)
        split.to_csv(SPLIT_A, index=False)
        print(f"Wrote {SPLIT_A}")

    # Checks: every sequence assigned once, every species on both sides.
    assert sorted(split.seq_id) == sorted(meta.seq_id), "split does not match metadata.csv"
    per_species = split.groupby(["species", "set"]).size().unstack(fill_value=0)
    assert (per_species["test"] >= 1).all() and (per_species["train"] >= 2).all()

    counts = split.set.value_counts()
    print(f"train: {counts['train']} sequences | test: {counts['test']} sequences "
          f"| species: {split.species.nunique()} (all on both sides)")


if __name__ == "__main__":
    main()
