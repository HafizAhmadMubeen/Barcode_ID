"""significance.py: confidence intervals and significance tests (improvement #1).

Are the differences between methods real, or could they be noise?

Confidence intervals: species-level (cluster) bootstrap. Queries of the same
species are not independent (in Condition B, 139 unknown queries come from only
8 species), so we resample SPECIES with replacement and keep all their queries.
2000 resamples, SEED 42, 95% percentile intervals.

Significance tests: exact McNemar test on the same queries for 13 method pairs
(NJ vs each ML variant, k-NN vs RF at k=4 and k=6, best close match vs NJ, k-NN
and RF at k=6), Holm-corrected within each
outcome. McNemar treats queries as independent, which overstates certainty, so
each pair also gets the difference in rates with a species-bootstrap interval:
if the two disagree, trust the interval.

Outcomes compared (ML at its main 95% threshold, NJ with its rule):
    A_correct        Condition A, the correct species named (no threshold, as in summary_A)
    B_unknown_named  Condition B unknown queries given a species name (lower = safer)
    B_known_correct  Condition B known queries, correct species with the threshold on

Input:  results/tables/condition_A.csv, condition_B.csv
Output: results/tables/confidence_intervals.csv, significance_tests.csv

Run from the repo root:
    python src/significance.py
"""
import sys
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import SEED, TABLES_DIR, UNKNOWN_ACCEPT_RATE  # noqa: E402

METHODS = ["nj", "knn_k4", "knn_k6", "rf_k4", "rf_k6", "bcm", "njc"]
PAIRS = [("nj", "knn_k4"), ("nj", "knn_k6"), ("nj", "rf_k4"), ("nj", "rf_k6"),
         ("knn_k4", "rf_k4"), ("knn_k6", "rf_k6"),
         # Best close match (improvement #2): is ML better than a plain distance rule?
         ("bcm", "nj"), ("bcm", "knn_k6"), ("bcm", "rf_k6"),
         # NJ tree + cut-off (decided 2026-10-13): does a fair cut-off close the gap?
         ("njc", "nj"), ("njc", "knn_k6"), ("njc", "rf_k6"), ("njc", "bcm")]
N_BOOT = 2000
RATE = round(UNKNOWN_ACCEPT_RATE * 100)


def outcome_columns(a, b):
    """One 0/1 column per (outcome, method), plus the species of each query."""
    out = {}
    unk, kno = b[b.query_type == "unknown"], b[b.query_type == "known"]
    for m in METHODS:
        if m == "nj":
            a_ans = a.nj_predicted_species
            u_named = unk.nj_predicted_species != "ambiguous"
            k_ans = kno.nj_predicted_species
        elif m == "bcm":                           # main rule: Meier's cut-off
            a_ans = a.bcm_predicted_species
            u_named = ~unk.bcm_flagged_unknown & (unk.bcm_predicted_species != "ambiguous")
            k_ans = kno.bcm_predicted_species.where(~kno.bcm_flagged_unknown, "unknown")
        elif m == "njc":                           # NJ answers + tree-distance cut-off
            a_ans = a.nj_predicted_species         # Condition A without cut-off, like ML
            u_named = ~unk.njc_flagged_unknown & (unk.nj_predicted_species != "ambiguous")
            k_ans = kno.nj_predicted_species.where(~kno.njc_flagged_unknown, "unknown")
        else:
            a_ans = a[f"{m}_predicted_species"]
            u_named = ~unk[f"{m}_flagged_at_{RATE}"]
            k_ans = kno[f"{m}_predicted_species"].where(~kno[f"{m}_flagged_at_{RATE}"], "unknown")
        out[("A_correct", m)] = pd.DataFrame({"species": a.true_species, "hit": (a_ans == a.true_species).astype(int)})
        out[("B_unknown_named", m)] = pd.DataFrame({"species": unk.true_species, "hit": u_named.astype(int)})
        out[("B_known_correct", m)] = pd.DataFrame({"species": kno.true_species, "hit": (k_ans == kno.true_species).astype(int)})
    return out


def species_bootstrap(frames, rng):
    """Bootstrap the mean of one or more aligned 0/1 columns, resampling species.

    frames: list of DataFrames with the SAME rows (same queries, same order),
    columns species and hit. Returns an (N_BOOT, len(frames)) array of means.
    """
    species = frames[0].species.to_numpy()
    groups = {s: np.where(species == s)[0] for s in np.unique(species)}
    names = list(groups)
    hits = np.column_stack([f.hit.to_numpy() for f in frames])
    means = np.empty((N_BOOT, len(frames)))
    for i in range(N_BOOT):
        drawn = rng.choice(len(names), size=len(names), replace=True)
        rows = np.concatenate([groups[names[j]] for j in drawn])
        means[i] = hits[rows].mean(axis=0)
    return means


