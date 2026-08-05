"""Round-trip tests for DEFN Template Editor."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEFN_IO = ROOT / "defn_io.py"
TEMPLATES = ROOT.parents[2] / "Catalyst Center Templates" / "Site BGP EVPN Templates"


@pytest.fixture
def templates_dir() -> Path:
    assert TEMPLATES.is_dir(), f"Missing templates: {TEMPLATES}"
    return TEMPLATES


def run_defn_io(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DEFN_IO), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_load_all_defn_files(templates_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "session.json"
    result = run_defn_io("load", "--folder", str(templates_dir), "--out", str(out))
    assert result.returncode == 0, result.stderr
    session = json.loads(out.read_text())
    assert len(session["files"]) == 11


def test_roundtrip_preserves_jinja_parse(templates_dir: Path, tmp_path: Path) -> None:
    work = tmp_path / "work"
    shutil.copytree(templates_dir, work)
    session = tmp_path / "session.json"

    load = run_defn_io("load", "--folder", str(work), "--out", str(session))
    assert load.returncode == 0, load.stderr

    save = run_defn_io("save", "--folder", str(work), "--in", str(session))
    assert save.returncode == 0, save.stderr

    validate = run_defn_io("validate", "--folder", str(work))
    assert validate.returncode == 0, validate.stderr


def test_roundtrip_values_equivalent(templates_dir: Path, tmp_path: Path) -> None:
    from defn_core.parser import parse_defn_file

    work = tmp_path / "work"
    shutil.copytree(templates_dir, work)
    session_path = tmp_path / "session.json"

    assert run_defn_io("load", "--folder", str(work), "--out", str(session_path)).returncode == 0
    assert run_defn_io("save", "--folder", str(work), "--in", str(session_path)).returncode == 0

    for path in sorted(work.glob("DEFN-*.j2")):
        original = parse_defn_file(templates_dir / path.name)
        roundtrip = parse_defn_file(path)
        assert original.variables() == roundtrip.variables(), path.name


def test_validate_cli(templates_dir: Path) -> None:
    result = run_defn_io("validate", "--folder", str(templates_dir))
    assert result.returncode == 0, result.stderr
