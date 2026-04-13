from __future__ import annotations

import json
from pathlib import Path

from .biogrid import load_biogrid_interactors, pool_interactors
from .config import load_job_config
from .models import InteractorRecord
from .output_writer import render_needs_user_input, write_csv, write_job_set_output
from .payloads import make_job_payload
from .sequences import SequenceResolver, load_accession_cache
from .utils import load_example_template, log, parse_sequence_blocks, safe_name


def build_global_candidate_pool(source_interactors: dict[str, dict[str, InteractorRecord]]) -> dict[str, InteractorRecord]:
    pooled: dict[str, InteractorRecord] = {}
    for source_map in source_interactors.values():
        for record in source_map.values():
            key = record.accession or record.partner_symbol
            if key not in pooled:
                pooled[key] = InteractorRecord(
                    partner_symbol=record.partner_symbol,
                    accession=record.accession,
                    biogrid_ids=list(record.biogrid_ids),
                    source_proteins=set(record.source_proteins),
                    raw_partner_symbols=set(record.raw_partner_symbols),
                    raw_accessions=set(record.raw_accessions),
                )
                continue

            destination = pooled[key]
            destination.biogrid_ids.extend(record.biogrid_ids)
            destination.source_proteins |= record.source_proteins
            destination.raw_partner_symbols |= record.raw_partner_symbols
            destination.raw_accessions |= record.raw_accessions

    return pooled


