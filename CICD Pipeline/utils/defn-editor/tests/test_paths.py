"""Project path resolution tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from defn_core.paths import resolve_project_path

TEMPLATES = (
    Path(__file__).resolve().parents[1].parents[2]
    / "Catalyst Center Templates"
    / "Site BGP EVPN Templates"
)


def test_resolve_absolute_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not TEMPLATES.is_dir():
        pytest.skip("templates missing")
    for src in TEMPLATES.glob("DEFN-*.j2"):
        (tmp_path / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setenv("ALLOWED_PATH_ROOTS", str(tmp_path))
    resolved = resolve_project_path(str(tmp_path))
    assert resolved == tmp_path.resolve()


def test_reject_path_outside_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    other = tmp_path / "other"
    allowed.mkdir()
    other.mkdir()
    (other / "DEFN-TEST.j2").write_text("{% set X = 1 %}", encoding="utf-8")
    monkeypatch.setenv("ALLOWED_PATH_ROOTS", str(allowed))
    with pytest.raises(ValueError, match="allowed roots"):
        resolve_project_path(str(other))


def test_reject_relative_path() -> None:
    with pytest.raises(ValueError, match="absolute path"):
        resolve_project_path("relative/folder")
