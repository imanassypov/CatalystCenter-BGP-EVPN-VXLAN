"""Normalize DEFN variable values between Jinja literals and flat table rows."""

from __future__ import annotations

from typing import Any


def normalize_variable(name: str, binding: str, value: Any) -> dict[str, Any]:
    """Convert a parsed Jinja value into session JSON variable payload."""
    if binding == "scalar":
        return {"type": "scalar", "value": value}

    if binding == "key_value_table":
        rows = [{"key": k, "value": v} for k, v in sorted(value.items())]
        return {"type": "key_value_table", "rows": rows}

    if binding == "role_host_table":
        rows: list[dict[str, str]] = []
        for role, hosts in sorted(value.items()):
            for host in hosts:
                rows.append({"role": role, "hostname": host})
        return {"type": "role_host_table", "rows": rows}

    if binding == "row_table":
        return {"type": "row_table", "rows": list(value)}

    if binding == "host_list_table":
        if name == "DEFN_TELEMETRY_SPLUNK_ROLES":
            rows = [{"role": r} for r in value]
        else:
            rows = [{"hostname": h} for h in value]
        return {"type": "host_list_table", "rows": rows}

    if binding == "prefix_list_table":
        rows = [{"prefix": p} for p in value]
        return {"type": "prefix_list_table", "rows": rows}

    if binding == "matrix_table":
        rows = [
            {"hostname": host, "vrf_ids": ",".join(vrf_ids)}
            for host, vrf_ids in sorted(value.items())
        ]
        return {"type": "matrix_table", "rows": rows}

    if binding == "overlay_vlan_table":
        rows = []
        for overlay in value:
            vrf = overlay["vrf"]
            for vlan_id in overlay.get("vlan_ids", []):
                params = overlay["vlans"][vlan_id]
                rows.append(
                    {
                        "vrf": vrf,
                        "vlan_id": vlan_id,
                        "name": params["name"],
                        "ipaddr": params["ipaddr"],
                        "mac": params["mac"],
                        "dhcp_helper": params["dhcp_helper"],
                        "bum_addr": params["bum_addr"],
                        "network": params["network"],
                    }
                )
        return {"type": "overlay_vlan_table", "rows": rows}

    if binding == "client_port_table":
        rows = []
        for hostname, ports in sorted(value.items()):
            for port in ports:
                rows.append({"hostname": hostname, **port})
        return {"type": "client_port_table", "rows": rows}

    if binding == "l3out_table":
        rows = []
        for entry in value:
            for iface in entry["interfaces"]:
                rows.append(
                    {
                        "vrf": entry["vrf"],
                        "node": entry["node"],
                        "neighbour_asn": entry["neighbour_asn"],
                        **iface,
                    }
                )
        return {"type": "l3out_table", "rows": rows}

    if binding == "nested_dict_table":
        rows = []
        for hostname, fields in sorted(value.items()):
            rows.append({"hostname": hostname, **fields})
        return {"type": "nested_dict_table", "rows": rows}

    if binding == "telemetry_subscription_table":
        rows = []
        for section in value:
            for sub in section["subscriptions"]:
                rows.append(
                    {
                        "section": section["section"],
                        "xpath": section["xpath"],
                        "subscription_id": sub["id"],
                        "policy": sub["policy"],
                        "period": sub.get("period", ""),
                    }
                )
        return {"type": "telemetry_subscription_table", "rows": rows}

    raise ValueError(f"Unknown binding type '{binding}' for variable {name}")


