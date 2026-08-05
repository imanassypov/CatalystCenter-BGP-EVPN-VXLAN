"""Enforce additive-only edits: loaded values/rows cannot be changed or removed."""

from __future__ import annotations

import copy
from typing import Any


META_KEYS = frozenset({"_locked"})


def snapshot_session(session: dict[str, Any]) -> dict[str, Any]:
    """Deep-copy variable payloads at load time for later comparison."""
    files: dict[str, Any] = {}
    for filename, file_data in session.get("files", {}).items():
        variables: dict[str, Any] = {}
        for varname, payload in file_data.get("variables", {}).items():
            variables[varname] = copy.deepcopy(payload)
        files[filename] = {"variables": variables}
    return {"files": files}


def _strip_meta(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in META_KEYS}


def _rows_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return _strip_meta(left) == _strip_meta(right)


def _match_rows(
    snapshot_rows: list[dict[str, Any]], current_rows: list[dict[str, Any]]
) -> list[str]:
    """Return errors if any snapshot row was removed or modified."""
    errors: list[str] = []
    remaining = list(current_rows)

    for snap_row in snapshot_rows:
        match_idx = None
        for idx, curr_row in enumerate(remaining):
            if _rows_equal(snap_row, curr_row):
                match_idx = idx
                break
        if match_idx is None:
            errors.append(
                "existing row was modified or removed: "
                f"{_strip_meta(snap_row)!r}"
            )
        else:
            remaining.pop(match_idx)

    return errors


def validate_additive_only(session: dict[str, Any]) -> list[dict[str, str]]:
    """Ensure session only adds new rows; loaded scalars and rows are unchanged."""
    issues: list[dict[str, str]] = []
    snapshots = session.get("_snapshots", {})
    snap_files = snapshots.get("files", {})

    for filename, snap_file in snap_files.items():
        current_file = session.get("files", {}).get(filename)
        if not current_file:
            issues.append(
                {
                    "level": "error",
                    "message": f"Missing file data for {filename}",
                }
            )
            continue

        for varname, snap_payload in snap_file.get("variables", {}).items():
            current_payload = current_file.get("variables", {}).get(varname)
            if current_payload is None:
                issues.append(
                    {
                        "level": "error",
                        "message": f"Missing variable {filename}::{varname}",
                    }
                )
                continue

            snap_type = snap_payload.get("type")
            if snap_type == "scalar":
                if current_payload.get("value") != snap_payload.get("value"):
                    issues.append(
                        {
                            "level": "error",
                            "message": (
                                f"Cannot modify existing scalar {varname} in {filename}"
                            ),
                        }
                    )
                continue

            snap_rows = snap_payload.get("rows", [])
            curr_rows = current_payload.get("rows", [])
            for message in _match_rows(snap_rows, curr_rows):
                issues.append(
                    {
                        "level": "error",
                        "message": f"{filename} {varname}: {message}",
                    }
                )

    return issues
