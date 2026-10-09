"""data_cleaning.py: turn the raw BOLD downloads into one clean, labelled dataset.

Reads data/raw/bold_Odonata_*.tsv (from download_bold.py) and applies these
filters in order, logging the sequence and species count after each one:

  1. COI-5P marker only (the standard ~658 bp barcode region)
  2. target families only (config.TARGET_FAMILIES)
  3. identified to species (drop records with no species name)
  4. cross-genus misIDs: drop a record if most records in its BIN belong to a
     species from a different genus (clear labelling errors). Barcode sharing
     within a genus is real biology and is kept.
  5. trim overlong sequences (> 700 bp) down to the barcode region: each is
     locally aligned to its family's reference barcode (the most common
     658 bp sequence in that family) and only the matching stretch is kept
  6. ambiguous bases: drop sequences with > 5% non-ACGT characters
  7. length: keep 600-700 bp
  8. deduplicate: keep one copy of each identical sequence per species
  9. drop species with fewer than 3 sequences

Output:
  data/processed/clean.fasta            header: ">PROCESSID Genus species"
  data/processed/metadata.csv           seq_id, species, genus, family, bin, country, length, trimmed
  data/processed/barcode_references.fasta   the reference barcode used for trimming, per family
  results/tables/cleaning_log.csv       counts after every step
  results/tables/removed_misids.csv     records dropped in step 4, with the reason

Run from the repo root:
    python src/data_cleaning.py
"""
import sys
from pathlib import Path

import pandas as pd
from Bio.Align import PairwiseAligner

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (  # noqa: E402
    MARKER, MAX_LEN, MAX_N_FRACTION, MIN_LEN, MIN_SEQS_PER_SPECIES,
    PROCESSED_DIR, RAW_DIR, TABLES_DIR, TARGET_FAMILIES,
)

log = []  # one row per cleaning step


def record(step, description, df):
    """Log the sequence and species count after a cleaning step."""
    n_seq, n_sp = len(df), df.loc[df.species != "", "species"].nunique()
    removed = log[-1]["n_sequences"] - n_seq if log else 0
    log.append({"step": step, "description": description,
                "n_sequences": n_seq, "n_species": n_sp, "removed": removed})
    print(f"{step:22s} {n_seq:6d} sequences  {n_sp:4d} species  (-{removed})")


def load_raw():
    """Read every raw TSV as plain text (no type guessing, empty cells stay "")."""
    files = sorted(RAW_DIR.glob("bold_Odonata_*.tsv"))
    if not files:
        sys.exit(f"No raw files in {RAW_DIR}. Run src/download_bold.py first.")
    frames = [pd.read_csv(f, sep="\t", dtype=str, keep_default_na=False) for f in files]
    return pd.concat(frames, ignore_index=True)


def bin_majority_species(coi):
    """For each BIN, the species with the most records (None if there is a tie).

    Computed on all named COI-5P Odonata records, not just our families, so a
    BIN's majority reflects as much evidence as possible.
    """
    named = coi[(coi.species != "") & (coi.bin_uri != "")]
    majority = {}
    for bin_uri, species in named.groupby("bin_uri").species:
        counts = species.value_counts()
        tie = len(counts) > 1 and counts.iloc[0] == counts.iloc[1]
        majority[bin_uri] = None if tie else counts.index[0]
    return majority


def family_references(df):
    """Reference barcode per family: its most common sequence of exactly 658 bp
    (the standard COI barcode length). Sorted first so ties break the same way."""
    full = df[df.seq.str.len() == 658].sort_values("processid")
    return {fam: g.seq.value_counts().index[0] for fam, g in full.groupby("family")}


def trim_to_reference(seq, reference, aligner):
    """Cut a long sequence down to the stretch that aligns to the reference barcode."""
    alignment = aligner.align(seq, reference)[0]
    blocks = alignment.aligned[0]            # aligned (start, end) blocks in seq
    return seq[blocks[0][0]:blocks[-1][1]]


