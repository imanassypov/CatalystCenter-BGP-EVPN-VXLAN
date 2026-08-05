"""Schema loading and UI projection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "defn_schema.yaml"


def load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def binding_for(schema: dict[str, Any], filename: str, var_name: str) -> str:
    for var in schema["files"][filename]["variables"]:
        if var["name"] == var_name:
            return var["binding"]
    raise KeyError(f"No schema binding for {filename}::{var_name}")


def ui_schema(schema: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return sheet tabs and editable variables (skips derived bindings)."""
    schema = schema or load_schema()
    tabs: list[dict[str, Any]] = []
    for sheet_name, sheet_def in schema.get("sheets", {}).items():
        if sheet_name == "Control":
            continue
        filename = sheet_def.get("file")
        if not filename:
            continue
        variables = []
        for var in schema["files"][filename]["variables"]:
            if var.get("derived_from"):
                continue
            variables.append(var)
        tabs.append(
            {
                "name": sheet_name,
                "file": filename,
                "description": sheet_def.get("description", ""),
                "variables": variables,
            }
        )
    return tabs
