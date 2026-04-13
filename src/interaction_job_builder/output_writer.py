from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import JobSetDefinition
from .utils import chunked


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_job_set_output(
    output_root: Path,
    job_set: JobSetDefinition,
    interactors_rows: list[dict[str, str]],
    generated_jobs: list[tuple[str, dict]],
    excluded_rows: list[dict[str, str]],
    batch_size: int,
    overwrite: bool,
    candidate_count: int,
    seed_missing: list[str],
) -> dict:
    job_set_dir = output_root / job_set.job_set_id
    batches_dir = job_set_dir / "batches"
    bundles_dir = job_set_dir / "bundles"
    job_set_dir.mkdir(parents=True, exist_ok=True)
    batches_dir.mkdir(exist_ok=True)
    bundles_dir.mkdir(exist_ok=True)

    manifest_rows: list[dict[str, str]] = []
    batch_chunks = chunked(generated_jobs, batch_size)
    for batch_index, batch in enumerate(batch_chunks, start=1):
        batch_name = f"batch_{batch_index:04d}"
        batch_dir = batches_dir / batch_name
        batch_dir.mkdir(exist_ok=True)

        bundle_entries = []
        for job_name, payload in batch:
            json_filename = f"{job_name}.json"
            json_path = batch_dir / json_filename
            if overwrite or not json_path.exists():
                json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            relpath = str(Path("batches") / batch_name / json_filename)
            bundle_entries.append({"job_name": job_name, "json_relpath": relpath})
            manifest_rows.append(
                {
                    "job_name": job_name,
                    "batch": batch_name,
                    "json_file": json_filename,
                    "json_relpath": relpath,
                }
            )

        bundle_payload = {
            "job_set_id": job_set.job_set_id,
            "batch": batch_name,
            "job_count": len(bundle_entries),
            "jobs": bundle_entries,
        }
        (bundles_dir / f"{batch_name}_bundle.json").write_text(json.dumps(bundle_payload, indent=2), encoding="utf-8")

    write_csv(
        job_set_dir / "interactors_all.csv",
        [
            "pool_key",
            "partner_symbol",
            "accession",
            "source_proteins",
            "biogrid_interaction_ids",
            "raw_partner_symbols",
            "raw_accessions",
            "resolve_status",
            "sequence_source",
            "sequence_length",
        ],
        interactors_rows,
    )
    write_csv(
        job_set_dir / "jobs_manifest.csv",
        ["job_name", "batch", "json_file", "json_relpath"],
        manifest_rows,
    )
    write_csv(
        job_set_dir / "excluded_jobs.csv",
        ["partner_symbol", "accession", "source_proteins", "reason"],
        excluded_rows,
    )

    summary = {
        "job_set_id": job_set.job_set_id,
        "description": job_set.description,
        "seed_proteins": job_set.seed_proteins,
        "pool_sources": job_set.pool_sources,
        "candidate_interactors": candidate_count,
        "generated_jobs": len(generated_jobs),
        "excluded_jobs": len(excluded_rows),
        "batch_count": len(batch_chunks),
        "batch_size": batch_size,
        "seed_missing": seed_missing,
    }
    (job_set_dir / "job_set_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def render_needs_user_input(rows: list[dict[str, str]]) -> str:
    lines = [
        "# NEEDS_USER_INPUT",
        "",
        "This file is only actionable for interactors that could not be resolved into sequences.",
        "Everything below is specific, minimal missing information.",
        "",
        "## Unresolved interactors",
        "",
        "These interactors could not be turned into jobs because no protein sequence could be resolved.",
        "Fastest fix is to provide either a UniProt accession or an amino acid sequence for each one.",
        "",
    ]

    for row in rows:
        lines.extend(
            [
                f"### {row['job_set_id']} :: {row['partner_symbol'] or 'UNKNOWN'}",
                f"- accession seen: {row['accession'] or 'NONE'}",
                f"- source proteins: {row['source_proteins'] or 'UNKNOWN'}",
                f"- reason: {row['reason']}",
                "- needed from user: one reviewed human UniProt accession or a direct amino acid sequence",
                "",
            ]
        )

    return "\n".join(lines)