def main():
    raw = load_raw()
    record("0_raw", "all downloaded rows (all markers, all families)", raw)

    df = raw[raw.marker_code == MARKER]
    coi_all = df  # kept for the BIN majority vote in step 4
    record("1_marker", f"marker_code == {MARKER}", df)

    df = df[df.family.isin(TARGET_FAMILIES)]
    record("2_family", f"family in {', '.join(TARGET_FAMILIES)}", df)

    df = df[df.species != ""]
    record("3_species_named", "identified to species", df)

    # Step 4: cross-genus misIDs.
    majority = bin_majority_species(coi_all)
    maj = df.bin_uri.map(majority)
    misid = maj.notna() & (maj.str.split().str[0] != df.genus)
    removed = df[misid].assign(bin_majority_species=maj[misid])
    df = df[~misid]
    record("4_cross_genus_misid", "BIN majority species is in a different genus", df)

    # Step 5: remove BOLD's alignment gaps, then trim overlong sequences.
    df = df.assign(seq=df.nuc.str.upper().str.replace("-", "", regex=False))
    references = family_references(df)
    aligner = PairwiseAligner(mode="local", match_score=2, mismatch_score=-1,
                              open_gap_score=-5, extend_gap_score=-1)
    too_long = df.seq.str.len() > MAX_LEN
    df = df.assign(trimmed=too_long)
    df.loc[too_long, "seq"] = [trim_to_reference(seq, references[fam], aligner)
                               for seq, fam in zip(df.seq[too_long], df.family[too_long])]
    record("5_trim_long", f"{too_long.sum()} sequences > {MAX_LEN} bp trimmed to the barcode", df)

    # Step 6: ambiguous-base filter on the final (trimmed) sequence.
    df = df.assign(length=df.seq.str.len())
    ambiguous = df.seq.str.count(r"[^ACGT]") / df.length.clip(lower=1)
    df = df[(df.length > 0) & (ambiguous <= MAX_N_FRACTION)]
    record("6_ambiguous_bases", f"<= {MAX_N_FRACTION:.0%} non-ACGT bases", df)

    df = df[df.length.between(MIN_LEN, MAX_LEN)]
    record("7_length", f"{MIN_LEN}-{MAX_LEN} bp", df)

    # Step 8: sort first so the same copy is always the one kept.
    df = df.sort_values("processid").drop_duplicates(["species", "seq"])
    record("8_dedup", "one copy of each identical sequence per species", df)

    counts = df.species.value_counts()
    df = df[df.species.isin(counts[counts >= MIN_SEQS_PER_SPECIES].index)]
    record("9_min_seqs", f">= {MIN_SEQS_PER_SPECIES} sequences per species", df)

    # --- Write outputs ---
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    df = df.sort_values(["family", "species", "processid"])

    with open(PROCESSED_DIR / "clean.fasta", "w", encoding="utf-8", newline="\n") as f:
        for row in df.itertuples():
            f.write(f">{row.processid} {row.species}\n{row.seq}\n")

    meta = df.rename(columns={"processid": "seq_id", "bin_uri": "bin", "country/ocean": "country"})
    meta[["seq_id", "species", "genus", "family", "bin", "country", "length", "trimmed"]].to_csv(
        PROCESSED_DIR / "metadata.csv", index=False)
    with open(PROCESSED_DIR / "barcode_references.fasta", "w", encoding="utf-8", newline="\n") as f:
        for fam, ref in references.items():
            f.write(f">{fam}_reference_658bp\n{ref}\n")
    pd.DataFrame(log).to_csv(TABLES_DIR / "cleaning_log.csv", index=False)
    removed[["processid", "species", "genus", "bin_uri", "bin_majority_species"]].to_csv(
        TABLES_DIR / "removed_misids.csv", index=False)

    print(f"\nFinal: {len(df)} sequences, {df.species.nunique()} species, "
          f"{df.genus.nunique()} genera, {df.family.nunique()} families")
    print(f"Trimmed sequences in final set: {int(df.trimmed.sum())}")
    print(f"Wrote {PROCESSED_DIR / 'clean.fasta'}, metadata.csv, barcode_references.fasta, "
          "cleaning_log.csv, removed_misids.csv")


if __name__ == "__main__":
    main()
