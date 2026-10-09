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
- [ ] **Confidence threshold for "unknown" flagging** — needs a concrete number/method (e.g., max class probability < threshold) decided during Phase 3, not left implicit.

Record final answers here once decided — don't leave open items unresolved past their phase.

---

## 4. Data

- **Source:** BOLD Systems Public Data Portal (https://www.boldsystems.org) — free, no login.
- **Format:** FASTA sequences (COI gene, ~650bp) + taxonomy metadata (species, genus, family).
- **Taxon:** Odonata (dragonflies and damselflies) — full European set or a narrower family/region, to be confirmed in Phase 1 against actual BOLD numbers. Target ~30–80 species, ~500–2000 sequences total.
- **Split strategy:** split by species (not by sequence) into train/test to avoid data leakage — a sequence from a species must not appear in both train and test just because a different individual of that species is in train.
- **Condition B specifically requires:** a subset of species held out entirely from training (not just from test-within-species), so the pipeline needs two distinct split functions, not one.

---

## 5. Methodology Detail

### 5.1 Data acquisition & cleaning
- Download FASTA + taxonomy metadata for the chosen taxon from BOLD.
- Remove sequences with excessive Ns/gaps (define a hard threshold, e.g., >5% ambiguous bases).
- Trim to a consistent barcode region/length window.
- Deduplicate identical sequences.
- Log sequence/species counts before and after each cleaning step (for traceability and for the report's data section).
- **As implemented (Phase 1):** `src/download_bold.py` fetches all European Odonata per country; `src/data_cleaning.py` keeps COI-5P from the two target families, drops unnamed records and cross-genus BIN misIDs, trims sequences over 700 bp to the barcode region, drops >5% non-ACGT, keeps 600–700 bp, dedups within species, and drops species with <3 sequences. Result: 784 sequences, 45 species.

### 5.2 Phylogenetic baseline
- Multiple sequence alignment via MAFFT.
- Build a Neighbor-Joining tree (Biopython `Phylo`).
- Optional stretch: Maximum Likelihood tree (IQ-TREE or RAxML) as a stronger baseline.
- **Identification rule:** a query is "identified" as species X if it clusters within X's clade on the tree. This rule needs a precise, code-implementable definition (e.g., nearest-neighbor leaf by tree distance, or smallest enclosing clade with a single species label) — decide and document this exactly, since "clusters within" is otherwise unfalsifiable.

### 5.3 ML classifiers
- Feature extraction: k-mer frequency vectors, k=4 and k=6 (compare both).
- Models: k-NN and Random Forest as primary; SVM as stretch.
- Standard scikit-learn train/test workflow, fixed random seed everywhere.

### 5.4 Core experiment — the actual contribution
- **Condition A (full coverage):** every test species has training examples. Standard supervised evaluation.
- **Condition B (incomplete coverage):** entirely hold out some species from training.
  - NJ/ML trees: does the held-out query land near a taxonomically related species on the tree (a sensible "closest relative" answer), or does it get placed nonsensically?
  - ML classifiers: does the model confidently (and wrongly) assign a known species label, or — if using a confidence threshold — correctly flag "not in database"?

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
│   ├── alignment.py
│   ├── phylo_baseline.py
│   ├── features.py
│   ├── ml_classifiers.py
│   ├── experiment_full.py
│   ├── experiment_incomplete.py
│   └── evaluate.py
├── notebooks/
├── results/
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

- [ ] Overall accuracy (ML vs. phylogenetic), full coverage
- [ ] Per-species precision/recall
- [ ] Runtime per query (both methods)
- [ ] Incomplete coverage: false-positive species assignment rate
- [ ] Incomplete coverage: correctly-flagged-unknown rate

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