def mcnemar_exact(x, y):
    """Exact two-sided McNemar p-value for paired 0/1 outcomes x and y."""
    b = int(((x == 1) & (y == 0)).sum())     # only the first method succeeded
    c = int(((x == 0) & (y == 1)).sum())     # only the second method succeeded
    n = b + c
    if n == 0:
        return b, c, 1.0
    tail = sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return b, c, min(1.0, 2 * tail)


def holm(pvalues):
    """Holm-Bonferroni adjusted p-values (same order as the input)."""
    p = np.asarray(pvalues)
    order = np.argsort(p)
    adjusted = np.empty_like(p)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (len(p) - rank) * p[idx])
        adjusted[idx] = min(1.0, running)
    return adjusted


def main():
    a = pd.read_csv(TABLES_DIR / "condition_A.csv")
    b = pd.read_csv(TABLES_DIR / "condition_B.csv")
    cols = outcome_columns(a, b)
    rng = np.random.default_rng(SEED)

    # --- Confidence intervals for every (outcome, method) ---
    ci_rows = []
    for (outcome, m), f in cols.items():
        boot = species_bootstrap([f], rng)[:, 0]
        ci_rows.append({"outcome": outcome, "method": m, "estimate": f.hit.mean(),
                        "ci_low": np.percentile(boot, 2.5), "ci_high": np.percentile(boot, 97.5),
                        "n_queries": len(f), "n_species": f.species.nunique()})
    ci = pd.DataFrame(ci_rows).round(4)
    ci.to_csv(TABLES_DIR / "confidence_intervals.csv", index=False)

    # --- Paired tests ---
    test_rows = []
    for outcome in ["A_correct", "B_unknown_named", "B_known_correct"]:
        rows = []
        for m1, m2 in PAIRS:
            f1, f2 = cols[(outcome, m1)], cols[(outcome, m2)]
            b_, c_, p = mcnemar_exact(f1.hit.to_numpy(), f2.hit.to_numpy())
            boot = species_bootstrap([f1, f2], rng)
            diff = boot[:, 0] - boot[:, 1]
            rows.append({"outcome": outcome, "method_1": m1, "method_2": m2,
                         "rate_1": f1.hit.mean(), "rate_2": f2.hit.mean(),
                         "difference": f1.hit.mean() - f2.hit.mean(),
                         "diff_ci_low": np.percentile(diff, 2.5), "diff_ci_high": np.percentile(diff, 97.5),
                         "only_1_hit": b_, "only_2_hit": c_, "mcnemar_p": p})
        for row, p_adj in zip(rows, holm([r["mcnemar_p"] for r in rows])):
            row["holm_p"] = p_adj
            row["mcnemar_significant"] = p_adj < 0.05
            row["ci_excludes_zero"] = row["diff_ci_low"] > 0 or row["diff_ci_high"] < 0
        test_rows += rows
    tests = pd.DataFrame(test_rows).round(4)
    tests.to_csv(TABLES_DIR / "significance_tests.csv", index=False)

    # --- Print ---
    pd.set_option("display.width", 200)
    print("95% confidence intervals (species bootstrap, 2000 resamples)")
    for outcome, g in ci.groupby("outcome", sort=False):
        print(f"\n{outcome} ({g.n_queries.iloc[0]} queries from {g.n_species.iloc[0]} species)")
        for r in g.itertuples():
            print(f"   {r.method:7s} {r.estimate:6.1%}   [{r.ci_low:6.1%} - {r.ci_high:6.1%}]")
    print("\nPaired comparisons (difference = method_1 - method_2)")
    for r in tests.itertuples():
        print(f"   {r.outcome:16s} {r.method_1:6s} vs {r.method_2:6s}  diff {r.difference:+6.1%} "
              f"[{r.diff_ci_low:+6.1%}, {r.diff_ci_high:+6.1%}]  only1/only2 {r.only_1_hit:3d}/{r.only_2_hit:<3d} "
              f"Holm p={r.holm_p:.4f}  {'SIG' if r.mcnemar_significant else '   '} "
              f"{'CI excl. 0' if r.ci_excludes_zero else ''}")


if __name__ == "__main__":
    main()
