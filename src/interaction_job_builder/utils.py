from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple


def log(message: str) -> None:
    print(message, flush=True)


def safe_name(text: str, max_len: int = 180) -> str:
    clean = re.sub(r"[^\w\.-]+", "_", (text or "").strip())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return (clean or "item")[:max_len]


def normalize_header_name(name: str) -> str:
    clean = (name or "").strip().replace("\r", "")
    if clean.startswith("#"):
        clean = clean[1:].strip()
    return clean


def first_token(cell: str) -> str:
    if cell is None:
        return ""
    value = str(cell).strip()
    if not value or value == "-":
        return ""
    for separator in ("|", ";", ",", " "):
        if separator in value:
            value = value.split(separator, 1)[0].strip()
    if "-" in value:
        value = value.split("-", 1)[0].strip()
    return value.upper()


def detect_delimiter(sample: str) -> str:
    return "\t" if sample.count("\t") > sample.count(",") else ","


def read_table(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        if not sample:
            return [], []
        handle.seek(0)
        delimiter = detect_delimiter(sample)
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            raw_header = next(reader)
        except StopIteration:
            return [], []

        header = [normalize_header_name(item) for item in raw_header]
        rows: List[Dict[str, str]] = []
        for parts in reader:
            if not parts or not any(str(item).strip() for item in parts):
                continue
            if len(parts) < len(header):
                parts += [""] * (len(header) - len(parts))
            elif len(parts) > len(header):
                parts = parts[: len(header)]
            cleaned = [str(item).strip().replace("\r", "") for item in parts]
            rows.append({header[index]: cleaned[index] for index in range(len(header))})
        return header, rows


def parse_sequence_blocks(path: Path) -> Dict[str, str]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"(?ms)^\s*([A-Za-z0-9_+-]+)\s*:\s*\n([A-Z\n]+?)(?=^\s*[A-Za-z0-9_+-]+\s*:\s*$|\Z)")
    sequences: Dict[str, str] = {}
    for match in pattern.finditer(text + "\n"):
        name = match.group(1).strip().upper()
        sequence = re.sub(r"\s+", "", match.group(2)).upper()
        if sequence:
            sequences[name] = sequence
    if not sequences:
        raise ValueError(f"No named sequence blocks found in {path}")
    return sequences


def load_example_template(example_json_path: Path) -> Tuple[str, int, bool]:
    dialect = "alphafoldserver"
    version = 2
    use_structure_template = True

    if not example_json_path.exists():
        return dialect, version, use_structure_template

    try:
        data = json.loads(example_json_path.read_text(encoding="utf-8"))
        first = data[0] if isinstance(data, list) and data else data
        dialect = first.get("dialect", dialect)
        version = int(first.get("version", version))
        for item in first.get("sequences", []):
            protein_chain = item.get("proteinChain") if isinstance(item, dict) else None
            if isinstance(protein_chain, dict) and "useStructureTemplate" in protein_chain:
                use_structure_template = bool(protein_chain["useStructureTemplate"])
                break
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass

    return dialect, version, use_structure_template


def deterministic_seed(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return str(int(digest[:15], 16) % 2_000_000_000 + 1)


def chunked(items: List, size: int) -> List[List]:
    return [items[index : index + size] for index in range(0, len(items), size)]
