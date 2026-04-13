from __future__ import annotations

from .utils import deterministic_seed


def make_protein_chain_entry(sequence: str, count: int, use_structure_template: bool) -> dict:
    return {
        "proteinChain": {
            "sequence": sequence,
            "count": count,
            "useStructureTemplate": use_structure_template,
        }
    }


def make_job_payload(
    job_name: str,
    seed_sequences: list[tuple[str, str]],
    interactor_sequence: str,
    dialect: str,
    version: int,
    use_structure_template: bool,
) -> list[dict]:
    sequences = [
        make_protein_chain_entry(sequence, 1, use_structure_template)
        for _, sequence in seed_sequences
    ]
    sequences.append(make_protein_chain_entry(interactor_sequence, 1, use_structure_template))
    return [
        {
            "name": job_name,
            "modelSeeds": [deterministic_seed(job_name)],
            "sequences": sequences,
            "dialect": dialect,
            "version": version,
        }
    ]
