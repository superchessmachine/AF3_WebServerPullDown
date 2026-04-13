#!/usr/bin/env python3

from pathlib import Path
import csv
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from interaction_job_builder.sequences import fetch_uniprot_fasta_sequence, load_accession_cache, write_accession_cache  # noqa: E402


def parse_args(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Build or extend a local UniProt sequence cache TSV.")
    parser.add_argument("--input", required=True, help="TSV manifest with at least an accession column.")
    parser.add_argument("--output", required=True, help="TSV cache file to write.")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    input_path = Path(args.input)
    output_path = Path(args.output)

    existing = load_accession_cache(output_path) if output_path.exists() else {}
    rows = []

    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            raise SystemExit("Input manifest is empty.")
        accession_field = next((field for field in reader.fieldnames if field.lower() == "accession"), None)
        gene_field = next((field for field in reader.fieldnames if field.lower() in {"gene_symbol", "symbol", "partner_symbol"}), None)
        if accession_field is None:
            raise SystemExit("Input manifest must contain an accession column.")

        for row in reader:
            accession = (row.get(accession_field) or "").strip().upper()
            gene_symbol = (row.get(gene_field) or "").strip() if gene_field else ""
            if not accession or accession == "-":
                continue
            if accession in existing:
                rows.append(existing[accession])
                continue
            sequence = fetch_uniprot_fasta_sequence(accession, timeout=args.timeout)
            if not sequence:
                print(f"SKIP {accession}: unable to fetch sequence", file=sys.stderr)
                continue
            cache_row = {
                "accession": accession,
                "gene_symbol": gene_symbol,
                "sequence": sequence,
            }
            existing[accession] = cache_row
            rows.append(cache_row)
            print(f"Fetched {accession}", file=sys.stderr)

    if not rows:
        rows = list(existing.values())

    write_accession_cache(output_path, existing)
    print(f"Wrote cache: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
