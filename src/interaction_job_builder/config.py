from __future__ import annotations

import json
from pathlib import Path

from .models import JobSetDefinition


DEFAULT_MAIN_PROTEINS = ["PROTEIN_A", "PROTEIN_B", "PROTEIN_C"]


def load_job_config(path: Path) -> tuple[list[str], int, list[JobSetDefinition]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    main_proteins = list(data.get("main_proteins") or data.get("primary_proteins") or DEFAULT_MAIN_PROTEINS)
    batch_size = int(data.get("batch_size", 30))
    job_sets = []

    for item in data.get("job_sets") or []:
        job_set_id = item.get("job_set_id") or item.get("id")
        if not job_set_id:
            raise ValueError(f"Job-set entry in {path} is missing job_set_id")
        pool_sources = item.get("pool_sources") or item.get("interactor_sources")
        if not pool_sources:
            raise ValueError(f"Job set {job_set_id} is missing pool_sources")
        job_sets.append(
            JobSetDefinition(
                job_set_id=job_set_id,
                description=item["description"],
                seed_proteins=list(item["seed_proteins"]),
                pool_sources=list(pool_sources),
            )
        )

    if not job_sets:
        raise ValueError(f"No job sets found in {path}")

    return main_proteins, batch_size, job_sets
