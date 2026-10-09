"""features.py: k-mer frequency features for the ML classifiers.

A k-mer is a run of k consecutive bases. For each sequence we count every
possible k-mer (4^k of them: 256 for k=4, 4096 for k=6) and divide by the total,
so each row is a frequency profile that sums to 1. Windows containing a gap or
an ambiguous base (anything not A/C/G/T) are skipped.

Uses the unaligned sequences (clean.fasta): k-mer methods need no alignment.
Features use only the sequence, never the species label, so building them for
all sequences at once leaks nothing.

Output (data/processed/):
    kmer_k4.npy, kmer_k6.npy   one row per sequence, in the order of kmer_ids.txt
    kmer_ids.txt               sequence ID of each row

Run from the repo root:
    python src/features.py
"""
import sys
from itertools import product
from pathlib import Path

import numpy as np
from Bio import SeqIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import KMER_SIZES, PROCESSED_DIR  # noqa: E402

CODE = {"A": 0, "C": 1, "G": 2, "T": 3}


def kmer_names(k):
    """Column names in matrix order: AAAA, AAAC, ..., TTTT."""
    return ["".join(p) for p in product("ACGT", repeat=k)]


def kmer_frequencies(seq, k):
    """Frequency of each of the 4^k k-mers in one sequence (sums to 1)."""
    x = np.array([CODE.get(b, -1) for b in seq])
    counts = np.zeros(4 ** k)
    for start in range(len(x) - k + 1):
        window = x[start:start + k]
        if (window >= 0).all():
            # Read the window as a base-4 number: AAAA=0, AAAC=1, ..., TTTT=4^k-1
            counts[int(window @ (4 ** np.arange(k - 1, -1, -1)))] += 1
    return counts / counts.sum()


def main():
    records = list(SeqIO.parse(PROCESSED_DIR / "clean.fasta", "fasta"))
    ids = [r.id for r in records]
    (PROCESSED_DIR / "kmer_ids.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")

    for k in KMER_SIZES:
        X = np.array([kmer_frequencies(str(r.seq), k) for r in records])
        np.save(PROCESSED_DIR / f"kmer_k{k}.npy", X)
        row_sums = X.sum(axis=1)
        print(f"k={k}: shape {X.shape} (expected {len(ids)} x {4 ** k}) | "
              f"row sums min {row_sums.min():.6f} max {row_sums.max():.6f} | "
              f"non-zero k-mers per row (median): {int(np.median((X > 0).sum(axis=1)))}")
        assert X.shape == (len(ids), 4 ** k)
        assert np.allclose(row_sums, 1.0)


if __name__ == "__main__":
    main()
