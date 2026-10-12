"""evaluate.py: final numbers and figures (Phase 5).

Every number here is computed from Phase 4 files (condition_A.csv,
condition_B.csv), the replicate runs (replicates.py) and runtime.csv
(runtime.py); nothing is re-trained.

Outcome of a query whose species is NOT in the database (Condition B unknown),
for every method: exactly one of
    abstained     flagged "unknown", or answered "ambiguous"         (safe)
    near_relative named a wrong species from the correct genus       (wrong, but close)
    other_genus   named a wrong species from another genus           (dangerous)
false_assignment_rate = near_relative + other_genus (any species named).
flagged_correct_genus_rate = abstained AND the reported genus is right
    ("safe and informative", improvement #4).

Barcode-sharing species (improvement #3): species that share a BOLD BIN with
another species. Condition B is also reported without them, for all 4 seeds.

Output (results/tables/):
    summary_A.csv                accuracy, macro precision/recall, abstain rate, runtime
    per_species_A.csv            precision/recall per species and method
    summary_B.csv                unknown and known queries, every method and threshold
    replicates_summary.csv       the key numbers for seed 42 and each replicate seed
    barcode_sharing_species.csv  the barcode-sharing species and their shared BINs
    sharing_split.csv            Condition B per seed: all / without / only barcode-sharing
Figures (results/figures/):
    accuracy_A.png, runtime.png, condition_B_outcomes.png, A_vs_B.png,
    threshold_curve.png, barcode_sharing.png, loso_per_species.png

Run from the repo root:
    python src/evaluate.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                     # write files only, no window
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import precision_recall_fscore_support  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (  # noqa: E402
    FIGURES_DIR, PROCESSED_DIR, REPLICATE_SEEDS, RESULTS_DIR, SEED, SENSITIVITY_ACCEPT_RATES,
    TABLES_DIR, UNKNOWN_ACCEPT_RATE,
)

ML = ["knn_k4", "knn_k6", "rf_k4", "rf_k6"]
METHODS = ["nj"] + ML + ["bcm"]
LABEL = {"nj": "NJ tree", "knn_k4": "k-NN (k=4)", "knn_k6": "k-NN (k=6)",
         "rf_k4": "RF (k=4)", "rf_k6": "RF (k=6)", "bcm": "Best close match"}
MAIN_RATE = round(UNKNOWN_ACCEPT_RATE * 100)

# Colours: one per method family (validated palette slots 1-3 + violet, checked
# all-pairs with the dataviz validator), status colours for outcomes
# (safe / close / dangerous, always with a text label).
FAMILY_COLOR = {"nj": "#2a78d6", "knn": "#eb6834", "rf": "#1baf7a", "bcm": "#4a3aa7"}
MAIN_SETTING = {"nj": "rule", "bcm": "Meier cut-off"}   # ML main setting: "accept 95%"
OUTCOME_COLOR = {"abstained_genus": "#0ca30c", "abstained_other": "#8fd18f",
                 "near_relative": "#fab219", "other_genus": "#d03b3b"}
OUTCOME_LABEL = {"abstained_genus": "Flagged unknown + correct genus (safe, informative)",
                 "abstained_other": "Flagged unknown, no correct genus (safe)",
                 "near_relative": "Wrong species, correct genus",
                 "other_genus": "Wrong species, wrong genus (dangerous)"}
SUBSET_COLOR = {"all": "#a8a69c", "excluding barcode-sharing": "#52514e"}
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e1e0d9", "#fcfcfb"


def family(method):
    return method.split("_")[0]


def main_setting(method):
    return MAIN_SETTING.get(method, f"accept {MAIN_RATE}%")


def answer(df, method, setting=None):
    """Each query's answer: a species name, 'unknown' (flagged) or 'ambiguous'.

    setting=None: no cut-off. "main": the method's main cut-off (ML: accept 95%;
    BCM: Meier's rule). 90/95/99: the calibrated cut-off accepting that share of
    known queries. "fixed_2": BCM's fixed 2% cut-off. NJ ignores the setting.
    """
    if method == "nj":
        return df.nj_predicted_species
    predicted = df[f"{method}_predicted_species"]
    if setting is None:
        return predicted
    if setting == "main":
        column = "flagged_unknown"
    elif isinstance(setting, int):
        column = f"flagged_at_{setting}"
    else:
        column = f"flagged_{setting}"
    return predicted.where(~df[f"{method}_{column}"], "unknown")


def genus_given(df, method):
    """The genus each method reports alongside its answer (improvement #4).

    NJ: the shared genus of the clade's species. ML/BCM: nearest or most
    probable genus, reported even when the species is flagged "unknown".
    """
    return df[f"{method}_predicted_genus"].fillna("")


def outcome_rates(df, ans, genus=None):
    """Shares of abstained / near_relative / other_genus for unknown queries.

    With genus given, also the share that abstained AND named the correct genus
    ("safe and informative": e.g. "unknown species, probably a Sympetrum").
    """
    abstained = ans.isin(["unknown", "ambiguous"])
    same_genus = ans.str.split().str[0] == df.true_genus
    out = {"abstained": abstained.mean(),
           "near_relative": (~abstained & same_genus).mean(),
           "other_genus": (~abstained & ~same_genus).mean()}
    if genus is not None:
        out["abstained_genus"] = (abstained & (genus == df.true_genus)).mean()
    return out


def barcode_sharing_species(meta):
    """Species whose specimens share a BOLD BIN with another species (improvement #3).

    BINs are BOLD's own sequence clusters, so this list does not depend on any
    of our methods. Returns a DataFrame: species, bins, shares_bin_with.
    """
    with_bin = meta[meta.bin.notna() & (meta.bin != "")]
    rows = []
    for species, g in with_bin.groupby("species"):
        bins = set(g.bin)
        others = sorted(set(with_bin[with_bin.bin.isin(bins)].species) - {species})
        if others:
            rows.append({"species": species, "bins": ";".join(sorted(bins)),
                         "shares_bin_with": ";".join(others)})
    return pd.DataFrame(rows)


def sharing_split(b, sharing, seed):
    """Condition B results for all held-out species, without and only the
    barcode-sharing ones (main setting of each method)."""
    rows = []
    subsets = {"all": lambda s: s == s,
               "excluding barcode-sharing": lambda s: ~s.isin(sharing),
               "barcode-sharing only": lambda s: s.isin(sharing)}
    for name, keep in subsets.items():
        unk = b[(b.query_type == "unknown") & keep(b.true_species)]
        kno = b[(b.query_type == "known") & keep(b.true_species)]
        if unk.empty:
            continue
        for m in METHODS:
            o = outcome_rates(unk, answer(unk, m, "main"), genus_given(unk, m))
            rows.append({"seed": seed, "subset": name, "method": m,
                         "unknown_false_assignment_rate": o["near_relative"] + o["other_genus"],
                         "unknown_flagged_rate": o["abstained"],
                         "unknown_flagged_correct_genus_rate": o["abstained_genus"],
                         "known_accuracy": (answer(kno, m, "main") == kno.true_species).mean(),
                         "n_unknown": len(unk), "n_unknown_species": unk.true_species.nunique(),
                         "n_known": len(kno)})
    return rows


def summarize_A(a, runtime):
    rows, per_species = [], []
    species = sorted(a.true_species.unique())
    for m in METHODS:
        ans = answer(a, m, "main")
        raw = answer(a, m)                          # no cut-off
        p, r, _, support = precision_recall_fscore_support(
            a.true_species, raw, labels=species, zero_division=0)
        per_species += [{"method": m, "species": s, "precision": round(pi, 3),
                         "recall": round(ri, 3), "n_queries": int(n)}
                        for s, pi, ri, n in zip(species, p, r, support)]
        rows.append({
            "method": m,
            "accuracy": (raw == a.true_species).mean(),
            "accuracy_with_unknown_flag": (ans == a.true_species).mean(),
            "abstain_rate": ans.isin(["unknown", "ambiguous"]).mean(),
            "macro_precision": p.mean(), "macro_recall": r.mean(),
            "runtime_ms_per_query": runtime.get(m, np.nan),
        })
    return pd.DataFrame(rows).round(4), pd.DataFrame(per_species)


def summarize_B(b):
    unk, kno = b[b.query_type == "unknown"], b[b.query_type == "known"]
    rates = [round(x * 100) for x in SENSITIVITY_ACCEPT_RATES]
    settings = ([("nj", None, "rule")]
                + [(m, None, "no threshold") for m in ML + ["bcm"]]
                + [(m, rate, f"accept {rate}%") for m in ML + ["bcm"] for rate in rates]
                + [("bcm", "main", "Meier cut-off"), ("bcm", "fixed_2", "fixed 2%")])
    rows = []
    for m, rate, setting in settings:
        u_ans, k_ans = answer(unk, m, rate), answer(kno, m, rate)
        o = outcome_rates(unk, u_ans, genus_given(unk, m))
        rows.append({
            "method": m, "setting": setting,
            "unknown_flagged_rate": o["abstained"],
            "unknown_flagged_correct_genus_rate": o["abstained_genus"],
            "unknown_false_assignment_rate": o["near_relative"] + o["other_genus"],
            "unknown_near_relative_rate": o["near_relative"],
            "unknown_other_genus_rate": o["other_genus"],
            "known_accuracy": (k_ans == kno.true_species).mean(),
            "known_flagged_rate": k_ans.isin(["unknown", "ambiguous"]).mean(),
            "n_unknown": len(unk), "n_known": len(kno),
        })
    return pd.DataFrame(rows).round(4)


def key_numbers(a, b, seed):
    """The headline numbers for one run (used to compare seeds)."""
    unk = b[b.query_type == "unknown"]
    row = {"seed": seed}
    for m in METHODS:
        row[f"A_acc_{m}"] = (answer(a, m) == a.true_species).mean()
        o = outcome_rates(unk, answer(unk, m, "main"), genus_given(unk, m))
        row[f"B_false_assign_{m}"] = o["near_relative"] + o["other_genus"]
        row[f"B_safe_genus_{m}"] = o["abstained_genus"]
    # Winners; ties are listed together ("knn_k4/knn_k6").
    best_a = max(row[f"A_acc_{m}"] for m in METHODS)
    best_b = min(row[f"B_false_assign_{m}"] for m in METHODS)
    row["A_best"] = "/".join(m for m in METHODS if np.isclose(row[f"A_acc_{m}"], best_a))
    row["B_safest"] = "/".join(m for m in METHODS if np.isclose(row[f"B_false_assign_{m}"], best_b))
    return row


# ---------------------------------------------------------------- figures --
def style(ax, title, xlabel=None, ylabel=None):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    if xlabel:
        ax.set_xlabel(xlabel, color=INK_2)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK_2)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=INK_2)
    ax.set_axisbelow(True)


def save(fig, name):
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout(rect=(0, 0.04, 1, 1))     # leave room for a footnote
    fig.savefig(FIGURES_DIR / name, dpi=200)
    plt.close(fig)


def fig_accuracy(summary_A, reps):
    fig, ax = plt.subplots(figsize=(7, 4))
    style(ax, "Condition A: correct species on known queries", ylabel="Accuracy (%)")
    x = np.arange(len(METHODS))
    acc = [100 * summary_A.set_index("method").accuracy[m] for m in METHODS]
    ax.bar(x, acc, width=0.6, color=[FAMILY_COLOR[family(m)] for m in METHODS],
           edgecolor=SURFACE, linewidth=2)
    for i, m in enumerate(METHODS):
        seeds = [100 * r[f"A_acc_{m}"] for r in reps if r["seed"] != SEED]
        ax.scatter([i] * len(seeds), seeds, s=36, color=INK, edgecolor=SURFACE, linewidth=1.5,
                   zorder=3, label="Replicate seeds" if i == 0 else None)
        # Value at the foot of the bar, clear of the replicate dots.
        ax.text(i, 80.6, f"{acc[i]:.1f}%", ha="center", va="bottom", color=INK, fontsize=9)
    ax.set_xticks(x, [LABEL[m] for m in METHODS])
    ax.set_ylim(80, 100)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.legend(frameon=False, loc="upper right", fontsize=9)
    fig.text(0.01, 0.01, "Bars: seed 42 (main run); dots: replicate seeds. Axis starts at 80%.",
             fontsize=8, color=INK_2)
    save(fig, "accuracy_A.png")


def fig_runtime(summary_A):
    s = summary_A.set_index("method").runtime_ms_per_query
    methods = [m for m in METHODS if not np.isnan(s[m])]     # only methods that were timed
    if not methods:
        return
    fig, ax = plt.subplots(figsize=(7, 0.6 * len(methods) + 0.8))
    style(ax, "Runtime per query (Condition A, 236 queries, median of 3 runs)",
          xlabel="Milliseconds per query (log scale)")
    y = np.arange(len(methods))[::-1]
    ax.barh(y, [s[m] for m in methods], height=0.6, color=[FAMILY_COLOR[family(m)] for m in methods],
            edgecolor=SURFACE, linewidth=2)
    for yi, m in zip(y, methods):
        ax.text(s[m] * 1.15, yi, f"{s[m]:,.0f} ms" if s[m] >= 100 else f"{s[m]:.1f} ms",
                va="center", color=INK, fontsize=9)
    ax.set_yticks(y, [LABEL[m] for m in methods])
    ax.set_xscale("log")
    ax.set_xlim(right=s.max() * 8)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    fig.text(0.01, 0.01, "NJ: alignment, distances, tree, rule. Best close match: alignment, "
             "distances. ML: k-mers + prediction (no training).", fontsize=7.5, color=INK_2)
    save(fig, "runtime.png")


def fig_outcomes(summary_B):
    rows = ([("nj", "rule", "NJ tree")]
            + [(m, "no threshold", f"{LABEL[m]}, no threshold") for m in ML]
            + [("bcm", "no threshold", "Best close match, no cut-off")]
            + [(m, f"accept {MAIN_RATE}%", f"{LABEL[m]}, threshold") for m in ML]
            + [("bcm", "Meier cut-off", "Best close match, Meier cut-off")])
    s = summary_B.set_index(["method", "setting"])
    fig, ax = plt.subplots(figsize=(8, 5.6))
    style(ax, "Condition B: answers for species NOT in the database",
          xlabel="Share of unknown queries (%)")
    y = np.arange(len(rows))[::-1]
    for yi, (m, setting, _) in zip(y, rows):
        left = 0
        r = s.loc[(m, setting)]
        parts = {"abstained_genus": r.unknown_flagged_correct_genus_rate,
                 "abstained_other": r.unknown_flagged_rate - r.unknown_flagged_correct_genus_rate,
                 "near_relative": r.unknown_near_relative_rate,
                 "other_genus": r.unknown_other_genus_rate}
        for key, val in parts.items():
            ax.barh(yi, 100 * val, left=left, height=0.62, color=OUTCOME_COLOR[key],
                    edgecolor=SURFACE, linewidth=2, label=OUTCOME_LABEL[key] if yi == y[0] else None)
            if val >= 0.08:
                ax.text(left + 100 * val / 2, yi, f"{100 * val:.0f}%", ha="center", va="center",
                        color=INK, fontsize=8)
            left += 100 * val
    ax.set_yticks(y, [label for _, _, label in rows])
    ax.set_xlim(0, 100)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.14), ncol=2, fontsize=8)
    save(fig, "condition_B_outcomes.png")


def fig_A_vs_B(summary_A, summary_B):
    sa = summary_A.set_index("method")
    sb = summary_B.set_index(["method", "setting"])
    fig, ax = plt.subplots(figsize=(7, 4.4))
    style(ax, "From full to incomplete coverage", ylabel="Share of queries (%)")
    ends = {}
    for m in METHODS:
        setting = main_setting(m)
        a = 100 * sa.accuracy_with_unknown_flag[m]
        b = 100 * sb.loc[(m, setting)].unknown_flagged_rate
        color = FAMILY_COLOR[family(m)]
        ax.plot([0, 1], [a, b], color=color, linewidth=2, marker="o", markersize=8,
                markeredgecolor=SURFACE, markeredgewidth=2)
        ends.setdefault(round(b), []).append(m)
    # One label per end value (methods with the same value share it), pushed
    # apart vertically so labels never overlap.
    last_y = None
    for value in sorted(ends, reverse=True):
        y = value if last_y is None else min(value, last_y - 6)
        names = " / ".join(LABEL[m] for m in ends[value])
        ax.text(1.04, y, f"{names}  {value}%", va="center", color=INK, fontsize=9)
        last_y = y
    ax.set_xticks([0, 1], ["Condition A\nknown species: correct answer",
                           "Condition B\nunknown species: safely flagged"])
    ax.set_xlim(-0.15, 1.9)
    ax.set_ylim(0, 105)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    fig.text(0.01, 0.01, "ML with its calibrated threshold (accept 95% of knowns); NJ with its rule; "
             "best close match with Meier's cut-off.", fontsize=8, color=INK_2)
    save(fig, "A_vs_B.png")


def fig_threshold_curve(b, summary_B):
    unk, kno = b[b.query_type == "unknown"], b[b.query_type == "known"]
    fig, ax = plt.subplots(figsize=(7, 4.6))
    style(ax, "Threshold sensitivity (Condition B)",
          xlabel="Known queries wrongly flagged unknown (%)",
          ylabel="Unknown queries caught (%)")
    for m in ML + ["bcm"]:
        # Confidence: higher = more sure. For BCM it is minus the nearest distance.
        conf = (lambda d: -d["bcm_nearest_distance"]) if m == "bcm" else (lambda d: d[f"{m}_confidence"])
        cu, ck = conf(unk).to_numpy(), conf(kno).to_numpy()
        cuts = np.unique(np.concatenate([cu, ck, [np.inf]]))
        xs = [100 * (ck < c).mean() for c in cuts]
        ys = [100 * (cu < c).mean() for c in cuts]
        marker = {"bcm": "^"}.get(m, "o" if m.endswith("k4") else "s")
        ax.plot(xs, ys, color=FAMILY_COLOR[family(m)], linewidth=2, label=LABEL[m],
                linestyle=(0, (4, 2)) if m.endswith("k4") else "-")
        # Markers: the calibrated cut-offs (90/95/99%), read from the flag columns.
        flags = [f"{m}_flagged_at_{round(x * 100)}" for x in SENSITIVITY_ACCEPT_RATES]
        if m == "bcm":
            flags.append("bcm_flagged_unknown")            # Meier's cut-off
        for col in flags:
            ax.scatter(100 * kno[col].mean(), 100 * unk[col].mean(), s=40, marker=marker,
                       color=FAMILY_COLOR[family(m)], edgecolor=SURFACE, linewidth=2, zorder=3)
    nj = summary_B.set_index("method").loc["nj"]
    ax.scatter(100 * nj.known_flagged_rate, 100 * nj.unknown_flagged_rate, s=70, marker="D",
               color=FAMILY_COLOR["nj"], edgecolor=SURFACE, linewidth=2, zorder=4, label="NJ tree (no threshold)")
    ax.set_xlim(0, 30)
    ax.set_ylim(0, 102)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    fig.text(0.01, 0.01, "Lines: every possible cut-off. Markers: calibrated 90%, 95%, 99% "
             "(best close match also: Meier's cut-off).", fontsize=8, color=INK_2)
    save(fig, "threshold_curve.png")


def fig_sharing(split):
    """Wrongly named unknowns, all held-out species vs without barcode-sharing ones."""
    d = split[split.subset.isin(SUBSET_COLOR)]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    style(ax, "Condition B: unknown species wrongly named, with and without barcode sharing",
          ylabel="Unknown queries wrongly named (%)")
    x = np.arange(len(METHODS))
    width = 0.36
    for j, (subset, color) in enumerate(SUBSET_COLOR.items()):
        g = d[d.subset == subset]
        means = [100 * g[g.method == m].unknown_false_assignment_rate.mean() for m in METHODS]
        xs = x + (j - 0.5) * width
        ax.bar(xs, means, width=width, color=color, edgecolor=SURFACE, linewidth=2,
               label=f"{subset.capitalize()} held-out species (mean of 4 seeds)")
        for xi, m in zip(xs, METHODS):
            seeds = 100 * g[g.method == m].unknown_false_assignment_rate.to_numpy()
            ax.scatter([xi] * len(seeds), seeds, s=22, color=INK, edgecolor=SURFACE,
                       linewidth=1.2, zorder=3)
    ax.set_xticks(x, [LABEL[m].replace(" (", "\n(") for m in METHODS])
    ax.set_ylim(0, 102)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.legend(frameon=False, loc="upper right", fontsize=8)
    fig.text(0.01, 0.01, "Barcode-sharing = shares a BOLD BIN with another species (10 species). "
             "Dots: the 4 seeds. Main cut-off for each method.", fontsize=7.5, color=INK_2)
    save(fig, "barcode_sharing.png")


def fig_loso():
    """Per-species chart for leave-one-species-out (improvement #5): how often
    each method wrongly named a species that was missing from the database."""
    path = TABLES_DIR / "loso_per_species.csv"
    if not path.exists():
        print("loso_per_species.csv missing: run src/leave_one_species_out.py (figure skipped)")
        return
    p = pd.read_csv(path)
    shown = ["nj", "knn_k6", "rf_k6", "bcm"]
    w = p.pivot(index="species", columns="method", values="false_assignment_rate")
    sharing = p.groupby("species").barcode_sharing.first()
    # Barcode-sharing species at the bottom; within each group, sort by NJ then name.
    order = sorted(w.index, key=lambda s: (sharing[s], -w.loc[s, "nj"], s))
    fig, ax = plt.subplots(figsize=(7.5, 10.5))
    style(ax, "Every species held out once: how often it was wrongly named",
          xlabel="Queries of the held-out species given a wrong species name (%)")
    y = np.arange(len(order))[::-1]
    n_clean = int((~sharing[order]).sum())
    ax.axhspan(-0.5, len(order) - n_clean - 0.5, color="#f0efec", zorder=0)   # barcode-sharing band
    offsets = {"nj": 0.24, "knn_k6": 0.08, "rf_k6": -0.08, "bcm": -0.24}
    markers = {"nj": "D", "knn_k6": "o", "rf_k6": "s", "bcm": "^"}
    for m in shown:
        ax.scatter(100 * w.loc[order, m], y + offsets[m], s=34, marker=markers[m],
                   color=FAMILY_COLOR[family(m)], edgecolor=SURFACE, linewidth=1.2, zorder=3,
                   label=LABEL[m])
    labels = [f"{s} *" if sharing[s] else s for s in order]
    ax.set_yticks(y, labels, fontsize=8, style="italic")
    ax.set_ylim(-0.7, len(order) - 0.3)
    ax.set_xlim(-3, 103)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.4, -0.05), ncol=4, fontsize=8)
    fig.text(0.01, 0.01, "* shaded rows: barcode-sharing species (share a BOLD BIN with another "
             "species). Main cut-off for each method.", fontsize=7.5, color=INK_2)
    save(fig, "loso_per_species.png")


def main():
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    a = pd.read_csv(TABLES_DIR / "condition_A.csv")
    b = pd.read_csv(TABLES_DIR / "condition_B.csv")
    meta = pd.read_csv(PROCESSED_DIR / "metadata.csv")
    sharing_table = barcode_sharing_species(meta)
    sharing_table.to_csv(TABLES_DIR / "barcode_sharing_species.csv", index=False)
    sharing = set(sharing_table.species)

    runtime = {}
    if (TABLES_DIR / "runtime.csv").exists():
        runtime = pd.read_csv(TABLES_DIR / "runtime.csv").groupby("method").ms_per_query.median().to_dict()
    else:
        print("runtime.csv missing: run src/runtime.py first (runtime column left empty)")

    summary_A, per_species = summarize_A(a, runtime)
    summary_B = summarize_B(b)
    summary_A.to_csv(TABLES_DIR / "summary_A.csv", index=False)
    per_species.to_csv(TABLES_DIR / "per_species_A.csv", index=False)
    summary_B.to_csv(TABLES_DIR / "summary_B.csv", index=False)

    reps = [key_numbers(a, b, SEED)]
    split_rows = sharing_split(b, sharing, SEED)
    for seed in REPLICATE_SEEDS:
        d = RESULTS_DIR / "replicates" / f"seed_{seed}"
        if (d / "condition_B.csv").exists():
            b_seed = pd.read_csv(d / "condition_B.csv")
            reps.append(key_numbers(pd.read_csv(d / "condition_A.csv"), b_seed, seed))
            split_rows += sharing_split(b_seed, sharing, seed)
        else:
            print(f"replicate seed {seed} missing: run src/replicates.py")
    pd.DataFrame(reps).round(4).to_csv(TABLES_DIR / "replicates_summary.csv", index=False)
    split = pd.DataFrame(split_rows).round(4)
    split.to_csv(TABLES_DIR / "sharing_split.csv", index=False)

    fig_accuracy(summary_A, reps)
    fig_runtime(summary_A)
    fig_outcomes(summary_B)
    fig_A_vs_B(summary_A, summary_B)
    fig_threshold_curve(b, summary_B)
    fig_sharing(split)
    fig_loso()

    pd.set_option("display.width", 200)
    print("barcode-sharing species (BIN):", ", ".join(sorted(sharing)))
    view = split.groupby(["subset", "method"], sort=False)[
        ["unknown_false_assignment_rate", "unknown_flagged_correct_genus_rate"]].agg(["min", "max"])
    print("\nCondition B unknowns across 4 seeds (min-max), main cut-offs:\n", view.round(3).to_string())
    print("summary_A:\n", summary_A.to_string(index=False))
    print("\nsummary_B:\n", summary_B.drop(columns=["n_unknown", "n_known"]).to_string(index=False))
    print("\nreplicates:\n", pd.DataFrame(reps).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
