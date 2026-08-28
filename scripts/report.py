#!/usr/bin/env python3
"""Backwards-compatible shim: `hmb report` is the supported entry point.

The runner scripts and older command lines call `python3 scripts/report.py`, so
this file stays. It forwards to the package, which holds the implementation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from harbor_methodology_bench.report import write_report  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate Harbor trial results.")
    parser.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    parser.add_argument("--pattern", type=str, default="*")
    parser.add_argument("--md-out", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    markdown, trials = write_report(args.jobs_dir, args.pattern, args.md_out, args.json_out)
    print(f"Found {len(trials)} trial(s) in {args.jobs_dir} (pattern={args.pattern!r})\n")
    if args.md_out:
        print(f"markdown report -> {args.md_out}")
    else:
        print(markdown)
    if args.json_out:
        print(f"json summary    -> {args.json_out}")


if __name__ == "__main__":
    main()
