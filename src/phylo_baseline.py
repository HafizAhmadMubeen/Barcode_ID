"""phylo_baseline.py: Neighbor-Joining tree identification (Condition A).

Identification rule (one sentence):
    A query is assigned the species of the training sequences in the smallest
    clade that contains the query and at least one training sequence; if that
    clade holds training sequences of more than one species, the query is
    "ambiguous" (and gets a genus if those species share one).

Method:
  1. K2P (Kimura 2-parameter) distances between all aligned sequences
     (train + test). Gaps and ambiguous bases are skipped pair by pair.
  2. One NJ tree from those distances (Biopython), rooted at its midpoint.
     Test sequences are in the tree, but their species labels are never used:
     only training labels decide a prediction.
  3. Apply the rule above to every test query.

Input:  data/processed/aligned.fasta, metadata.csv, split_A.csv
Output: results/nj_tree.nwk                       (cached; rebuilt if inputs change)
        results/tables/nj_predictions_A.csv
        results/tables/nj_timing_A.csv

Run from the repo root:
    python src/phylo_baseline.py
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from Bio import Phylo, SeqIO
from Bio.Phylo.TreeConstruction import DistanceMatrix, DistanceTreeConstructor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED_DIR, RESULTS_DIR, TABLES_DIR  # noqa: E402
from distances import k2p_matrix  # noqa: E402

ALIGNED = PROCESSED_DIR / "aligned.fasta"
SPLIT_A = PROCESSED_DIR / "split_A.csv"
TREE_A = RESULTS_DIR / "nj_tree.nwk"
AMBIGUOUS = "ambiguous"


def build_tree(ids, seqs):
    """NJ tree from K2P distances, rooted at the midpoint."""
    D = k2p_matrix(seqs)
    lower = [[float(D[i, j]) for j in range(i + 1)] for i in range(len(ids))]
    tree = DistanceTreeConstructor().nj(DistanceMatrix(list(ids), lower))
    tree.root_at_midpoint()
    return tree


def identify(tree, query_ids, train_species, genus_of):
    """Apply the smallest-clade rule to every query. Returns a list of dicts."""
    results = []
    for qid in query_ids:
        leaf = next(tree.find_clades(name=qid))
        path = [tree.root] + tree.get_path(leaf)       # root ... parent, leaf
        for clade in reversed(path[:-1]):              # walk up from the parent
            refs = [t.name for t in clade.get_terminals() if t.name in train_species]
            if refs:
                break
        species = sorted({train_species[r] for r in refs})
        genera = sorted({genus_of[s] for s in species})
        results.append({
            "query_id": qid,
            "predicted_species": species[0] if len(species) == 1 else AMBIGUOUS,
            "predicted_genus": genera[0] if len(genera) == 1 else "",
            "n_refs_in_clade": len(refs),
            "ref_species_in_clade": ";".join(species),
        })
    return results


def main():
    meta = pd.read_csv(PROCESSED_DIR / "metadata.csv")
    split = pd.read_csv(SPLIT_A)
    genus_of = dict(zip(meta.species, meta.genus))
    aligned = {r.id: str(r.seq) for r in SeqIO.parse(ALIGNED, "fasta")}

    train = split[split.set == "train"]
    test = split[split.set == "test"]
    # Leakage guards: no sequence on both sides, and no identical sequence of the
    # same species on both sides (data_cleaning.py deduplicated within species).
    assert not set(train.seq_id) & set(test.seq_id)
    train_pairs = {(sp, aligned[s]) for s, sp in zip(train.seq_id, train.species)}
    assert not any((sp, aligned[s]) in train_pairs for s, sp in zip(test.seq_id, test.species))

    # --- Tree (cached) ---
    ids = list(split.seq_id)
    newest_input = max(ALIGNED.stat().st_mtime, SPLIT_A.stat().st_mtime)
    if TREE_A.exists() and TREE_A.stat().st_mtime > newest_input:
        print(f"Using cached tree {TREE_A}")
        tree, tree_seconds = Phylo.read(TREE_A, "newick"), float("nan")
    else:
        print(f"Building NJ tree for {len(ids)} sequences (takes a few minutes)...")
        start = time.time()
        tree = build_tree(ids, [aligned[i] for i in ids])
        tree_seconds = time.time() - start
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        Phylo.write(tree, TREE_A, "newick")
        print(f"Tree built in {tree_seconds:.0f}s -> {TREE_A}")
    assert {t.name for t in tree.get_terminals()} == set(ids), "tree leaves != split"

    # --- Identify every test query ---
    start = time.time()
    train_species = dict(zip(train.seq_id, train.species))
    preds = pd.DataFrame(identify(tree, list(test.seq_id), train_species, genus_of))
    rule_seconds = time.time() - start

    preds.insert(1, "true_species", list(test.species))
    preds["correct"] = preds.predicted_species == preds.true_species
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    preds.to_csv(TABLES_DIR / "nj_predictions_A.csv", index=False)
    pd.DataFrame([{"n_sequences_in_tree": len(ids), "n_queries": len(preds),
                   "tree_build_seconds": round(tree_seconds, 1),
                   "rule_seconds_total": round(rule_seconds, 2)}]).to_csv(
        TABLES_DIR / "nj_timing_A.csv", index=False)

    # --- Summary ---
    n = len(preds)
    ambiguous = preds.predicted_species == AMBIGUOUS
    wrong = ~preds.correct & ~ambiguous
    genus_ok = preds.predicted_genus == preds.true_species.map(genus_of)
    print(f"\nCondition A, NJ ({n} queries, {preds.true_species.nunique()} species)")
    print(f"  correct species : {preds.correct.sum():4d}  ({preds.correct.mean():.1%})")
    print(f"  ambiguous       : {ambiguous.sum():4d}  ({ambiguous.mean():.1%})")
    print(f"  wrong species   : {wrong.sum():4d}  ({wrong.mean():.1%})")
    print(f"  correct genus   : {genus_ok.sum():4d}  ({genus_ok.mean():.1%})")
    print(f"  random guessing : {1 / split.species.nunique():.1%}")


if __name__ == "__main__":
    main()
