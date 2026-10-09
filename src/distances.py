"""distances.py: pairwise genetic distances, shared by cleaning and the NJ tree."""
import numpy as np


def k2p_matrix(seqs):
    """Pairwise Kimura 2-parameter (K2P) distances for equal-length aligned sequences.

    Gaps and ambiguous bases are skipped pair by pair. Bases are coded A=0, C=1,
    G=2, T=3: A and G (even codes) are purines, C and T (odd codes) are
    pyrimidines, so a difference is a transition when both codes have the same
    parity, and a transversion otherwise.
    """
    code = {"A": 0, "C": 1, "G": 2, "T": 3}
    X = np.array([[code.get(b, -1) for b in s] for s in seqs])   # -1 = gap/ambiguous
    valid = X >= 0
    n = len(X)
    D = np.zeros((n, n))
    for i in range(n):
        both = valid[i] & valid                       # sites usable for this pair
        sites = np.maximum(both.sum(axis=1), 1)
        diff = (X[i] != X) & both
        transitions = diff & ((X[i] % 2) == (X % 2))
        P = transitions.sum(axis=1) / sites           # proportion of transitions
        Q = (diff.sum(axis=1) - transitions.sum(axis=1)) / sites   # transversions
        with np.errstate(divide="ignore", invalid="ignore"):
            D[i] = -0.5 * np.log(1 - 2 * P - Q) - 0.25 * np.log(1 - 2 * Q)
    # K2P is undefined for very distant pairs; cap those at the largest finite value.
    D[~np.isfinite(D)] = D[np.isfinite(D)].max()
    np.fill_diagonal(D, 0.0)
    return D
