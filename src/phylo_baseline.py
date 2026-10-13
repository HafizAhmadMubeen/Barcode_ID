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
  4. Optional cut-off ("NJ tree + cut-off"): also flag a query as "unknown" if
     its tree distance to the nearest training sequence is larger than for
     95% of training sequences (calibrated inside the same tree, training
     sequences only). Plain NJ ignores these flags.

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
from config import (  # noqa: E402
    PROCESSED_DIR, RESULTS_DIR, SENSITIVITY_ACCEPT_RATES, TABLES_DIR, UNKNOWN_ACCEPT_RATE,
)
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


def nearest_training_distance(tree, train_ids):
    """Tree (patristic) distance from every leaf to its nearest OTHER training leaf.

    Used for NJ's optional 'unknown' cut-off: a query far from every reference
    on the tree is probably a species that is not in the reference set.
    Distances along the tree are depth(a) + depth(b) - 2 * depth(common ancestor).
    Instead of comparing every pair, each node remembers the two shallowest
    training leaves below it; walking up from a leaf then finds its nearest one.
    """
    depth = tree.depths()                                  # clade -> distance from root
    best = {}                                              # clade -> [(depth, name), ...] (2 smallest)
    for clade in tree.find_clades(order="postorder"):
        if clade.is_terminal():
            best[clade] = [(depth[clade], clade.name)] if clade.name in train_ids else []
        else:
            below = sorted(x for child in clade.clades for x in best[child])
            best[clade] = below[:2]
    out = {}
    for leaf in tree.get_terminals():
        nearest = np.inf
        for anc in [tree.root] + tree.get_path(leaf)[:-1]:
            for d_leaf, name in best[anc]:
                if name != leaf.name:                      # never the leaf itself
                    nearest = min(nearest, d_leaf + depth[leaf] - 2 * depth[anc])
                    break
        out[leaf.name] = nearest
    return out


def run_nj(train, queries, tree_path, cache_inputs):
    """Build (or load) an NJ tree of train + query sequences and identify the queries.

    train, queries: DataFrames with columns seq_id and species. Query species
    are only used for the leakage check, never for the prediction.
    tree_path: where the tree is cached; it is rebuilt if any file in
    cache_inputs is newer. Returns (predictions, tree_seconds, rule_seconds).
    """
    meta = pd.read_csv(PROCESSED_DIR / "metadata.csv")
    genus_of = dict(zip(meta.species, meta.genus))
    aligned = {r.id: str(r.seq) for r in SeqIO.parse(ALIGNED, "fasta")}

    # Leakage guards: no sequence on both sides, and no identical sequence of the
    # same species on both sides (data_cleaning.py deduplicated within species).
    assert not set(train.seq_id) & set(queries.seq_id)
    train_pairs = {(sp, aligned[s]) for s, sp in zip(train.seq_id, train.species)}
    assert not any((sp, aligned[s]) in train_pairs for s, sp in zip(queries.seq_id, queries.species))

    # --- Tree (cached) ---
    ids = list(train.seq_id) + list(queries.seq_id)
    newest_input = max(Path(f).stat().st_mtime for f in [ALIGNED, *cache_inputs])
    if tree_path.exists() and tree_path.stat().st_mtime > newest_input:
        print(f"Using cached tree {tree_path}")
        tree, tree_seconds = Phylo.read(tree_path, "newick"), float("nan")
    else:
        print(f"Building NJ tree for {len(ids)} sequences (takes a few minutes)...")
        start = time.time()
        tree = build_tree(ids, [aligned[i] for i in ids])
        tree_seconds = time.time() - start
        tree_path.parent.mkdir(parents=True, exist_ok=True)
        Phylo.write(tree, tree_path, "newick")
        print(f"Tree built in {tree_seconds:.0f}s -> {tree_path}")
    assert {t.name for t in tree.get_terminals()} == set(ids), "tree leaves != train + queries"

    # --- Identify every query ---
    start = time.time()
    train_species = dict(zip(train.seq_id, train.species))
    preds = pd.DataFrame(identify(tree, list(queries.seq_id), train_species, genus_of))

    # --- Optional 'unknown' cut-off ("NJ tree + cut-off", decided 2026-10-13) ---
    # Calibrated on training leaves only, inside the same tree: each training
    # sequence's tree distance to its nearest OTHER training sequence. The
    # cut-off accepts UNKNOWN_ACCEPT_RATE of these, like the ML thresholds.
    dist = nearest_training_distance(tree, set(train.seq_id))
    scores = np.array([dist[t] for t in train.seq_id])
    cutoffs = {rate: float(np.percentile(scores, 100 * rate)) for rate in SENSITIVITY_ACCEPT_RATES}
    preds["nearest_distance"] = [round(dist[q], 5) for q in queries.seq_id]
    preds["flagged_unknown"] = preds.nearest_distance > cutoffs[UNKNOWN_ACCEPT_RATE]
    for rate, cut in cutoffs.items():
        preds[f"flagged_at_{round(rate * 100)}"] = preds.nearest_distance > cut
    preds.attrs["cutoffs"] = cutoffs
    return preds, tree_seconds, time.time() - start


def main():
    meta = pd.read_csv(PROCESSED_DIR / "metadata.csv")
    split = pd.read_csv(SPLIT_A)
    genus_of = dict(zip(meta.species, meta.genus))
    train = split[split.set == "train"]
    test = split[split.set == "test"]
    ids = list(split.seq_id)
    preds, tree_seconds, rule_seconds = run_nj(train, test, TREE_A, [SPLIT_A])

    preds.insert(1, "true_species", list(test.species))
    preds["correct"] = preds.predicted_species == preds.true_species
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    preds.to_csv(TABLES_DIR / "nj_predictions_A.csv", index=False)
    pd.DataFrame([{"accept_rate": r, "tree_distance_max": round(c, 5)}
                  for r, c in preds.attrs["cutoffs"].items()]).to_csv(
        TABLES_DIR / "nj_thresholds.csv", index=False)
    # A cached tree has no build time: keep the one measured when it was built.
    timing_file = TABLES_DIR / "nj_timing_A.csv"
    if tree_seconds != tree_seconds and timing_file.exists():     # NaN check
        tree_seconds = pd.read_csv(timing_file).tree_build_seconds.iloc[0]
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
