"""Resolve and validate project folder paths (host + Docker)."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path


def allowed_roots() -> list[Path]:
    """Return allowed host path roots; empty list means no restriction (local dev)."""
    raw = os.environ.get("ALLOWED_PATH_ROOTS", "").strip()
    if not raw:
        return []
    return [Path(part).expanduser().resolve() for part in raw.split(os.pathsep) if part.strip()]


def resolve_project_path(folder: str | Path) -> Path:
    """
    Resolve a user-supplied folder to an absolute path inside allowed roots.

    In Docker, mount the host home (or broader path) at the same absolute path
    so /Users/you/... on the host is visible at /Users/you/... in the container.
    """
    path = Path(folder).expanduser()
    if not path.is_absolute():
        raise ValueError(f"Project folder must be an absolute path: {folder}")

    resolved = path.resolve()
    if not resolved.is_dir():
        raise ValueError(f"Project folder not found: {resolved}")

    roots = allowed_roots()
    if roots and not any(resolved == root or root in resolved.parents for root in roots):
        allowed = ", ".join(str(r) for r in roots)
        raise ValueError(f"Path must be under allowed roots: {allowed}")

    defn_files = list(resolved.glob("DEFN-*.j2"))
    if not defn_files:
        raise ValueError(f"No DEFN-*.j2 files in {resolved}")

    return resolved


def default_project_folder() -> Path:
    """Default folder shown in the UI (may be overridden by user)."""
    env = os.environ.get("DEFN_DEFAULT_FOLDER", "").strip()
    if env:
        return Path(env).expanduser()
    return Path(os.environ.get("DEFN_PROJECT_ROOT", "/data/templates")).expanduser()


def native_pick_folder() -> str | None:
    """
    Open a native folder picker on macOS (host only, not inside Linux Docker).

    Returns an absolute path or None if cancelled / unavailable.
    """
    if platform.system() != "Darwin":
        return None
    if os.environ.get("DEFN_NATIVE_PICKER", "1") != "1":
        return None
    script = 'POSIX path of (choose folder with prompt "Select DEFN project folder")'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    path = result.stdout.strip()
    return path or None
