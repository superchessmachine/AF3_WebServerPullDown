# Interaction Job Builder

Generate reusable JSON job bundles from BioGRID-style protein interaction exports and seed-sequence inputs.

## What this repo expects

- A config file that lists your seed proteins and job-set definitions.
- An input directory containing:
  - `main_sequences.txt` with named protein sequence blocks.
  - One BioGRID-style export per seed protein, named `<PROTEIN>.txt`.
- Optionally, a cached accession-to-sequence TSV.

## Quick start

1. Edit `configs/job_sets.json` to match your proteins and grouping strategy.
2. Put your input files under `input_data/`.
3. Run:

```bash
python generate_outputs.py --repo-root .
```

Generated files are written to `generated_job_output/` by default.

## Input format

`main_sequences.txt` uses named blocks like:

```text
PROTEIN_A:
MSEQUENCEEXAMPLE

PROTEIN_B:
MSEQUENCEEXAMPLE
```

Each per-protein interaction file should be a BioGRID-style TSV or CSV export for that protein.

## Notes

- `configs/job_sets.json` is only a generic example; replace every placeholder before use.
- Local input data and generated outputs are ignored by `.gitignore` so they do not get committed accidentally.

