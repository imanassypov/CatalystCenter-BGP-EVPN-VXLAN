#!/usr/bin/env python3
"""DEFN Template Editor — load/save/validate CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from defn_core.service import load_project, save_project, validate_project

ROOT = Path(__file__).resolve().parent


def cmd_load(folder: Path, out: Path) -> int:
    try:
        session = load_project(folder)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(session, indent=2), encoding="utf-8")
    print(f"Loaded {len(session['files'])} DEFN files -> {out}")
    return 0


def cmd_save(folder: Path, session_path: Path, strict: bool = False) -> int:
    try:
        session = json.loads(session_path.read_text(encoding="utf-8"))
        result = save_project(folder, session, strict=strict)
    except Exception as exc:
        print(f"Save failed: {exc}", file=sys.stderr)
        return 1

    for issue in result["issues"]:
        print(f"[{issue['level'].upper()}] {issue['message']}", file=sys.stderr)
    print(f"Saved {len(result['written'])} DEFN files to {folder}")
    return 0


def cmd_validate(folder: Path, session_path: Path | None = None) -> int:
    session = None
    if session_path:
        session = json.loads(session_path.read_text(encoding="utf-8"))
        folder = Path(session.get("project_folder", folder))

    issues = validate_project(folder, session)
    errors = 0
    for issue in issues:
        print(f"[{issue['level'].upper()}] {issue['message']}")
        if issue["level"] == "error":
            errors += 1

    if errors:
        return 1
    print(f"All DEFN files in {folder} passed validation.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="DEFN Template Editor I/O")
    sub = parser.add_subparsers(dest="command", required=True)

    p_load = sub.add_parser("load", help="Load DEFN folder into session JSON")
    p_load.add_argument("--folder", type=Path, required=True)
    p_load.add_argument("--out", type=Path, required=True)

    p_save = sub.add_parser("save", help="Write session JSON back to DEFN folder")
    p_save.add_argument("--folder", type=Path, required=True)
    p_save.add_argument("--in", dest="session_in", type=Path, required=True)
    p_save.add_argument("--strict", action="store_true")

    p_val = sub.add_parser("validate", help="Validate Jinja2 syntax and cross-DEFN rules")
    p_val.add_argument("--folder", type=Path, required=True)
    p_val.add_argument("--session", type=Path, default=None)

    args = parser.parse_args()
    if args.command == "load":
        return cmd_load(args.folder, args.out)
    if args.command == "save":
        return cmd_save(args.folder, args.session_in, strict=args.strict)
    if args.command == "validate":
        return cmd_validate(args.folder, args.session)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
