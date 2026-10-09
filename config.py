"""Shared settings for every BarcodeID script.

Import from here instead of hard-coding paths or seeds:
    from config import SEED, RAW_DIR
"""
from pathlib import Path

# One fixed random seed for all splits and models (see CLAUDE.md).
SEED = 42

# --- Paths (all relative to the repo root, so the repo works on any machine) ---
ROOT = Path(__file__).resolve().parent

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"              # untouched BOLD downloads
PROCESSED_DIR = DATA_DIR / "processed"  # cleaned and aligned sequences

RESULTS_DIR = ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
TABLES_DIR = RESULTS_DIR / "tables"

REPORT_DIR = ROOT / "report"

# --- External tools ---
# MAFFT is kept inside the repo (tools/, not in git) so deleting the folder removes it.
# Teammates without this folder fall back to a "mafft" on their PATH (brew/apt install).
_LOCAL_MAFFT = ROOT / "tools" / "mafft-7.526-win64-signed" / "mafft-win" / "mafft.bat"
MAFFT_CMD = str(_LOCAL_MAFFT) if _LOCAL_MAFFT.exists() else "mafft"

# --- Cleaning thresholds (Phase 1) ---
MAX_N_FRACTION = 0.05     # drop sequences with more than 5% ambiguous bases
MIN_SEQS_PER_SPECIES = 3  # drop species with fewer than 3 sequences

# --- ML settings (Phase 3) ---
KMER_SIZES = (4, 6)

# Still open, decided in later phases (see CLAUDE.md "Still open"):
# UNKNOWN_THRESHOLD  -> Phase 3
# HELDOUT_SPECIES_FILE -> Phase 4 (saved once, never regenerated)
