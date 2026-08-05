"""Flask API smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import create_app
from defn_core.service import load_project

TEMPLATES = (
    Path(__file__).resolve().parents[1].parents[2]
    / "Catalyst Center Templates"
    / "Site BGP EVPN Templates"
)


@pytest.fixture
def client(tmp_path):
    work = tmp_path / "templates"
    if TEMPLATES.is_dir():
        for src in TEMPLATES.glob("DEFN-*.j2"):
            work.mkdir(parents=True, exist_ok=True)
            work.joinpath(src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    app = create_app()
    app.config["PROJECT_ROOT"] = work
    app.config["TESTING"] = True
    return app.test_client()


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"


def test_schema(client):
    res = client.get("/api/schema")
    assert res.status_code == 200
    data = res.get_json()
    assert "ui" in data
    assert len(data["ui"]) == 11


def test_load_validate_save_flow(client, tmp_path):
    work = Path(client.application.config["PROJECT_ROOT"])
    if not work.is_dir():
        pytest.skip("templates fixture missing")

    res = client.post("/api/project/load", json={"folder": str(work)})
    assert res.status_code == 200
    session = res.get_json()
    assert len(session["files"]) == 11

    res = client.post("/api/validate")
    assert res.status_code == 200

    res = client.post("/api/save")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["status"] == "ok"
    assert len(payload["written"]) == 11

    reloaded = load_project(work)
    assert reloaded["files"].keys() == session["files"].keys()
