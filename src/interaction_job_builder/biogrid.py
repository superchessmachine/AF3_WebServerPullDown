from __future__ import annotations

from pathlib import Path

from .models import InteractorRecord
from .utils import first_token, read_table


def choose_accession_from_row(row: dict[str, str], side: str) -> str:
    swiss = first_token(row.get(f"SWISS-PROT Accessions Interactor {side}", ""))
    trembl = first_token(row.get(f"TREMBL Accessions Interactor {side}", ""))
    return swiss or trembl


def extract_partner_from_biogrid_row(row: dict[str, str], source_symbol: str) -> tuple[str, str, str]:
    symbol_a = (row.get("Official Symbol Interactor A", "") or "").strip().upper()
    symbol_b = (row.get("Official Symbol Interactor B", "") or "").strip().upper()
    interaction_id = (row.get("BioGRID Interaction ID", "") or "").strip()
    source_symbol = source_symbol.upper()

    if symbol_a == source_symbol and symbol_b:
        return symbol_b, choose_accession_from_row(row, "B"), interaction_id
    if symbol_b == source_symbol and symbol_a:
        return symbol_a, choose_accession_from_row(row, "A"), interaction_id
    if symbol_a and symbol_a != source_symbol:
        return symbol_a, choose_accession_from_row(row, "A"), interaction_id
    if symbol_b and symbol_b != source_symbol:
        return symbol_b, choose_accession_from_row(row, "B"), interaction_id
    return "", "", interaction_id


def load_biogrid_interactors(input_data_dir: Path, main_proteins: list[str]) -> dict[str, dict[str, InteractorRecord]]:
    result: dict[str, dict[str, InteractorRecord]] = {}
    available_sources = [protein for protein in main_proteins if (input_data_dir / f"{protein}.txt").exists()]

    for source in available_sources:
        _, rows = read_table(input_data_dir / f"{source}.txt")
        interactors: dict[str, InteractorRecord] = {}

        for row in rows:
            organism_a = (row.get("Organism ID Interactor A", "") or "").strip()
            organism_b = (row.get("Organism ID Interactor B", "") or "").strip()
            if organism_a and organism_b and not (organism_a == "9606" and organism_b == "9606"):
                continue

            partner_symbol, partner_accession, interaction_id = extract_partner_from_biogrid_row(row, source)
            if not partner_symbol and not partner_accession:
                continue

            partner_symbol = partner_symbol.upper()
            partner_accession = first_token(partner_accession)
            if partner_symbol == source.upper():
                continue

            key = partner_accession or partner_symbol
            record = interactors.setdefault(
                key,
                InteractorRecord(
                    partner_symbol=partner_symbol or key,
                    accession=partner_accession,
                ),
            )
            if interaction_id:
                record.biogrid_ids.append(interaction_id)
            record.source_proteins.add(source)
            if partner_symbol:
                record.raw_partner_symbols.add(partner_symbol)
            if partner_accession:
                record.raw_accessions.add(partner_accession)

        result[source] = interactors

    return result


def pool_interactors(
    source_interactors: dict[str, dict[str, InteractorRecord]],
    pool_sources: list[str],
) -> dict[str, InteractorRecord]:
    pooled: dict[str, InteractorRecord] = {}

    for source in pool_sources:
        for record in source_interactors.get(source, {}).values():
            merge_key = record.accession or record.partner_symbol
            if merge_key not in pooled:
                pooled[merge_key] = InteractorRecord(
                    partner_symbol=record.partner_symbol,
                    accession=record.accession,
                )

            destination = pooled[merge_key]
            destination.biogrid_ids.extend(record.biogrid_ids)
            destination.source_proteins |= record.source_proteins
            destination.raw_partner_symbols |= record.raw_partner_symbols
            destination.raw_accessions |= record.raw_accessions

            if not destination.accession and record.accession:
                destination.accession = record.accession
            if (not destination.partner_symbol or destination.partner_symbol == merge_key) and record.partner_symbol:
                destination.partner_symbol = record.partner_symbol

    return pooled
