from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import InteractorRecord, ResolutionRecord
from .utils import first_token, log


UNIPROT_ENTRY_FASTA = "https://rest.uniprot.org/uniprotkb/{accession}.fasta"
UNIPROT_SEARCH_TSV = (
    "https://rest.uniprot.org/uniprotkb/search"
    "?format=tsv&size=10&fields=accession,reviewed,gene_names,protein_name"
    "&query={query}"
)


def make_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.35,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fasta_to_sequence(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not lines[0].startswith(">"):
        return ""
    return "".join(lines[1:]).strip()


def fetch_sequence_by_accession(
    session: requests.Session,
    accession: str,
    timeout: float,
) -> tuple[Optional[str], str]:
    clean_accession = first_token(accession)
    if not clean_accession:
        return None, "no_accession"
    url = UNIPROT_ENTRY_FASTA.format(accession=clean_accession)
    try:
        response = session.get(url, headers={"Accept": "text/plain"}, timeout=timeout)
        if response.status_code == 200:
            sequence = fasta_to_sequence(response.text)
            if sequence:
                return sequence, f"uniprot_accession:{clean_accession}"
            return None, f"empty_fasta:{clean_accession}"
        if response.status_code == 404:
            return None, f"accession_not_found:{clean_accession}"
        return None, f"accession_http_{response.status_code}:{clean_accession}"
    except requests.RequestException as exc:
        return None, f"accession_request_error:{clean_accession}:{type(exc).__name__}"


def fetch_uniprot_fasta_sequence(accession: str, timeout: float = 25.0) -> str:
    session = make_session()
    sequence, _ = fetch_sequence_by_accession(session, accession, timeout)
    return sequence or ""


def search_uniprot_by_gene(
    session: requests.Session,
    gene_symbol: str,
    timeout: float,
) -> tuple[Optional[str], Optional[str], str]:
    gene = (gene_symbol or "").strip()
    if not gene:
        return None, None, "no_gene_symbol"

    query = requests.utils.quote(f"(gene_exact:{gene}) AND (organism_id:9606)")
    url = UNIPROT_SEARCH_TSV.format(query=query)

    try:
        response = session.get(url, headers={"Accept": "text/plain"}, timeout=timeout)
        if response.status_code != 200:
            return None, None, f"gene_search_http_{response.status_code}:{gene}"
        lines = [line for line in response.text.splitlines() if line.strip()]
        if len(lines) <= 1:
            return None, None, f"gene_search_no_hits:{gene}"

        header = lines[0].split("\t")
        rows = [dict(zip(header, line.split("\t"))) for line in lines[1:]]
        ranked = sorted(
            rows,
            key=lambda row: (
                0 if row.get("Reviewed", "").lower() == "reviewed" else 1,
                row.get("Entry", ""),
            ),
        )
        for row in ranked:
            accession = row.get("Entry", "").strip()
            if not accession:
                continue
            sequence, reason = fetch_sequence_by_accession(session, accession, timeout)
            if sequence:
                return accession, sequence, f"gene_search:{gene}->{accession}"
        return None, None, f"gene_search_hits_but_no_sequence:{gene}"
    except requests.RequestException as exc:
        return None, None, f"gene_search_request_error:{gene}:{type(exc).__name__}"


def load_accession_cache(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            return {}
        field_lookup = {field.lower(): field for field in reader.fieldnames}
        accession_field = field_lookup.get("accession")
        sequence_field = field_lookup.get("sequence")
        gene_symbol_field = field_lookup.get("gene_symbol") or field_lookup.get("symbol")
        if accession_field is None or sequence_field is None:
            raise ValueError(f"Cache file {path} must include accession and sequence columns")
        cache: dict[str, dict[str, str]] = {}
        for row in reader:
            accession = (row.get(accession_field) or "").strip().upper()
            sequence = (row.get(sequence_field) or "").strip().upper()
            if not accession or not sequence:
                continue
            cache[accession] = {
                "accession": accession,
                "gene_symbol": (row.get(gene_symbol_field) or "").strip() if gene_symbol_field else "",
                "sequence": sequence,
                "source": f"sequence_cache:{accession}",
            }
        return cache


def write_accession_cache(path: Path, cache: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["accession", "gene_symbol", "sequence"], delimiter="\t")
        writer.writeheader()
        for accession in sorted(cache):
            writer.writerow(
                {
                    "accession": cache[accession].get("accession", accession),
                    "gene_symbol": cache[accession].get("gene_symbol", ""),
                    "sequence": cache[accession].get("sequence", ""),
                }
            )


class SequenceResolver:
    def __init__(
        self,
        timeout: float = 25.0,
        sleep: float = 0.05,
        sequence_cache: Optional[dict[str, dict[str, str]]] = None,
        write_cache_path: Path | None = None,
    ) -> None:
        self.timeout = timeout
        self.sleep = sleep
        self.session = make_session()
        self.sequence_cache = sequence_cache or {}
        self.write_cache_path = write_cache_path
        self.resolution_cache: dict[str, ResolutionRecord] = {}

    def resolve(self, partner_symbol: str, accession: str) -> ResolutionRecord:
        cache_key = accession or partner_symbol
        if cache_key in self.resolution_cache:
            return self.resolution_cache[cache_key]

        resolved_accession = accession or None
        sequence = None
        reason = ""

        clean_accession = (accession or "").strip().upper()
        if clean_accession and clean_accession in self.sequence_cache:
            cached = self.sequence_cache[clean_accession]
            result = ResolutionRecord(
                accession=cached.get("accession") or clean_accession,
                sequence=cached.get("sequence") or None,
                reason=cached.get("source") or f"sequence_cache:{clean_accession}",
            )
            self.resolution_cache[cache_key] = result
            return result

        if accession:
            sequence, reason = fetch_sequence_by_accession(self.session, accession, self.timeout)

        if not sequence:
            fallback_accession, fallback_sequence, fallback_reason = search_uniprot_by_gene(
                self.session,
                partner_symbol,
                self.timeout,
            )
            if fallback_sequence:
                resolved_accession = fallback_accession or resolved_accession
                sequence = fallback_sequence
                reason = fallback_reason
            else:
                reason = f"{reason}; {fallback_reason}" if reason else fallback_reason

        result = ResolutionRecord(accession=resolved_accession, sequence=sequence, reason=reason)
        self.resolution_cache[cache_key] = result

        if sequence and resolved_accession:
            self.sequence_cache[resolved_accession] = {
                "accession": resolved_accession,
                "gene_symbol": (partner_symbol or "").strip().upper(),
                "sequence": sequence,
                "source": reason,
            }
            if self.write_cache_path is not None:
                write_accession_cache(self.write_cache_path, self.sequence_cache)

        return result

    def resolve_all(self, candidates: dict[str, InteractorRecord]) -> dict[str, ResolutionRecord]:
        total = len(candidates)
        log(f"Resolving sequences for {total} unique interaction partners...")
        for index, (_, record) in enumerate(sorted(candidates.items()), start=1):
            self.resolve(record.partner_symbol, record.accession)
            if index == 1 or index % 50 == 0 or index == total:
                log(f"  resolved {index}/{total}")
            if self.sleep > 0:
                time.sleep(self.sleep)
        return self.resolution_cache
