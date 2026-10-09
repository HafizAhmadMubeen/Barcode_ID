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

# --- Dataset scope (decided in Phase 1, see CLAUDE.md) ---
TARGET_FAMILIES = ("Libellulidae", "Coenagrionidae")
MARKER = "COI-5P"
# European countries that have Odonata records on BOLD (as of 2026-10-09).
EUROPE_COUNTRIES = (
    "Austria", "Germany", "Italy", "Montenegro", "Poland", "Netherlands", "Norway",
    "Finland", "France", "United Kingdom", "Spain", "Greece", "Portugal", "Sweden",
    "Croatia", "Belgium", "Switzerland", "Denmark", "Czechia", "Slovakia", "Hungary",
    "Bosnia and Herzegovina", "Albania", "Bulgaria", "Romania", "Serbia", "Ukraine",
    "Belarus", "Lithuania", "North Macedonia",
)

# --- Cleaning thresholds (Phase 1) ---
MAX_N_FRACTION = 0.05     # drop sequences with more than 5% ambiguous bases (anything not A/C/G/T)
MIN_LEN, MAX_LEN = 600, 700  # keep full-length barcodes only (decided in Phase 1)
MIN_SEQS_PER_SPECIES = 3  # drop species with fewer than 3 sequences (after dedup)
# Drop a sequence if its nearest other sequence is further than this (K2P).
# Chosen in Phase 2: no sequence falls between 0.08 and 0.15, so 0.10 sits in that empty gap.
MAX_NN_DISTANCE = 0.10

# --- Train/test split (Phase 2) ---
TEST_FRACTION_A = 0.30    # Condition A: ~30% of each species' sequences are test queries

# --- Phylogenetic baseline (Phase 2) ---
DISTANCE_MODEL = "K2P"    # Kimura 2-parameter distance for the NJ tree

# --- ML settings (Phase 3) ---
KMER_SIZES = (4, 6)
# "Unknown" thresholds accept this share of known-species queries,
# calibrated by cross-validation on training data only (decided in Phase 3).
UNKNOWN_ACCEPT_RATE = 0.95

# Still open, decided in later phases (see CLAUDE.md "Still open"):
# UNKNOWN_THRESHOLD  -> Phase 3
# HELDOUT_SPECIES_FILE -> Phase 4 (saved once, never regenerated)
