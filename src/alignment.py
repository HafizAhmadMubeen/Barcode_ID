"""alignment.py: align the clean barcodes with MAFFT.

Input:  data/processed/clean.fasta      (from data_cleaning.py)
Output: data/processed/aligned.fasta    (all sequences, same length, gaps as "-")

All sequences (train and test) are aligned together. This uses no species
labels, so it does not leak test information. MAFFT's --auto picks a suitable
accuracy/speed strategy for the data size.

The result is cached: if aligned.fasta is newer than clean.fasta, nothing runs.

Run from the repo root:
    python src/alignment.py
"""
import subprocess
import sys
import time
from pathlib import Path

from Bio import SeqIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MAFFT_CMD, PROCESSED_DIR  # noqa: E402

IN_FASTA = PROCESSED_DIR / "clean.fasta"
OUT_FASTA = PROCESSED_DIR / "aligned.fasta"


def mafft_align(in_fasta):
    """Align a FASTA file with MAFFT and return the aligned FASTA as text.

    Sequences are uppercased (MAFFT writes lowercase); headers are unchanged.
    """
    result = subprocess.run([MAFFT_CMD, "--auto", "--thread", "-1", str(in_fasta)],
                            capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"MAFFT failed:\n{result.stderr[-2000:]}")
    # The Windows build prints a "code page" line before the FASTA; keep from the first ">".
    fasta = result.stdout[result.stdout.index(">"):]
    lines = [line if line.startswith(">") else line.upper() for line in fasta.splitlines()]
    return "\n".join(lines) + "\n"


def run_mafft():
    """Align clean.fasta and write aligned.fasta."""
    start = time.time()
    OUT_FASTA.write_text(mafft_align(IN_FASTA), encoding="utf-8")
    print(f"MAFFT finished in {time.time() - start:.0f}s")


def main():
    if OUT_FASTA.exists() and OUT_FASTA.stat().st_mtime > IN_FASTA.stat().st_mtime:
        print(f"Using cached alignment {OUT_FASTA}")
    else:
        run_mafft()

    # Sanity checks: same sequences in, every row the same length.
    raw = list(SeqIO.parse(IN_FASTA, "fasta"))
    aln = list(SeqIO.parse(OUT_FASTA, "fasta"))
    lengths = {len(r.seq) for r in aln}
    assert [r.id for r in raw] == [r.id for r in aln], "IDs changed during alignment"
    assert len(lengths) == 1, f"rows have different lengths: {sorted(lengths)[:5]}"

    width = lengths.pop()
    gap_share = [sum(str(r.seq[i]) == "-" for r in aln) / len(aln) for i in range(width)]
    print(f"{len(aln)} sequences, alignment length {width} columns")
    print(f"columns that are >50% gaps: {sum(g > 0.5 for g in gap_share)}")
    print(f"columns that are >90% gaps: {sum(g > 0.9 for g in gap_share)}")


if __name__ == "__main__":
    main()
