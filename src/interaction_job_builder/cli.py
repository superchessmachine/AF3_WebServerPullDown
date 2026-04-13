from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .pipeline import run_generation


def build_parser() -> argparse.ArgumentParser:
    toolkit_root = Path(__file__).resolve().parents[2]
    repo_root = toolkit_root.parent

    parser = argparse.ArgumentParser(description="Generate reusable JSON job bundles from BioGRID-style protein interaction exports.")
    parser.add_argument("--repo-root", default=str(repo_root), help="Root of the project repo.")
    parser.add_argument("--input-data-dir", default="", help="Override the `input_data` directory.")
    parser.add_argument("--output-root", default="", help="Output directory for generated jobs and reports.")
    parser.add_argument(
        "--config",
        default=str(toolkit_root / "configs" / "job_sets.json"),
        help="Job-set configuration JSON.",
    )
    parser.add_argument(
        "--example-template",
        default="",
        help="Optional example job JSON used to infer dialect, version, and `useStructureTemplate`.",
    )
    parser.add_argument("--sequence-cache", default="", help="Optional TSV cache with `accession`, `gene_symbol`, and `sequence`.")
    parser.add_argument("--write-sequence-cache", default="", help="Optional TSV file to persist resolved sequences.")
    parser.add_argument("--batch-size", type=int, default=0, help="Override the batch size from the config.")
    parser.add_argument("--timeout", type=float, default=25.0, help="Timeout in seconds for UniProt requests.")
    parser.add_argument("--sleep", type=float, default=0.05, help="Delay between UniProt resolutions.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing JSON payload files.")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    try:
        repo_root = Path(args.repo_root).resolve()
        toolkit_root = Path(__file__).resolve().parents[2]
        input_data_dir = Path(args.input_data_dir).resolve() if args.input_data_dir else repo_root / "input_data"
        output_root = Path(args.output_root).resolve() if args.output_root else repo_root / "generated_job_output"
        config_path = Path(args.config).resolve()
        example_template_path = Path(args.example_template).resolve() if args.example_template else repo_root / "example_job_request.json"
        sequence_cache_path = Path(args.sequence_cache).resolve() if args.sequence_cache else None
        write_sequence_cache_path = Path(args.write_sequence_cache).resolve() if args.write_sequence_cache else None

        if not config_path.exists():
            raise FileNotFoundError(f"Missing config file: {config_path}")
        if not example_template_path.exists():
            fallback_template = toolkit_root / "templates" / "job_template.json"
            example_template_path = fallback_template

        run_generation(
            repo_root=repo_root,
            input_data_dir=input_data_dir,
            output_root=output_root,
            config_path=config_path,
            example_template_path=example_template_path,
            batch_size_override=args.batch_size or None,
            timeout=args.timeout,
            sleep=args.sleep,
            overwrite=args.overwrite,
            sequence_cache_path=sequence_cache_path,
            write_sequence_cache_path=write_sequence_cache_path,
        )
        return 0
    except (FileNotFoundError, RuntimeError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
