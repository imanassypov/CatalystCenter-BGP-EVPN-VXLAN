"""High-level load/save/validate operations for DEFN projects."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from defn_core.additive import snapshot_session, validate_additive_only
from defn_core.normalizers import (
    denormalize_variable,
    derive_client_port_devices,
    normalize_variable,
)
from defn_core.parser import list_defn_files, parse_defn_file, parse_defn_source, validate_jinja_syntax
from defn_core.schema import load_schema
from defn_core.serializer import render_defn_file
from defn_core.validators import validate_session


def ensure_within_root(path: Path, root: Path) -> Path:
    """Resolve path and verify it stays inside root."""
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise PermissionError(f"Path outside project root: {path}") from exc
    return resolved


def _file_entry_from_parsed(parsed: Any, filename: str, schema: dict[str, Any]) -> dict[str, Any]:
    file_entry: dict[str, Any] = {
        "path": filename,
        "catc_header": parsed.catc_header,
        "file_leading": parsed.file_leading,
        "file_trailing": parsed.file_trailing,
        "set_order": [s["name"] for s in parsed.sets],
        "preambles": {s["name"]: s["preamble"] for s in parsed.sets},
        "trailings": {s["name"]: s["trailing"] for s in parsed.sets},
        "variables": {},
    }
    for var_def in schema["files"][filename]["variables"]:
        name = var_def["name"]
        binding = var_def["binding"]
        if var_def.get("derived_from"):
            continue
        raw = parsed.variables().get(name)
        if raw is None:
            continue
        file_entry["variables"][name] = normalize_variable(name, binding, raw)
    return file_entry


def load_project(folder: Path) -> dict[str, Any]:
    schema = load_schema()
    folder = folder.resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")

    session: dict[str, Any] = {
        "project_folder": str(folder),
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": schema.get("version", 1),
        "files": {},
    }

    for path in list_defn_files(folder):
        filename = path.name
        if filename not in schema["files"]:
            continue
        parsed = parse_defn_file(path)
        file_entry = _file_entry_from_parsed(parsed, filename, schema)
        file_entry["path"] = str(path)
        session["files"][filename] = file_entry

    session["load_mode"] = "path"
    session["_snapshots"] = snapshot_session(session)
    return session


def load_project_from_files(files: dict[str, str], folder_label: str) -> dict[str, Any]:
    """Load a project from uploaded/picked file contents (browser folder picker)."""
    schema = load_schema()
    if not files:
        raise ValueError("No DEFN files provided")

    session: dict[str, Any] = {
        "project_folder": folder_label,
        "load_mode": "browser",
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": schema.get("version", 1),
        "files": {},
    }

    for filename, source in sorted(files.items()):
        if not filename.startswith("DEFN-") or not filename.endswith(".j2"):
            continue
        if filename not in schema["files"]:
            continue
        parsed = parse_defn_source(source, filename)
        session["files"][filename] = _file_entry_from_parsed(parsed, filename, schema)

    if not session["files"]:
        raise ValueError("No recognized DEFN-*.j2 files in selection")

    session["_snapshots"] = snapshot_session(session)
    return session


def render_session_files(session: dict[str, Any]) -> dict[str, str]:
    """Render all DEFN files from session to source text."""
    schema = load_schema()
    rendered: dict[str, str] = {}
    for filename, file_data in session["files"].items():
        sets = session_to_parsed_sets(session, filename, schema)
        content = render_defn_file(
            catc_header=file_data.get("catc_header", ""),
            file_leading=file_data.get("file_leading", ""),
            sets=sets,
            file_trailing=file_data.get("file_trailing", ""),
        )
        validate_jinja_syntax(content, label=filename)
        rendered[filename] = content
    return rendered


def session_to_parsed_sets(
    session: dict[str, Any], filename: str, schema: dict[str, Any]
) -> list[dict[str, Any]]:
    file_data = session["files"][filename]
    sets: list[dict[str, Any]] = []
    for var_def in schema["files"][filename]["variables"]:
        name = var_def["name"]
        binding = var_def["binding"]
        payload = file_data["variables"].get(name)
        if payload is None and not var_def.get("derived_from"):
            continue
        if var_def.get("derived_from"):
            if name == "DEFN_CLIENT_PORT_DEVICES":
                ports_payload = file_data["variables"].get("DEFN_CLIENT_PORTS")
                value = derive_client_port_devices(ports_payload) if ports_payload else []
            else:
                continue
        else:
            value = denormalize_variable(name, binding, payload)
        sets.append(
            {
                "name": name,
                "value": value,
                "preamble": file_data.get("preambles", {}).get(name, ""),
                "trailing": file_data.get("trailings", {}).get(name, ""),
            }
        )

    order = file_data.get("set_order")
    if order:
        order_index = {n: i for i, n in enumerate(order)}
        sets.sort(key=lambda s: order_index.get(s["name"], 999))

    return sets


def save_project(
    folder: Path,
    session: dict[str, Any],
    *,
    strict: bool = False,
    backup: bool = True,
) -> dict[str, Any]:
    folder = folder.resolve()

    issues = validate_additive_only(session)
    issues.extend(validate_session(session))
    if any(i["level"] == "error" for i in issues):
        raise ValueError(
            issues[0]["message"] if issues else "Save aborted due to validation errors"
        )
    if strict and any(i["level"] == "warning" for i in issues):
        raise ValueError("Save aborted due to validation warnings (strict mode)")

    written: list[str] = []
    backups: list[str] = []
    file_contents = render_session_files(session)

    for filename, content in file_contents.items():
        target = folder / filename

        if target.exists() and backup:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = target.with_suffix(target.suffix + f".bak.{ts}")
            shutil.copy2(target, backup_path)
            backups.append(str(backup_path))

        target.write_text(content, encoding="utf-8")
        written.append(str(target))

    session["_snapshots"] = snapshot_session(session)

    return {
        "written": written,
        "backups": backups,
        "issues": issues,
        "files": file_contents,
    }


def save_session(session: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    """Validate and render session; write to disk (path mode) or return files (browser mode)."""
    if session.get("load_mode") == "path" and session.get("project_folder"):
        from defn_core.paths import resolve_project_path

        folder = resolve_project_path(session["project_folder"])
        return save_project(folder, session, strict=strict)

    issues = validate_additive_only(session)
    issues.extend(validate_session(session))
    if any(i["level"] == "error" for i in issues):
        raise ValueError(
            issues[0]["message"] if issues else "Save aborted due to validation errors"
        )
    if strict and any(i["level"] == "warning" for i in issues):
        raise ValueError("Save aborted due to validation warnings (strict mode)")

    file_contents = render_session_files(session)
    session["_snapshots"] = snapshot_session(session)
    return {
        "written": [],
        "backups": [],
        "issues": issues,
        "files": file_contents,
    }


def validate_project(folder: Path | None, session: dict[str, Any] | None = None) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if session:
        issues.extend(validate_additive_only(session))
        issues.extend(validate_session(session))

    if folder is not None:
        for path in list_defn_files(folder):
            try:
                validate_jinja_syntax(path.read_text(encoding="utf-8"), label=path.name)
            except ValueError as exc:
                issues.append({"level": "error", "message": str(exc)})
    elif session and session.get("load_mode") == "browser":
        try:
            for filename, content in render_session_files(session).items():
                validate_jinja_syntax(content, label=filename)
        except ValueError as exc:
            issues.append({"level": "error", "message": str(exc)})

    return issues
