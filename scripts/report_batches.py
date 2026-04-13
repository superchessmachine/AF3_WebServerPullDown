#!/usr/bin/env python3

from pathlib import Path
import json


def parse_args(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Summarize generated job-batch folders.")
    parser.add_argument("--output-root", required=True, help="Root output folder created by the generator")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    output_root = Path(args.output_root)
    if not output_root.exists():
        raise SystemExit(f"Output root not found: {output_root}")

    summary_path = output_root / "run_summary.json"
    if not summary_path.exists():
        raise SystemExit(f"run_summary.json not found in: {output_root}")

    data = json.loads(summary_path.read_text(encoding="utf-8"))
    job_sets = data.get("job_sets") or []
    for job_set in job_sets:
        job_set_id = job_set.get("job_set_id") or "UNKNOWN"
        print(
            f"{job_set_id}: "
            f"generated={job_set['generated_jobs']} "
            f"excluded={job_set['excluded_jobs']} "
            f"batches={job_set['batch_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
