# PHASES.md — BarcodeID

The project split into phases. Every phase ends with **files you can open** and **numbers you can check**. Don't start the next phase until the current one passes its validation list.

**Taxon:** Odonata (dragonflies and damselflies), COI barcodes from BOLD.
**Core question:** which method do you trust when the query species is *not* in the reference database?

---

## Phase 0 — Setup
**Goal:** repo and environment ready, taxon locked.

**Output**
- Git repo with the folder structure from PLANNING.md
- `requirements.txt`
- CLAUDE.md shows taxon = Odonata

**Validate**
- [ ] Every teammate can clone the repo
- [ ] `pip install -r requirements.txt` works in a fresh virtualenv
- [ ] `mafft --version` prints a version number
- [ ] CLAUDE.md has no "TBD" for the taxon

**Red flag:** one person's machine can run it and another's can't. Fix now, not in Phase 4.

---

## Phase 1 — Data Acquisition & Cleaning
**Goal:** one clean, labeled dataset both pipelines will use.

**Output**
- `data/raw/` — untouched BOLD download
- `data/processed/clean.fasta` + `metadata.csv` (sequence ID, species, genus, family)
- `results/tables/cleaning_log.csv` — counts after every cleaning step

**Validate**
- [ ] Cleaning log shows raw → after N-filter → after dedup → after min-sequences filter → final
- [ ] Species count is about 30–80 (if far higher, narrow to one family or region and record why in CLAUDE.md)
- [ ] Sequence count is about 500–2000
- [ ] Every kept species has at least 3 sequences (needed so a species can appear in both train and test)
- [ ] Sequence lengths are roughly 600–660 bp; none has more than 5% N
- [ ] Open the FASTA by hand: headers intact, no empty sequences
- [ ] No species name looks like a typo or duplicate ("Aeshna cyanea" vs "Aeshna cyanea ")

**Red flag:** a big drop in species count during cleaning means the filters are too strict, or BOLD labels are messy. Investigate before moving on.

---

## Phase 2 — Phylogenetic Baseline
**Goal:** given a query sequence, the tree method outputs a species.

**Output**
- `data/processed/aligned.fasta` (MAFFT)
- `results/nj_tree.nwk`
- Identification rule written in one plain-English sentence (docstring + PLANNING.md)
- `results/tables/nj_predictions_A.csv` (query ID, true species, predicted species, correct?)

**Validate**
- [ ] Alignment looks sane: same length for all rows, few gap-heavy columns
- [ ] Tree opens (iTOL or `Phylo.draw`) and you can see same-species sequences sitting together for at least 3 species you pick yourself
- [ ] Hand-check 10 predictions: you agree with the correct/incorrect label on each
- [ ] Accuracy is printed. Expect high (roughly 85–99%) on Odonata

**Red flag:** accuracy near 100% with no mistakes anywhere. Check that test sequences were not in the tree used to place them (leakage).

---

## Phase 3 — ML Classifiers
**Goal:** k-NN and Random Forest predict species from k-mer features, and can say "unknown".

**Output**
- Feature matrices for k=4 and k=6 (`.npy`)
- Saved models
- `results/tables/ml_predictions_A.csv` (same columns as the NJ file)
- The "unknown" rule written as a specific number, e.g. "flag unknown if top class probability < 0.X"

**Validate**
- [ ] Matrix shapes are correct: k=4 gives 256 columns, k=6 gives 4096 columns
- [ ] Each row of k-mer frequencies sums to 1 (or whatever normalization you documented)
- [ ] Accuracy is far above random guessing (1 / number of species)
- [ ] Same seed gives the same result twice
- [ ] The unknown threshold has a stated reason, not a guess

**Red flag:** 100% accuracy on the first run. Almost always means train and test share near-identical sequences. Re-check the split.

---

## Phase 4 — Core Experiment (Condition A and B)
**Goal:** both methods tested under full coverage and under missing species. This is the project's contribution.

**Output**
- `results/heldout_species.txt` — which species were hidden from training (fixed seed, never regenerated)
- `results/tables/condition_A.csv` and `condition_B.csv`, both methods side by side per query

**Validate**
- [ ] Held-out species list exists and is the same on every run
- [ ] Grep a held-out species name in the training data and the tree: zero hits
- [ ] Condition A uses the same test queries for NJ and ML
- [ ] In Condition B, ML without a threshold gives a known-species label to 100% of queries (this is expected and is the point)
- [ ] In Condition B, hand-inspect 5 queries: where did NJ place it, and is that a close relative (same genus)?
- [ ] At least a few species held out, ideally from different genera, not just one

**Red flag:** Condition B accuracy looks fine. A held-out species can never be "correct", so if something scores well, you're counting the wrong thing.

---

## Phase 5 — Evaluation and Plots
**Goal:** the final numbers and figures.

**Output**
- `results/tables/summary_A.csv`: accuracy, per-species precision/recall, runtime per query, for each method
- `results/tables/summary_B.csv`: false-assignment rate, correctly-flagged-unknown rate, near-relative rate
- `results/figures/`: accuracy comparison, runtime comparison, Condition A vs B drop

**Validate**
- [ ] Every number in a table can be traced to a Phase 4 file
- [ ] Runtime is measured the same way for both methods (same machine, same queries, alignment time counted for NJ)
- [ ] Figures have labeled axes, a legend, and readable text
- [ ] Threshold sensitivity: results shown for at least 3 threshold values, not just one

**Red flag:** a conclusion that depends on one lucky threshold or one lucky split. Rerun with 3 different seeds and check the winner doesn't change.

---

## Phase 6 — Report and Presentation
**Goal:** a clear answer to the core question.

**Output**
- Final report
- Slide deck

**Validate**
- [ ] Report states one data-backed conclusion in a sentence, e.g. "ML was X points more accurate under full coverage but assigned a wrong species to Y% of unknown queries; NJ placed Z% of them in the correct genus"
- [ ] Every number in the report matches a file in `results/`
- [ ] Limitations section is honest: single taxon, small dataset, one gene
- [ ] Every teammate can explain the Condition B result without notes

---

## Status Tracker

| Phase | Output you can open | Status |
|---|---|---|
| 0 Setup | repo + requirements | ☑ |
| 1 Data | clean.fasta + cleaning_log.csv | ☑ |
| 2 Phylogenetics | nj_tree.nwk + nj_predictions_A.csv | ☐ |
| 3 ML | ml_predictions_A.csv + models | ☐ |
| 4 Experiment | condition_A.csv + condition_B.csv | ☐ |
| 5 Evaluation | summary tables + figures | ☐ |
| 6 Report | report + slides | ☐ |
