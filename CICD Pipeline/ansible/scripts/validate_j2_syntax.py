#!/usr/bin/env python3
"""Parse all .j2 templates with Jinja2 to catch syntax errors in {% %} / {{ }} blocks."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from jinja2 import Environment, TemplateSyntaxError
except ImportError:
    print("jinja2 is required: pip install jinja2", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[3]
GLOBS = (
    "Catalyst Center Templates/**/*.j2",
    "CICD Pipeline/ansible/**/*.j2",
)


def main() -> int:
    env = Environment(extensions=["jinja2.ext.do"])
    errors: list[str] = []

    for pattern in GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            source = path.read_text(encoding="utf-8")
            try:
                env.parse(source)
            except TemplateSyntaxError as exc:
                rel = path.relative_to(ROOT)
                errors.append(f"{rel}:{exc.lineno}: {exc.message}")

    if errors:
        print("Jinja2 syntax errors:\n", file=sys.stderr)
        for line in errors:
            print(f"  {line}", file=sys.stderr)
        return 1

    print("All .j2 templates passed Jinja2 parse check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
