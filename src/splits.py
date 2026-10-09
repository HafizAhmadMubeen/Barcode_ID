"""splits.py: create the train/test splits shared by the NJ and ML methods.

Condition A (full coverage): split *within* each species, so every test species
also has training sequences. About 30% of each species' sequences become test
queries, with at least 1 test and at least 2 training sequences per species.
Dedup in data_cleaning.py guarantees no identical sequence of the same species
sits on both sides of the split.

Condition B (incomplete coverage): some species are held out of training
entirely. One species is drawn at random (SEED) from each genus that has at
least two species, so every held-out species still has relatives in training.
    train         = Condition A training sequences, minus held-out species
    test_known    = Condition A test sequences of the remaining species
    test_unknown  = ALL sequences of the held-out species

Output: data/processed/split_A.csv     columns: seq_id, species, set ("train"/"test")
        results/heldout_species.txt    one held-out species per line
        data/processed/split_B.csv     columns: seq_id, species, set

Each file is written once and never regenerated: if it exists, it is only
checked. Delete it on purpose if the split must change.

Run from the repo root:
    python src/splits.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED_DIR, RESULTS_DIR, SEED, TEST_FRACTION_A  # noqa: E402

SPLIT_A = PROCESSED_DIR / "split_A.csv"
SPLIT_B = PROCESSED_DIR / "split_B.csv"
HELDOUT = RESULTS_DIR / "heldout_species.txt"


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


def choose_heldout(meta):
    """One random species from each genus with at least two species."""
    rng = np.random.default_rng(SEED)
    heldout = []
    for genus, group in meta.groupby("genus"):          # genera in alphabetical order
        species = sorted(group.species.unique())
        if len(species) >= 2:
            heldout.append(str(rng.choice(species)))
    return heldout


def make_split_B(split_A, heldout):
    """Condition B sets, derived from Condition A (see module docstring)."""
    out = split_A.copy()
    is_held = out.species.isin(heldout)
    out["set"] = np.where(is_held, "test_unknown",
                          np.where(out.set == "train", "train", "test_known"))
    return out


def load_or_make(path, make, read):
    """Read a split file if it exists, otherwise create it once."""
    if path.exists():
        print(f"Using existing {path} (not regenerated)")
        return read(path)
    result = make()
    print(f"Wrote {path}")
    return result


def main():
    meta = pd.read_csv(PROCESSED_DIR / "metadata.csv")

    # --- Condition A ---
    def make_A():
        split = make_split_A(meta)
        split.to_csv(SPLIT_A, index=False)
        return split
    split_A = load_or_make(SPLIT_A, make_A, pd.read_csv)
    assert sorted(split_A.seq_id) == sorted(meta.seq_id), "split_A does not match metadata.csv"
    per_species = split_A.groupby(["species", "set"]).size().unstack(fill_value=0)
    assert (per_species["test"] >= 1).all() and (per_species["train"] >= 2).all()
    counts = split_A.set.value_counts()
    print(f"  A: train {counts['train']} | test {counts['test']} "
          f"| species {split_A.species.nunique()} (all on both sides)")

    # --- Held-out species (Condition B) ---
    def make_heldout():
        heldout = choose_heldout(meta)
        HELDOUT.parent.mkdir(parents=True, exist_ok=True)
        HELDOUT.write_text("\n".join(heldout) + "\n", encoding="utf-8")
        return heldout
    heldout = load_or_make(HELDOUT, make_heldout,
                           lambda p: p.read_text(encoding="utf-8").split("\n")[:-1])
    genus_of = dict(zip(meta.species, meta.genus))
    print("  held-out species:", ", ".join(heldout))

    # --- Condition B ---
    def make_B():
        split = make_split_B(split_A, heldout)
        split.to_csv(SPLIT_B, index=False)
        return split
    split_B = load_or_make(SPLIT_B, make_B, pd.read_csv)

    # Checks: held-out species never in training, and each keeps a relative there.
    train_B = split_B[split_B.set == "train"]
    assert not set(heldout) & set(train_B.species), "held-out species found in training"
    train_genera = set(train_B.species.map(genus_of))
    assert all(genus_of[s] in train_genera for s in heldout)
    counts = split_B.set.value_counts()
    print(f"  B: train {counts['train']} | test_known {counts['test_known']} "
          f"| test_unknown {counts['test_unknown']} | training species {train_B.species.nunique()}")


if __name__ == "__main__":
    main()
