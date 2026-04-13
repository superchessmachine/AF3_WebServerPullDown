# AF3 WebServer PullDown

Clean, modular tooling for turning your BioGRID pull-down exports into AlphaFold3 webserver job JSON files.

It is built around the working `make-af3-jobs.py` flow that resolved 747 interactors and generated the full 6 experiment sets for this repo.

## What's inside

- `generate_outputs.py` – toolkit entry point with the same core behavior as `make-af3-jobs.py`
- `src/af3_webserver_pulldown/` – modular BioGRID parsing, UniProt resolution, payload building, and report writing
- `configs/experiment_sets.json` – the 6 pull-down experiment definitions
- `templates/af3_job_template.json` – fallback AF3 template metadata
- `scripts/fetch_uniprot_cache.py` – optional helper to build a local accession cache TSV
- `scripts/report_batches.py` – quick summary for a generated output folder
- `automation/README.md` – how to pair this with the browser automation repo

## What it does

The generator:

1. Reads seed protein sequences from `personal_data/Sequence_data_for_all_main.txt`
2. Reads BioGRID exports like `personal_data/USP22.txt`
3. Collects the partner proteins opposite each bait
4. Pools those interactors into 6 experiment sets
5. Resolves sequences from UniProt by accession, then by gene-symbol fallback
6. Writes one AlphaFold3 webserver JSON per valid bait-plus-interactor job
7. Batches jobs into folders of 30 and writes bundle manifests and summary files

## Quick start

Install the only required dependency:

```bash
python -m pip install requests
```

Run the same workflow as the working script:

```bash
python make-af3-jobs.py \
  --repo-root /Users/ysb/Downloads/USP22_27x_51_AlphaPullDown \
  --output-root /Users/ysb/Downloads/USP22_27x_51_AlphaPullDown/AF3_WebServerPullDown_Output_final \
  --overwrite
```

You can also call the toolkit directly:

```bash
python AF3_WebServerPullDown/generate_outputs.py \
  --repo-root /Users/ysb/Downloads/USP22_27x_51_AlphaPullDown \
  --output-root /Users/ysb/Downloads/USP22_27x_51_AlphaPullDown/AF3_WebServerPullDown_Output_final \
  --overwrite
```

## Inputs it expects

- `personal_data/Sequence_data_for_all_main.txt`
- `personal_data/USP22.txt`
- `personal_data/USP27X.txt`
- `personal_data/USP51.txt`
- `personal_data/ATXN7.txt`
- `personal_data/ATXN7L3.txt`
- `personal_data/ENY2.txt`
- `example_job_request.json` at the repo root

If `example_job_request.json` is missing, the toolkit falls back to `AF3_WebServerPullDown/templates/af3_job_template.json`.

## Output layout

For each experiment, the generator writes:

- `batches/batch_0001/*.json` – upload-ready AF3 job payloads
- `bundles/batch_0001_bundle.json` – manifest for each 30-job batch
- `interactors_all.csv` – every pooled candidate and its resolution status
- `jobs_manifest.csv` – every generated job and its batch location
- `excluded_jobs.csv` – candidates that could not become jobs
- `experiment_summary.json` – per-experiment counts

At the run level, it writes:

- `run_summary.json`
- `unresolved_global.csv`
- `NEEDS_USER_INPUT.md` only when some interactors still cannot be resolved

## Useful options

- `--batch-size 30` – override the config batch size
- `--timeout 25` – UniProt request timeout in seconds
- `--sleep 0.05` – delay between sequence lookups
- `--sequence-cache path.tsv` – preload resolved sequences from a TSV cache
- `--write-sequence-cache path.tsv` – save resolved sequences for reuse
- `--personal-data-dir path` – point to a different input folder

## Optional helpers

Build a local UniProt cache from a manifest that has an `accession` column:

```bash
python AF3_WebServerPullDown/scripts/fetch_uniprot_cache.py \
  --input AF3_WebServerPullDown_Output_final/unresolved_global.csv \
  --output AF3_WebServerPullDown/templates/sequence_cache.tsv
```

Summarize a finished run:

```bash
python AF3_WebServerPullDown/scripts/report_batches.py \
  --output-root AF3_WebServerPullDown_Output_final
```

## Pair it with submission automation

This repo only generates and organizes AF3 job files.

To submit those drafts and download completed predictions, use the browser-console scripts documented in `AF3_WebServerPullDown/automation/README.md` and stored in `AlphaFold3-Webserver-Automation/`.
# AF3_WebServerPullDown
