"""Cross-DEFN and schema validation for save operations."""

from __future__ import annotations

from typing import Any


def validate_session(session: dict[str, Any]) -> list[dict[str, str]]:
    """Return list of validation issues (error or warning)."""
    issues: list[dict[str, str]] = []
    files = session.get("files", {})

    overlay_networks = _overlay_red_networks(files)
    loopback_aggregates = _loop_overlay_red_aggregates(files)
    allowed_aggregates = overlay_networks | loopback_aggregates
    aggregates = _l3out_aggregates(files)
    for prefix in aggregates:
        if prefix not in allowed_aggregates:
            issues.append(
                {
                    "level": "warning",
                    "message": (
                        f"L3OUT aggregate '{prefix}' has no matching DEFN_OVERLAY "
                        "network or red loopback overlay prefix (DEFN_LOOP_OVERLAY)"
                    ),
                }
            )

    roles = _role_hosts(files)
    for host in _client_port_hosts(files):
        if host not in roles.get("CLIENT", set()):
            issues.append(
                {
                    "level": "warning",
                    "message": f"CLIENT_PORTS hostname '{host}' not in DEFN_NODE_ROLES CLIENT",
                }
            )

    for host in _tunnel_nodes(files):
        if host not in roles.get("BORDER", set()):
            issues.append(
                {
                    "level": "warning",
                    "message": f"DEFN_TUNNELS node '{host}' not in DEFN_NODE_ROLES BORDER",
                }
            )

    for row in _l3out_nodes(files):
        if row not in roles.get("SPINE", set()):
            issues.append(
                {
                    "level": "warning",
                    "message": f"L3OUT node '{row}' not in DEFN_NODE_ROLES SPINE",
                }
            )

    return issues


def _file_var(files: dict[str, Any], filename: str, varname: str) -> dict[str, Any] | None:
    file_data = files.get(filename)
    if not file_data:
        return None
    return file_data.get("variables", {}).get(varname)


def _overlay_red_networks(files: dict[str, Any]) -> set[str]:
    payload = _file_var(files, "DEFN-OVERLAY.j2", "DEFN_OVERLAY")
    if not payload:
        return set()
    networks: set[str] = set()
    for row in payload.get("rows", []):
        if row.get("vrf") == "red" and row.get("network"):
            networks.add(str(row["network"]).strip())
    return networks


def _loop_overlay_red_aggregates(files: dict[str, Any]) -> set[str]:
    """Derive the red /24 summary for per-node Loopback901 (DEFN_LOOP_OVERLAY)."""
    payload = _file_var(files, "DEFN-LOOPBACKS.j2", "DEFN_LOOP_OVERLAY")
    if not payload:
        return set()
    for row in payload.get("rows", []):
        if str(row.get("key", "")).strip() != "red":
            continue
        prefix = str(row.get("value", "")).strip().rstrip(".")
        octets = [p for p in prefix.split(".") if p]
        if len(octets) >= 3:
            network = f"{octets[0]}.{octets[1]}.{octets[2]}.0 255.255.255.0"
            return {network}
    return set()


def _l3out_aggregates(files: dict[str, Any]) -> list[str]:
    payload = _file_var(files, "DEFN-L3OUT.j2", "DEFN_L3OUT_AGGREGATES")
    if not payload:
        return []
    return [
        str(row.get("prefix", "")).strip()
        for row in payload.get("rows", [])
        if row.get("prefix")
    ]


def _role_hosts(files: dict[str, Any]) -> dict[str, set[str]]:
    payload = _file_var(files, "DEFN-ROLES.j2", "DEFN_NODE_ROLES")
    result: dict[str, set[str]] = {}
    if not payload:
        return result
    for row in payload.get("rows", []):
        role = str(row.get("role", "")).strip()
        host = str(row.get("hostname", "")).strip()
        if role and host:
            result.setdefault(role, set()).add(host)
    return result


def _client_port_hosts(files: dict[str, Any]) -> set[str]:
    payload = _file_var(files, "DEFN-CLIENT-PORTS.j2", "DEFN_CLIENT_PORTS")
    if not payload:
        return set()
    return {
        str(row.get("hostname", "")).strip()
        for row in payload.get("rows", [])
        if row.get("hostname")
    }


def _tunnel_nodes(files: dict[str, Any]) -> set[str]:
    payload = _file_var(files, "DEFN-BORDER-DMZ-TUNNELS.j2", "DEFN_TUNNELS")
    if not payload:
        return set()
    return {str(row.get("node", "")).strip() for row in payload.get("rows", []) if row.get("node")}


def _l3out_nodes(files: dict[str, Any]) -> set[str]:
    payload = _file_var(files, "DEFN-L3OUT.j2", "DEFN_L3OUT")
    if not payload:
        return set()
    return {str(row.get("node", "")).strip() for row in payload.get("rows", []) if row.get("node")}
