from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._io import load_json, preflight, write_new
from .core import analyze, render_csv, render_json, render_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an evidence-gated delivery matrix.")
    parser.add_argument("input", type=Path, help="UTF-8 JSON input file")
    parser.add_argument("--format", choices=("markdown", "json", "csv"), default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--explain-blockers",
        action="store_true",
        help="include causal dependency paths in JSON or Markdown reports",
    )
    args = parser.parse_args(argv)
    try:
        if args.explain_blockers and args.format == "csv":
            raise ValueError("blocker explanations require JSON or Markdown output")
        report = analyze(
            load_json(args.input),
            explain_blockers=args.explain_blockers,
        )
        rendered = {
            "json": render_json,
            "markdown": render_markdown,
            "csv": render_csv,
        }[args.format](report)
        if args.output:
            preflight([args.output])
            write_new(args.output, rendered)
        else:
            sys.stdout.write(rendered)
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