def denormalize_variable(name: str, binding: str, payload: dict[str, Any]) -> Any:
    """Convert session JSON variable payload back to a Jinja literal Python value."""
    if binding == "scalar":
        return payload["value"]

    if binding == "key_value_table":
        return {row["key"]: row["value"] for row in payload["rows"] if row.get("key")}

    if binding == "role_host_table":
        result: dict[str, list[str]] = {}
        for row in payload["rows"]:
            role = row.get("role", "").strip()
            host = row.get("hostname", "").strip()
            if not role or not host:
                continue
            result.setdefault(role, []).append(host)
        return result

    if binding == "row_table":
        return [_clean_row(row) for row in payload["rows"] if _row_has_data(row)]

    if binding == "host_list_table":
        if name == "DEFN_TELEMETRY_SPLUNK_ROLES":
            return [row["role"].strip() for row in payload["rows"] if row.get("role", "").strip()]
        return [row["hostname"].strip() for row in payload["rows"] if row.get("hostname", "").strip()]

    if binding == "prefix_list_table":
        return [row["prefix"].strip() for row in payload["rows"] if row.get("prefix", "").strip()]

    if binding == "matrix_table":
        result = {}
        for row in payload["rows"]:
            host = row.get("hostname", "").strip()
            if not host:
                continue
            raw = row.get("vrf_ids", "")
            vrf_ids = [v.strip() for v in str(raw).split(",") if v.strip()]
            result[host] = vrf_ids
        return result

    if binding == "overlay_vlan_table":
        by_vrf: dict[str, dict[str, Any]] = {}
        vlan_order: dict[str, list[str]] = {}
        for row in payload["rows"]:
            vrf = row.get("vrf", "").strip()
            vlan_id = str(row.get("vlan_id", "")).strip()
            if not vrf or not vlan_id:
                continue
            if vrf not in by_vrf:
                by_vrf[vrf] = {"vrf": vrf, "vlan_ids": [], "vlans": {}}
                vlan_order[vrf] = []
            if vlan_id not in vlan_order[vrf]:
                vlan_order[vrf].append(vlan_id)
            by_vrf[vrf]["vlan_ids"] = vlan_order[vrf]
            by_vrf[vrf]["vlans"][vlan_id] = {
                "name": row["name"],
                "ipaddr": row["ipaddr"],
                "mac": row["mac"],
                "dhcp_helper": row["dhcp_helper"],
                "bum_addr": row["bum_addr"],
                "network": row["network"],
            }
        return list(by_vrf.values())

    if binding == "client_port_table":
        result: dict[str, list[dict[str, Any]]] = {}
        for row in payload["rows"]:
            host = row.get("hostname", "").strip()
            port = row.get("port", "").strip()
            if not host or not port:
                continue
            entry = {
                "port": port,
                "vlan": str(row["vlan"]),
                "description": row["description"],
                "portfast": _to_bool(row.get("portfast")),
                "mode": row["mode"],
            }
            result.setdefault(host, []).append(entry)
        return result

    if binding == "l3out_table":
        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in payload["rows"]:
            vrf = row.get("vrf", "").strip()
            node = row.get("node", "").strip()
            asn = str(row.get("neighbour_asn", "")).strip()
            if not vrf or not node:
                continue
            key = (vrf, node, asn)
            if key not in grouped:
                grouped[key] = {
                    "vrf": vrf,
                    "node": node,
                    "neighbour_asn": asn,
                    "interfaces": [],
                }
            iface = {
                "ifname": row["ifname"],
                "parent": row["parent"],
                "name": row["name"],
                "vlan": str(row["vlan"]),
                "ipaddr": row["ipaddr"],
                "neighbour": row["neighbour"],
            }
            grouped[key]["interfaces"].append(iface)
        return list(grouped.values())

    if binding == "nested_dict_table":
        result = {}
        for row in payload["rows"]:
            host = row.get("hostname", "").strip()
            if not host:
                continue
            fields = {k: v for k, v in row.items() if k != "hostname"}
            result[host] = fields
        return result

    if binding == "telemetry_subscription_table":
        sections: dict[tuple[str, str], dict[str, Any]] = {}
        order: list[tuple[str, str]] = []
        for row in payload["rows"]:
            section = row.get("section", "").strip()
            xpath = row.get("xpath", "").strip()
            sub_id = str(row.get("subscription_id", "")).strip()
            if not section or not xpath or not sub_id:
                continue
            key = (section, xpath)
            if key not in sections:
                sections[key] = {"section": section, "xpath": xpath, "subscriptions": []}
                order.append(key)
            sections[key]["subscriptions"].append(
                {
                    "id": sub_id,
                    "policy": row["policy"],
                    "period": row.get("period", ""),
                }
            )
        return [sections[k] for k in order]

    raise ValueError(f"Unknown binding type '{binding}' for variable {name}")


def derive_client_port_devices(client_ports_payload: dict[str, Any]) -> list[str]:
    hosts = sorted(
        {
            row.get("hostname", "").strip()
            for row in client_ports_payload.get("rows", [])
            if row.get("hostname", "").strip()
        }
    )
    return hosts


def _row_has_data(row: dict[str, Any]) -> bool:
    return any(str(v).strip() for v in row.values() if v is not None)


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in row.items():
        if key in {"_locked"}:
            continue
        if key == "dnac_managed":
            cleaned[key] = _to_bool(value)
        elif isinstance(value, str):
            cleaned[key] = value.strip()
        else:
            cleaned[key] = value
    return cleaned


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y"}
