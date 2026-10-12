"""leave_one_species_out.py: hold out every species once (improvement #5).

Condition B with 8 held-out species gave very different numbers depending on
WHICH species were drawn. Here every eligible species is held out on its own:

    for each species S in a genus with at least 2 species (39 species):
        training = Condition A training sequences, minus S
        queries  = ALL sequences of S  (all "unknown": S is not in training)
        run NJ (own tree), k-NN, RF (retrained, thresholds re-calibrated)
        and best close match, exactly as in Condition B

So each species gets its own result, and the overall numbers do not depend
on a lucky or unlucky draw. Progress is saved after every species: if the run
stops, re-running continues where it left off. Takes ~1-1.5 hours.

Output: results/loso/loso_predictions.csv   one row per (held-out species, query)
        results/loso/trees/                 cached NJ trees
        results/loso/models/                (git-ignored)
        results/tables/loso_per_species.csv results per species and method
        results/tables/loso_overall.csv     overall results per method

Run from the repo root:
    python src/leave_one_species_out.py
"""
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED_DIR, RESULTS_DIR, TABLES_DIR  # noqa: E402
from bcm import run_bcm  # noqa: E402
from evaluate import METHODS, answer, barcode_sharing_species, genus_given, outcome_rates  # noqa: E402
from experiment_full import to_wide  # noqa: E402
from ml_classifiers import run_ml  # noqa: E402
from phylo_baseline import run_nj  # noqa: E402

LOSO_DIR = RESULTS_DIR / "loso"
PREDICTIONS = LOSO_DIR / "loso_predictions.csv"
SPLIT_A = PROCESSED_DIR / "split_A.csv"


def eligible_species(meta):
    """Species whose genus has at least one other species (so a relative stays in training)."""
    n_per_genus = meta.groupby("genus").species.nunique()
    multi = n_per_genus[n_per_genus >= 2].index
    return sorted(meta[meta.genus.isin(multi)].species.unique())


def run_one(species, split, genus_of):
    """Hold out one species and run all methods on its sequences."""
    train = split[(split.set == "train") & (split.species != species)]
    queries = split[split.species == species]               # train + test sequences of S
    assert species not in set(train.species), "held-out species in training"

    slug = species.replace(" ", "_")
    nj, _, _ = run_nj(train, queries, LOSO_DIR / "trees" / f"{slug}.nwk", [SPLIT_A])
    ml, _, _ = run_ml(list(train.seq_id), train.species, list(queries.seq_id), LOSO_DIR / "models")
    bcm, _ = run_bcm(train, queries)
    truth = pd.DataFrame({"query_id": queries.seq_id, "true_species": queries.species,
                          "true_genus": queries.species.map(genus_of), "query_type": "unknown"})
    wide = to_wide(nj, ml, truth, bcm)
    wide.insert(0, "held_out_species", species)
    return wide


def summarize(preds, sharing):
    """Per-species and overall results for every method (main cut-offs)."""
    rows = []
    for species, g in preds.groupby("held_out_species"):
        for m in METHODS:
            o = outcome_rates(g, answer(g, m, "main"), genus_given(g, m))
            rows.append({"species": species, "genus": species.split()[0],
                         "barcode_sharing": species in sharing, "method": m, "n_queries": len(g),
                         "false_assignment_rate": o["near_relative"] + o["other_genus"],
                         "other_genus_rate": o["other_genus"],
                         "flagged_rate": o["abstained"],
                         "flagged_correct_genus_rate": o["abstained_genus"]})
    per_species = pd.DataFrame(rows)

    overall = []
    subsets = {"all": per_species.barcode_sharing | ~per_species.barcode_sharing,
               "excluding barcode-sharing": ~per_species.barcode_sharing,
               "barcode-sharing only": per_species.barcode_sharing}
    for name, keep in subsets.items():
        for m in METHODS:
            g = per_species[keep & (per_species.method == m)]
            overall.append({
                "subset": name, "method": m, "n_species": len(g),
                # Each species counts equally (a species with 60 sequences does
                # not outweigh one with 3).
                "false_assignment_rate_mean": g.false_assignment_rate.mean(),
                "flagged_correct_genus_rate_mean": g.flagged_correct_genus_rate.mean(),
                "other_genus_rate_mean": g.other_genus_rate.mean(),
                # Share of species where the method never named a wrong species.
                "species_never_wrongly_named": (g.false_assignment_rate == 0).mean(),
                # Share of species where it named a wrong species for over half the queries.
                "species_mostly_wrongly_named": (g.false_assignment_rate > 0.5).mean(),
            })
    return per_species.round(4), pd.DataFrame(overall).round(4)


def main():
    meta = pd.read_csv(PROCESSED_DIR / "metadata.csv")
    genus_of = dict(zip(meta.species, meta.genus))
    split = pd.read_csv(SPLIT_A)
    species_list = eligible_species(meta)
    LOSO_DIR.mkdir(parents=True, exist_ok=True)

    done = pd.read_csv(PREDICTIONS) if PREDICTIONS.exists() else pd.DataFrame()
    finished = set(done.held_out_species) if not done.empty else set()
    print(f"{len(species_list)} eligible species, {len(finished)} already done", flush=True)

    for i, species in enumerate(species_list, start=1):
        if species in finished:
            continue
        start = time.time()
        wide = run_one(species, split, genus_of)
        done = pd.concat([done, wide], ignore_index=True)
        done.to_csv(PREDICTIONS, index=False)               # save progress every species
        named = (wide.nj_predicted_species != "ambiguous").mean()
        print(f"[{i:2d}/{len(species_list)}] {species:26s} {len(wide):3d} queries | "
              f"NJ named {named:5.0%} | kNN k6 named {(~wide.knn_k6_flagged_unknown).mean():5.0%} | "
              f"{time.time() - start:4.0f}s", flush=True)

    sharing = set(barcode_sharing_species(meta).species)
    per_species, overall = summarize(done, sharing)
    per_species.to_csv(TABLES_DIR / "loso_per_species.csv", index=False)
    overall.to_csv(TABLES_DIR / "loso_overall.csv", index=False)
    pd.set_option("display.width", 200)
    print("\nOverall (each species counts equally, main cut-offs):")
    print(overall.to_string(index=False))


if __name__ == "__main__":
    main()
