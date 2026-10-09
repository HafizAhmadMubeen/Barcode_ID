"""download_bold.py: download the raw BOLD records for our dataset scope.

Scope: all Odonata from each country in config.EUROPE_COUNTRIES, one BOLD v5
query per country (BOLD rejects queries with many countries at once).

We download the whole order, not just TARGET_FAMILIES, because BOLD's query
endpoint does not recognise "tax:family:Libellulidae" (it reads it as a sample
ID). The family filter is done in data_cleaning.py using BOLD's own "family"
column, so it shows up as a logged cleaning step.

Output (in data/raw/, never edited afterwards):
    bold_Odonata_<Country>.tsv    BOLD's TSV export, saved byte-for-byte
    download_manifest.csv         one row per file: query, row count, date

Already-downloaded files are skipped, so re-running only fetches what is missing.
Delete a file to force it to be downloaded again.

Run from the repo root:
    python src/download_bold.py
"""
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

# Make config.py (in the repo root) importable when run as "python src/download_bold.py".
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import EUROPE_COUNTRIES, RAW_DIR  # noqa: E402

TAXON = "Odonata"
API = "https://portal.boldsystems.org/api"
# BOLD refuses Python's default User-Agent (HTTP 403), so we send our own.
HEADERS = {"User-Agent": "BarcodeID-student-project (urllib)"}
PAUSE_SECONDS = 2   # wait between requests so BOLD does not rate-limit us (HTTP 503)
MAX_TRIES = 4       # retries for temporary server errors


def get(url):
    """GET a URL and return the raw bytes, retrying on temporary errors."""
    for attempt in range(1, MAX_TRIES + 1):
        try:
            time.sleep(PAUSE_SECONDS)
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < MAX_TRIES:
                wait = 15 * attempt
                print(f"    HTTP {e.code}, retrying in {wait}s (attempt {attempt}/{MAX_TRIES})")
                time.sleep(wait)
            else:
                raise


def api(endpoint, **params):
    """Call a BOLD API endpoint with query parameters."""
    return get(f"{API}/{endpoint}?" + urllib.parse.urlencode(params))


def check_query(query):
    """Stop if BOLD did not understand every term in the query.

    BOLD silently drops terms it cannot match (e.g. it reads "Libellulidae" as
    a sample ID), which would quietly download the wrong data. It answers such
    queries with HTTP 400 plus a JSON list of the failed terms.
    """
    try:
        result = json.loads(api("query/preprocessor", query=query))
    except urllib.error.HTTPError as e:
        if e.code != 400:
            raise
        result = json.loads(e.read())
    if result.get("failed_terms"):
        sys.exit(f"BOLD did not recognise query terms: {result['failed_terms']}\nQuery: {query}")


def download(query, out_path):
    """Run one BOLD query and save its TSV export untouched."""
    check_query(query)
    query_id = json.loads(api("query", query=query, extent="full"))["query_id"]
    tsv = get(f"{API}/documents/{query_id}/download?format=tsv")
    out_path.write_bytes(tsv)


def count_rows(path):
    """Number of records in a TSV file (lines minus the header)."""
    with open(path, encoding="utf-8", newline="") as f:
        return max(sum(1 for _ in f) - 1, 0)


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []

    for i, country in enumerate(EUROPE_COUNTRIES, start=1):
        query = f"tax:order:{TAXON};geo:country/ocean:{country}"
        out_path = RAW_DIR / f"bold_{TAXON}_{country.replace(' ', '_')}.tsv"

        if out_path.exists():
            status = "cached"
        else:
            download(query, out_path)
            status = "downloaded"

        n = count_rows(out_path)
        print(f"[{i:2d}/{len(EUROPE_COUNTRIES)}] {country:24s} {n:5d} records ({status})")
        manifest.append({
            "taxon": TAXON,
            "country": country,
            "query": query,
            "file": out_path.name,
            "n_records": n,
            # File modification date = the day the data was downloaded from BOLD.
            "download_date": date.fromtimestamp(out_path.stat().st_mtime).isoformat(),
        })

    manifest_path = RAW_DIR / "download_manifest.csv"
    with open(manifest_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)

    # Raw total, so data loss can be traced from the very first step.
    total = sum(m["n_records"] for m in manifest)
    print(f"\nRaw total: {total} {TAXON} records from {len(manifest)} countries "
          "(all families and markers, before any cleaning)")
    print(f"Manifest written to {manifest_path}")


if __name__ == "__main__":
    main()
