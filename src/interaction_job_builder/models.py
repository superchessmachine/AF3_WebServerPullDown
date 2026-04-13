from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class JobSetDefinition:
    job_set_id: str
    description: str
    seed_proteins: list[str]
    pool_sources: list[str]


@dataclass
class InteractorRecord:
    partner_symbol: str
    accession: str
    biogrid_ids: list[str] = field(default_factory=list)
    source_proteins: set[str] = field(default_factory=set)
    raw_partner_symbols: set[str] = field(default_factory=set)
    raw_accessions: set[str] = field(default_factory=set)
    sequence: str | None = None
    sequence_source: str = ""
    resolve_status: str = ""
    exclude_reason: str = ""


@dataclass(frozen=True)
class ResolutionRecord:
    accession: str | None
    sequence: str | None
    reason: str
