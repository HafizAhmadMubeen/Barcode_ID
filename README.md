# BarcodeID

Comparing machine learning and phylogenetic methods for DNA barcode-based species identification (Odonata, COI).

See `PLANNING.md` for the full plan and `PHASES.md` for the phase checklist.

## Setup

Requires **Python 3.12 or newer** and **MAFFT** on the command line.

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
mafft --version
```

### Installing MAFFT
- **Windows:** download `mafft-7.526-win64-signed.zip` (all-in-one) from https://mafft.cbrc.jp/alignment/software/windows.html and unzip it into `tools/`, so `tools/mafft-7.526-win64-signed/mafft-win/mafft.bat` exists. No PATH change needed; `config.py` finds it there. `tools/` is git-ignored, and deleting the repo folder removes MAFFT.
- **macOS:** `brew install mafft`
- **Linux (Debian/Ubuntu):** `sudo apt install mafft`

## Running the pipeline
Run each step from the repo root, in order:

```bash
python src/download_bold.py    # raw BOLD data -> data/raw/ (skips files already downloaded)
python src/data_cleaning.py    # -> data/processed/clean.fasta, metadata.csv, results/tables/cleaning_log.csv
```

## Layout
- `config.py`: seed (`SEED = 42`), paths, thresholds
- `data/raw/`: untouched BOLD downloads
- `data/processed/`: cleaned and aligned sequences
- `src/`: one script per pipeline stage, each runnable on its own
- `results/`: tables and figures
- `report/`: write-up
