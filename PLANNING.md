# PLANNING.md — BarcodeID

Full project plan for **BarcodeID: Comparing Machine Learning and Phylogenetic Methods for DNA Barcode-Based Species Identification**. This is the single source of truth for what we're building, how, and who does what. Keep it updated as decisions are made — don't let CLAUDE.md, this file, and PHASES.md drift out of sync.

---

## 1. Project Goal

Determine whether machine learning classifiers can match or outperform traditional phylogenetic methods (Neighbor-Joining, optionally Maximum Likelihood) at identifying species from short DNA barcode sequences (COI gene) — and characterize **when** each approach wins, especially under incomplete reference-database coverage.

**The real contribution:** not "ML got X% accuracy" but a head-to-head comparison under two conditions — full species coverage vs. incomplete coverage (querying a species never seen in training). This is what makes the project defensible as a finding rather than a benchmark exercise.

---

## 2. Team & Ownership

| Role | Primary Ownership |
|---|---|
| Data & Phylogenetics | Data acquisition & cleaning, phylogenetic baseline (Phases 1–2) |
| ML | Feature extraction & ML classifiers (Phase 3) |
| Experiments & Report | Experimentation, evaluation & report writing (Phases 4–6) |

Assign these three roles among the team however works best. Ownership is primary responsibility, not exclusive — everyone reviews everyone's output before it's marked done, since Phase 4 (the core experiment) depends on Phases 2 and 3 both being correct.

---

## 3. Open Decisions

