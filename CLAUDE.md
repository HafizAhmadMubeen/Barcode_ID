# CLAUDE.md — BarcodeID

Context for Claude Code. Read this at the start of every session, and update it when decisions are made.

## Project
**BarcodeID: Comparing Machine Learning and Phylogenetic Methods for DNA Barcode-Based Species Identification**

University bioinformatics research project, team of three. Deliverables: working code, results tables and figures, a written report, and a short presentation.

## Core question
Which method should you trust when the query species is **not** in the reference database: a phylogenetic tree (Neighbor-Joining) or a machine learning classifier?

Accuracy on known species is not the point. The contribution is the comparison under two conditions:
- **Condition A, full coverage:** every test species also appears in training.
- **Condition B, incomplete coverage:** some species are held out of training entirely, then queried as "unknown". Measure whether each method fails safely (flags unknown, or places the query near a close relative) or fails dangerously (confidently names the wrong species).

## Decided
- **Taxon:** Odonata (dragonflies and damselflies).
- **Marker:** COI barcode, about 650 bp.
- **Source:** BOLD Systems public data (https://www.boldsystems.org), FASTA plus taxonomy metadata.
- **Reason for taxon:** a 2021 study covered 103 of 145 European Odonata species from 697 COI specimens, and over 88% of species were identifiable from the barcode alone (https://peerj.com/articles/11192/). These are published-study numbers, so the live BOLD count may differ.
- **Target size:** about 30–80 species, 500–2000 sequences.
- **Final scope (decided 2026-10-09, Phase 1):** families **Libellulidae + Coenagrionidae**, specimens from **Europe** (the 30 European countries with Odonata records on BOLD, listed in `config.py` as `EUROPE_COUNTRIES`; Russia and Turkey excluded). Reason: full Odonata is far too large, and two families with many multi-species genera (Sympetrum, Ischnura, Coenagrion) give Condition B real close relatives.
- **Real BOLD counts (v5 portal summary API, 2026-10-09, before cleaning):** all Odonata 2,434 species / 25,245 COI-5P records; European Odonata 120 species (105 with ≥3 records, 3,273 records); European Libellulidae 30 species (26 with ≥3, 810 records); European Coenagrionidae 25 species (24 with ≥3, 1,043 records). Chosen scope: about 55 species, 50 with ≥3 records, about 1,850 records.

## Still open
- Exact rule that turns a tree position into a species prediction (Phase 2).
- Confidence threshold for flagging "unknown" in ML (Phase 3).
- Which species to hold out for Condition B (Phase 4).

## Pipeline
1. **Data:** download, remove sequences with more than 5% N, trim to a consistent region, deduplicate, drop species with fewer than 3 sequences, split into train/test.
2. **Phylogenetic baseline:** MAFFT alignment, Neighbor-Joining tree (Biopython `Phylo`), explicit identification rule.
3. **ML:** k-mer frequency features (k=4 and k=6), k-NN and Random Forest. SVM and Maximum Likelihood trees are stretch goals only, and only after A and B work end to end.
4. **Experiment:** Condition A and Condition B, both methods, same queries.
5. **Evaluation:** accuracy, per-species precision/recall, runtime per query, and for Condition B the false-assignment rate and correctly-flagged-unknown rate.
6. **Report.**

The phase-by-phase checklist is in `PHASES.md`. The full plan is in `PLANNING.md`.

## How to work (rules for Claude Code)
- **One phase at a time.** Do the phase asked for, run the checks in `PHASES.md`, report the results, then stop. Don't start the next phase.
- **Show evidence.** After each phase, print the numbers the validation list asks for (counts, shapes, accuracy) so a human can verify them. Don't just say "done".
- **Never invent data or results.** If a download fails, say so and ask. Don't generate fake sequences or placeholder numbers.
- **Guard against leakage.** Split by species where required. Check that no held-out species appears in training data or in the tree. A perfect score is a warning sign: investigate it before reporting it.
- **Reproducibility.** One fixed random seed everywhere (`SEED = 42` in a shared config). Held-out species list is saved to a file and never regenerated.
- **Cache expensive steps** (alignment, tree) to disk. Check `data/processed/` before re-downloading or recomputing.
- **Separate scripts per stage.** Each runs on its own from cached files. No single giant notebook.
- **Log counts** (species, sequences) at every filter so data loss is traceable.
- **Keep code simple and commented.** The team has to explain it in a presentation.
- **Don't put personal names** in code, docs, or reports. Use roles if needed.
- **Ask before** adding a new dependency, changing a decided item above, or doing stretch goals.

## BOLD download note
If the BOLD API or website can't be reached from the sandbox, stop and tell the user. They will download the FASTA and metadata manually into `data/raw/`. Don't work around it with unofficial mirrors.

## Tech stack
Python 3, Biopython, scikit-learn, pandas, numpy, matplotlib/seaborn, MAFFT (command line). Virtualenv, pinned `requirements.txt`.

## Repo structure
```
barcodeid/
├── CLAUDE.md
├── PLANNING.md
├── PHASES.md
├── README.md
├── requirements.txt
├── config.py                  # SEED, thresholds, paths
├── data/
│   ├── raw/                   # untouched BOLD files
│   └── processed/             # cleaned and aligned sequences
├── src/
│   ├── data_cleaning.py
│   ├── alignment.py
│   ├── phylo_baseline.py
│   ├── features.py
│   ├── ml_classifiers.py
│   ├── experiment_full.py         # Condition A
│   ├── experiment_incomplete.py   # Condition B
│   └── evaluate.py
├── notebooks/
├── results/
│   ├── figures/
│   └── tables/
└── report/
```

## Status
- [x] Phase 0: taxon chosen (Odonata)
- [x] Phase 0: repo and environment set up
- [ ] Phase 1: data acquisition and cleaning
- [ ] Phase 2: phylogenetic baseline
- [ ] Phase 3: ML classifiers
- [ ] Phase 4: Condition A and B experiment
- [ ] Phase 5: evaluation and plots
- [ ] Phase 6: report and presentation

Update this list as phases pass their validation.

## References
- Coverage and quality of DNA barcode references for Central and Northern European Odonata (2021): https://peerj.com/articles/11192/
- AI-Powered Biodiversity Assessment: Species Classification via DNA Barcoding and Deep Learning (2024): https://www.research.unipd.it/bitstream/11577/3541838/2/technologies-12-00240-v2.pdf
- A New Method for Species Identification via Protein-Coding and Non-Coding DNA Barcodes by Combining Machine Learning with Bioinformatic Methods: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3282726/
- BOLD Systems database overview: https://pmc.ncbi.nlm.nih.gov/articles/PMC11070247