def run_generation(
    repo_root: Path,
    input_data_dir: Path,
    output_root: Path,
    config_path: Path,
    example_template_path: Path,
    batch_size_override: int | None = None,
    timeout: float = 25.0,
    sleep: float = 0.05,
    overwrite: bool = False,
    sequence_cache_path: Path | None = None,
    write_sequence_cache_path: Path | None = None,
) -> dict:
    main_sequence_path = input_data_dir / "main_sequences.txt"
    if not input_data_dir.exists():
        raise FileNotFoundError(f"Missing input data dir: {input_data_dir}")
    if not main_sequence_path.exists():
        raise FileNotFoundError(f"Missing main sequence file: {main_sequence_path}")

    main_proteins, config_batch_size, job_sets = load_job_config(config_path)
    batch_size = batch_size_override or config_batch_size
    output_root.mkdir(parents=True, exist_ok=True)

    if not example_template_path.exists():
        fallback_template = Path(__file__).resolve().parents[2] / "templates" / "job_template.json"
        example_template_path = fallback_template

    dialect, version, use_structure_template = load_example_template(example_template_path)
    main_sequences = parse_sequence_blocks(main_sequence_path)

    missing_main = [
        protein
        for protein in main_proteins
        if protein not in main_sequences and (input_data_dir / f"{protein}.txt").exists()
    ]
    if missing_main:
        log(f"Warning: missing main sequences for: {', '.join(missing_main)}")

    log("Loading BioGRID interactors...")
    source_interactors = load_biogrid_interactors(input_data_dir, main_proteins)
    all_candidates = build_global_candidate_pool(source_interactors)

    resolver = SequenceResolver(
        timeout=timeout,
        sleep=sleep,
        sequence_cache=load_accession_cache(sequence_cache_path),
        write_cache_path=write_sequence_cache_path,
    )
    resolution_cache = resolver.resolve_all(all_candidates)

    run_summary = {
        "output_root": str(output_root),
        "job_sets": [],
        "unresolved_global_count": 0,
    }
    unresolved_global_rows: list[dict[str, str]] = []

    for job_set in job_sets:
        pooled = pool_interactors(source_interactors, job_set.pool_sources)
        for record in pooled.values():
            cache_key = record.accession or record.partner_symbol
            resolution = resolution_cache.get(cache_key)
            if resolution is None:
                continue
            if resolution.accession and not record.accession:
                record.accession = resolution.accession
            record.sequence = resolution.sequence
            record.sequence_source = resolution.reason
            record.resolve_status = "resolved" if resolution.sequence else "unresolved"

        seed_sequences: list[tuple[str, str]] = []
        seed_missing: list[str] = []
        for protein in job_set.seed_proteins:
            sequence = main_sequences.get(protein.upper())
            if sequence:
                seed_sequences.append((protein, sequence))
            else:
                seed_missing.append(protein)

        candidate_count = len(pooled)
        generated_jobs: list[tuple[str, dict]] = []
        excluded_rows: list[dict[str, str]] = []
        interactors_rows: list[dict[str, str]] = []

        for pool_key, record in sorted(
            pooled.items(),
            key=lambda item: ((item[1].partner_symbol or ""), (item[1].accession or "")),
        ):
            interactors_rows.append(
                {
                    "pool_key": pool_key,
                    "partner_symbol": record.partner_symbol,
                    "accession": record.accession,
                    "source_proteins": "|".join(sorted(record.source_proteins)),
                    "biogrid_interaction_ids": "|".join(sorted(set(record.biogrid_ids))),
                    "raw_partner_symbols": "|".join(sorted(record.raw_partner_symbols)),
                    "raw_accessions": "|".join(sorted(record.raw_accessions)),
                    "resolve_status": record.resolve_status,
                    "sequence_source": record.sequence_source,
                    "sequence_length": str(len(record.sequence) if record.sequence else 0),
                }
            )

            if seed_missing:
                excluded_rows.append(
                    {
                        "partner_symbol": record.partner_symbol,
                        "accession": record.accession,
                        "source_proteins": "|".join(sorted(record.source_proteins)),
                        "reason": f"missing_seed_sequences:{'|'.join(seed_missing)}",
                    }
                )
                continue

            if not record.sequence:
                reason = record.sequence_source or "could_not_resolve_interactor_sequence"
                record.exclude_reason = reason
                excluded_rows.append(
                    {
                        "partner_symbol": record.partner_symbol,
                        "accession": record.accession,
                        "source_proteins": "|".join(sorted(record.source_proteins)),
                        "reason": reason,
                    }
                )
                unresolved_global_rows.append(
                    {
                        "job_set_id": job_set.job_set_id,
                        "partner_symbol": record.partner_symbol,
                        "accession": record.accession,
                        "source_proteins": "|".join(sorted(record.source_proteins)),
                        "reason": reason,
                    }
                )
                continue

            job_name = safe_name(
                f"{job_set.job_set_id}__{record.partner_symbol or 'UNKNOWN'}__{record.accession or 'NOACC'}",
                max_len=140,
            )
            payload = make_job_payload(
                job_name=job_name,
                seed_sequences=seed_sequences,
                interactor_sequence=record.sequence,
                dialect=dialect,
                version=version,
                use_structure_template=use_structure_template,
            )
            generated_jobs.append((job_name, payload))

        summary = write_job_set_output(
            output_root=output_root,
            job_set=job_set,
            interactors_rows=interactors_rows,
            generated_jobs=generated_jobs,
            excluded_rows=excluded_rows,
            batch_size=batch_size,
            overwrite=overwrite,
            candidate_count=candidate_count,
            seed_missing=seed_missing,
        )
        run_summary["job_sets"].append(summary)
        log(
            f"{job_set.job_set_id}: candidates={candidate_count} generated={len(generated_jobs)} "
            f"excluded={len(excluded_rows)} batches={summary['batch_count']}"
        )

    run_summary["unresolved_global_count"] = len(unresolved_global_rows)
    (output_root / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    write_csv(
        output_root / "unresolved_global.csv",
        ["job_set_id", "partner_symbol", "accession", "source_proteins", "reason"],
        unresolved_global_rows,
    )

    needs_user_input_path = output_root / "NEEDS_USER_INPUT.md"
    if unresolved_global_rows:
        needs_user_input_path.write_text(render_needs_user_input(unresolved_global_rows), encoding="utf-8")
    elif needs_user_input_path.exists():
        needs_user_input_path.unlink()

    log("")
    log(f"Finished. Output written to: {output_root}")
    log("Key files:")
    log(f"  - {output_root / 'run_summary.json'}")
    log(f"  - {output_root / 'unresolved_global.csv'}")
    if needs_user_input_path.exists():
        log(f"  - {needs_user_input_path}")

    return run_summary