- [x] **Taxonomic group — Odonata (dragonflies and damselflies).** Chosen based on a published reference-library study: 103 of 145 recorded European species covered (71%), from 697 COI-barcoded specimens across 274 localities in 16 countries, with >88% of included species reliably identifiable from their barcode alone (Blackman et al., *Coverage and quality of DNA barcode references for Central and Northern European Odonata*, PeerJ, 2021: https://peerj.com/articles/11192/). Sequence count (~697) sits in our target range; species count (103) runs slightly above the 30–80 target — **Phase 1's first task is to pull the actual current BOLD Odonata record count and decide whether to use the full set or narrow to one family (e.g., Libellulidae or Coenagrionidae) or one region.**
- [x] **Final scope — Libellulidae + Coenagrionidae, Europe** (decided 2026-10-09). Live BOLD counts showed all Odonata at 2,434 species and European Odonata at 120 species / 3,273 records, both over target. The two families from 30 European countries give about 55 species (50 with ≥3 records) and about 1,850 records before cleaning. Country list is in `config.py`; full counts are in CLAUDE.md.
- [ ] **ML/Maximum Likelihood stretch goal** — decide after Phase 2/3 are stable whether we have time for IQ-TREE/RAxML ML trees and/or SVM, or whether NJ + k-NN/RF is the full scope.
- [x] **Confidence threshold for "unknown" flagging** (decided Phase 3): thresholds accept 95% of known-species queries, calibrated by cross-validation on training data only. RF: top class probability below the cut-off; k-NN: distance to the nearest training sequence above the cut-off. Phase 5 adds a sensitivity analysis over at least 3 thresholds.

Record final answers here once decided — don't leave open items unresolved past their phase.

---

## 4. Data

- **Source:** BOLD Systems Public Data Portal (https://www.boldsystems.org) — free, no login.
- **Format:** FASTA sequences (COI gene, ~650bp) + taxonomy metadata (species, genus, family).
- **Taxon:** Odonata (dragonflies and damselflies) — full European set or a narrower family/region, to be confirmed in Phase 1 against actual BOLD numbers. Target ~30–80 species, ~500–2000 sequences total.
- **Split strategy:** Condition A splits *within* each species (70/30, `data/processed/split_A.csv`), so every test species has training sequences; leakage is prevented by deduplicating identical sequences within species, so no identical sequence of a species sits on both sides. Condition B additionally holds whole species out of training (Phase 4).
- **Condition B specifically requires:** a subset of species held out entirely from training (not just from test-within-species), so the pipeline needs two distinct split functions, not one.

---

## 5. Methodology Detail

### 5.1 Data acquisition & cleaning
- Download FASTA + taxonomy metadata for the chosen taxon from BOLD.
- Remove sequences with excessive Ns/gaps (define a hard threshold, e.g., >5% ambiguous bases).
- Trim to a consistent barcode region/length window.
- Deduplicate identical sequences.
- Log sequence/species counts before and after each cleaning step (for traceability and for the report's data section).
- **As implemented (Phase 1):** `src/download_bold.py` fetches all European Odonata per country; `src/data_cleaning.py` keeps COI-5P from the two target families, drops unnamed records and cross-genus BIN misIDs, trims sequences over 700 bp to the barcode region, drops >5% non-ACGT, keeps 600–700 bp, dedups within species, drops outliers with no relative within 0.10 K2P (added in Phase 2), and drops species with <3 sequences. Result: 779 sequences, 45 species.

### 5.2 Phylogenetic baseline
- Multiple sequence alignment via MAFFT.
- Build a Neighbor-Joining tree (Biopython `Phylo`).
- Optional stretch: Maximum Likelihood tree (IQ-TREE or RAxML) as a stronger baseline.
- **Identification rule (decided Phase 2):** a query is assigned the species of the training sequences in the smallest clade that contains the query and at least one training sequence; if that clade holds training sequences of more than one species, the query is "ambiguous" (and gets a genus if those species share one).
- **As implemented (Phase 2):** K2P distances (`src/distances.py`), one Biopython NJ tree of all training sequences plus all test queries (query labels never used), midpoint-rooted, cached at `results/nj_tree.nwk`. Condition A: 92.4% correct, 3.4% ambiguous, 4.2% wrong species, 100% correct genus (236 queries).

### 5.3 ML classifiers
- Feature extraction: k-mer frequency vectors, k=4 and k=6 (compare both).
- Models: k-NN and Random Forest as primary; SVM as stretch.
- Standard scikit-learn train/test workflow, fixed random seed everywhere.
- **As implemented (Phase 3):** `src/features.py` (k-mer frequency matrices), `src/ml_classifiers.py` (k-NN k=5 distance-weighted; RF 500 trees, balanced class weights; chosen by training-only CV). Condition A: k-NN 93.2% (k=4 and k=6), RF 91.5% (k=4) / 92.4% (k=6).

### 5.4 Core experiment — the actual contribution
- **Condition A (full coverage):** every test species has training examples. Standard supervised evaluation.
- **Condition B (incomplete coverage):** entirely hold out some species from training.
  - NJ/ML trees: does the held-out query land near a taxonomically related species on the tree (a sensible "closest relative" answer), or does it get placed nonsensically?
  - ML classifiers: does the model confidently (and wrongly) assign a known species label, or — if using a confidence threshold — correctly flag "not in database"?
- **As implemented (Phase 4):** `src/splits.py` holds out one random species per multi-species genus (8 species, `results/heldout_species.txt`) and writes `split_B.csv`; `src/experiment_full.py` and `src/experiment_incomplete.py` write `condition_A.csv` and `condition_B.csv` (one row per query, all methods side by side). First results on the 139 unknown queries: NJ named a wrong species 66.9% of the time but always within the correct genus; k-NN with threshold flagged 100% as unknown, RF 88.5–91.4%. Full numbers in CLAUDE.md.

### 5.5 Evaluation
- Overall accuracy (ML vs. phylogenetic), Condition A.
- Per-species precision/recall.
- Runtime per query (ML expected to be much faster — worth quantifying, not just claiming).
- Condition B: false-positive species assignment rate vs. correct "unknown" flag rate.

### 5.6 Write-up
- Central claim to test: "ML wins with full data, phylogenetics degrades more gracefully with gaps" (or whatever the data actually shows — don't force this conclusion if results say otherwise).

---

## 6. Tech Stack

- **Language:** Python 3
- **Core libraries:** Biopython, scikit-learn, pandas, numpy, matplotlib/seaborn
- **Alignment:** MAFFT (CLI)
- **Tree building:** Biopython NJ (built-in) — IQ-TREE/RAxML if ML tree stretch goal is taken
- **Environment:** virtualenv, dependencies pinned in `requirements.txt`

## 7. Repo Structure

```
barcodeid/
├── CLAUDE.md
├── PLANNING.md                # this file
├── PHASES.md                  # phase breakdown + verification checkpoints
├── README.md
├── requirements.txt
├── data/
│   ├── raw/                   # untouched BOLD downloads
│   └── processed/             # cleaned/aligned sequences
├── src/
│   ├── download_bold.py       # fetch raw BOLD TSVs (all European Odonata) into data/raw/
│   ├── data_cleaning.py
│   ├── alignment.py           # MAFFT alignment
│   ├── distances.py           # K2P distance matrix (shared)
│   ├── splits.py              # saved train/test splits (Condition A, later B)
│   ├── phylo_baseline.py
│   ├── features.py
│   ├── ml_classifiers.py
│   ├── experiment_full.py
│   ├── experiment_incomplete.py
│   ├── replicates.py          # robustness: re-run with seeds 1, 2, 3
│   ├── runtime.py             # timing benchmark (NJ vs ML, same queries)
│   └── evaluate.py
├── notebooks/
├── results/
│   ├── models/                # saved ML models (git-ignored, re-created by ml_classifiers.py)
│   ├── figures/
│   └── tables/
└── report/
```

## 8. Coding Conventions

- Separate, independently runnable scripts per pipeline stage — no monolithic notebook.
- Cache expensive steps (alignment, tree building) to disk; don't recompute every run.
- Fixed random seed everywhere splits or ML models are involved.
- Log dataset sizes (species count, sequence count) at every cleaning/filtering step.
- Every script should run standalone from a cached intermediate file, so one person's failure doesn't block the other two.

## 9. Evaluation Metrics Checklist

- [x] Overall accuracy (ML vs. phylogenetic), full coverage
- [x] Per-species precision/recall
- [x] Runtime per query (both methods)
- [x] Incomplete coverage: false-positive species assignment rate
- [x] Incomplete coverage: correctly-flagged-unknown rate

## 10. Risks / Things That Could Derail This

- **BOLD data quality:** public records can have missing/wrong taxonomy labels — budget real time for cleaning, don't assume the download is ready to use.
- **NJ "clustering" definition being vague:** if not pinned down precisely (see 5.2), the phylogenetic side of the comparison isn't reproducible or gradeable.
- **Confidence threshold for ML "unknown" flagging:** picked arbitrarily, this can make ML look artificially better or worse in Condition B — needs justification, maybe a small sensitivity analysis across thresholds.
- **Scope creep:** ML/SVM and Maximum Likelihood trees are explicitly stretch goals — don't start them before Conditions A and B work end-to-end with the simpler primary methods.

## 11. Reference Papers

- AI-Powered Biodiversity Assessment: Species Classification via DNA Barcoding and Deep Learning (2024): https://www.research.unipd.it/bitstream/11577/3541838/2/technologies-12-00240-v2.pdf
- A New Method for Species Identification via Protein-Coding and Non-Coding DNA Barcodes by Combining Machine Learning with Bioinformatic Methods: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3282726/
- BOLD Systems database overview: https://pmc.ncbi.nlm.nih.gov/articles/PMC11070247
- Coverage and quality of DNA barcode references for Central and Northern European Odonata (2021), source for taxon-choice numbers: https://peerj.com/articles/11192/
