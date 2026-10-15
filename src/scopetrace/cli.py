from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
            json.loads(args.input.read_text(encoding="utf-8")),
            explain_blockers=args.explain_blockers,
        )
        rendered = {
            "json": render_json,
            "markdown": render_markdown,
            "csv": render_csv,
        }[args.format](report)
        if args.output:
            if args.output.exists():
                raise ValueError(f"output already exists: {args.output}")
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
