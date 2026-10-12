"""runtime.py: time both methods the same way (Phase 5).

Batch timing on the Condition A queries (236), same machine, starting from the
raw (unaligned) sequences, repeated REPEATS times; the median is reported.

  NJ: MAFFT alignment of reference + query sequences, K2P distances, NJ tree,
      identification rule. A tree method has no separate "training": the
      reference sequences must be in every tree, so all of this counts.
  BCM: MAFFT alignment of reference + query sequences, K2P distances, nearest
      match (best close match has no training either).
  ML: k-mer features of the queries + prediction + confidence, using models
      already trained by ml_classifiers.py. Training is a one-off cost and is
      reported separately (fit_seconds in results/tables/ml_timing_A.csv).

Run it on an otherwise idle machine (it takes ~15 minutes).

Output: results/tables/runtime.csv     one row per (method, repeat)

Run from the repo root (all methods, or only some, e.g. "bcm"):
    python src/runtime.py
    python src/runtime.py bcm
"""
import sys
import tempfile
import time
from io import StringIO
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from Bio import SeqIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import KMER_SIZES, PROCESSED_DIR, RESULTS_DIR, TABLES_DIR  # noqa: E402
from alignment import mafft_align  # noqa: E402
from bcm import best_match  # noqa: E402
from distances import k2p_matrix  # noqa: E402
from features import kmer_frequencies  # noqa: E402
from ml_classifiers import confidence  # noqa: E402
from phylo_baseline import build_tree, identify  # noqa: E402

REPEATS = 3


def time_nj(train, test, raw, genus_of):
    """Seconds to identify all test queries with NJ, from unaligned sequences."""
    ids = list(train.seq_id) + list(test.seq_id)
    start = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        fasta = Path(tmp) / "nj_input.fasta"
        fasta.write_text("".join(f">{i}\n{raw[i]}\n" for i in ids), encoding="utf-8")
        aligned = {r.id: str(r.seq) for r in SeqIO.parse(StringIO(mafft_align(fasta)), "fasta")}
    tree = build_tree(ids, [aligned[i] for i in ids])
    identify(tree, list(test.seq_id), dict(zip(train.seq_id, train.species)), genus_of)
    return time.time() - start


def time_ml(name, k, test, raw):
    """Seconds to identify all test queries with one trained ML model."""
    # joblib uses pickle, which can run code: only ever load models that
    # ml_classifiers.py wrote on this machine (results/models/ is git-ignored,
    # never downloaded or shared). Loading is not timed.
    model = joblib.load(RESULTS_DIR / "models" / f"{name}_k{k}.joblib")
    start = time.time()
    X = np.array([kmer_frequencies(raw[i], k) for i in test.seq_id])
    model.predict(X)
    confidence(model, name, X)
    return time.time() - start


def time_bcm(train, test, raw):
    """Seconds to identify all test queries with best close match, from unaligned sequences."""
    ids = list(train.seq_id) + list(test.seq_id)
    start = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        fasta = Path(tmp) / "bcm_input.fasta"
        fasta.write_text("".join(f">{i}\n{raw[i]}\n" for i in ids), encoding="utf-8")
        aligned = {r.id: str(r.seq) for r in SeqIO.parse(StringIO(mafft_align(fasta)), "fasta")}
    D = k2p_matrix([aligned[i] for i in ids])
    n_train = len(train)
    best_match(D[n_train:, :n_train], train.species.to_numpy())
    return time.time() - start


def main():
    """Time every method, or only the ones named on the command line
    (e.g. "python src/runtime.py bcm"); rows for other methods are kept."""
    meta = pd.read_csv(PROCESSED_DIR / "metadata.csv")
    genus_of = dict(zip(meta.species, meta.genus))
    raw = {r.id: str(r.seq) for r in SeqIO.parse(PROCESSED_DIR / "clean.fasta", "fasta")}
    split = pd.read_csv(PROCESSED_DIR / "split_A.csv")
    train, test = split[split.set == "train"], split[split.set == "test"]

    all_methods = ["nj", "bcm"] + [f"{n}_k{k}" for k in KMER_SIZES for n in ("knn", "rf")]
    chosen = sys.argv[1:] or all_methods
    rows = []
    for repeat in range(1, REPEATS + 1):
        for method in chosen:
            if method == "nj":
                seconds = time_nj(train, test, raw, genus_of)
            elif method == "bcm":
                seconds = time_bcm(train, test, raw)
            else:
                name, k = method.split("_k")
                seconds = time_ml(name, int(k), test, raw)
            rows.append({"method": method, "repeat": repeat, "seconds_total": seconds})
            print(f"repeat {repeat}: {method} {seconds:.2f}s")

    out = pd.DataFrame(rows)
    out["n_queries"] = len(test)
    out["ms_per_query"] = 1000 * out.seconds_total / len(test)
    path = TABLES_DIR / "runtime.csv"
    if path.exists() and sys.argv[1:]:                # keep earlier rows of other methods
        old = pd.read_csv(path)
        out = pd.concat([old[~old.method.isin(chosen)], out], ignore_index=True)
    out.round(4).to_csv(path, index=False)
    print("\nmedian ms per query:")
    print(out.groupby("method", sort=False).ms_per_query.median().round(2).to_string())


if __name__ == "__main__":
    main()
