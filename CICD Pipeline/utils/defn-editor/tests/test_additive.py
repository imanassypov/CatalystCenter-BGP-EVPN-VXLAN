"""Additive-only edit enforcement tests."""

from __future__ import annotations

import copy

from defn_core.additive import snapshot_session, validate_additive_only
from defn_core.service import load_project

TEMPLATES = (
    __import__("pathlib").Path(__file__).resolve().parents[1].parents[2]
    / "Catalyst Center Templates"
    / "Site BGP EVPN Templates"
)


def test_snapshot_allows_new_rows_only() -> None:
    session = load_project(TEMPLATES)
    assert "_snapshots" in session
    assert not validate_additive_only(session)

    mutated = copy.deepcopy(session)
    rows = mutated["files"]["DEFN-OVERLAY.j2"]["variables"]["DEFN_OVERLAY"]["rows"]
    rows[0]["name"] = "changed-name"
    errors = validate_additive_only(mutated)
    assert any(e["level"] == "error" for e in errors)

    additive = copy.deepcopy(session)
    rows = additive["files"]["DEFN-OVERLAY.j2"]["variables"]["DEFN_OVERLAY"]["rows"]
    rows.append(
        {
            "vrf": "red",
            "vlan_id": "199",
            "name": "corp-199",
            "ipaddr": "198.18.199.1 255.255.255.0",
            "mac": "0000.0901.0199",
            "dhcp_helper": "198.19.2.78",
            "bum_addr": "239.190.100.199",
            "network": "198.18.199.0 255.255.255.0",
        }
    )
    assert not validate_additive_only(additive)


def test_scalar_cannot_change() -> None:
    session = load_project(TEMPLATES)
    mutated = copy.deepcopy(session)
    mutated["files"]["DEFN-OVERLAY.j2"]["variables"]["FABRIC_BGP_ASN"]["value"] = "65099"
    errors = validate_additive_only(mutated)
    assert any("FABRIC_BGP_ASN" in e["message"] for e in errors)
