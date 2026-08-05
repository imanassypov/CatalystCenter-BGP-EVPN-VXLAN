"""Validator unit tests."""

from __future__ import annotations

from defn_core.service import load_project
from defn_core.validators import validate_session

TEMPLATES = (
    __import__("pathlib").Path(__file__).resolve().parents[1].parents[2]
    / "Catalyst Center Templates"
    / "Site BGP EVPN Templates"
)


def test_l3out_loopback_aggregate_not_warned() -> None:
    session = load_project(TEMPLATES)
    issues = validate_session(session)
    loopback_warns = [
        i
        for i in issues
        if "198.18.100.0 255.255.255.0" in i["message"]
    ]
    assert not loopback_warns
