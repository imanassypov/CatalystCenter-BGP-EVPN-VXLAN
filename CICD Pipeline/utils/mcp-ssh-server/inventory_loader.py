"""Load MCP SSH inventory from CML (virl2_client) + static host definitions."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from virl2_client import ClientLibrary

_SERVER_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = _SERVER_DIR.parent.parent

DEFAULT_NODE_DEFINITIONS: dict[str, str] = {
    "cat9000v-uadp": "iosxe",
    "cat8000v": "iosxe",
    "nxosv9000": "nxos",
}

PLATFORM_ROLE: dict[str, str] = {
    "iosxe": "router",
    "nxos": "core",
    "linux": "linux",
}


def resolve_server_path(path_str: str) -> Path:
    """Resolve paths from env vars; relative to CICD Pipeline/ or mcp-ssh-server/."""
    path = Path(path_str).expanduser()
    if path.is_absolute():
        return path.resolve()
    for base in (PIPELINE_DIR, _SERVER_DIR):
        candidate = (base / path).resolve()
        if candidate.exists():
            return candidate
    return (PIPELINE_DIR / path).resolve()


@dataclass
class RawDevice:
    name: str
    host: str
    port: int
    username: str
    password: str | None
    key_path: str | None
    platform: str
    role: str
    tags: list[str]
    proxy_jump: str | None = None


def _normalize_tag(value: str) -> str:
    return value.strip().lower()


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _cml_credentials() -> tuple[str, str, str, str]:
    host = (os.getenv("CML_HOST") or "").strip()
    username = (os.getenv("CML_USERNAME") or "").strip()
    password = os.getenv("CML_PASSWORD") or ""
    if not host or not username or not password:
        raise ValueError(
            "CML inventory requires CML_HOST, CML_USERNAME, and CML_PASSWORD in the environment"
        )
    return host, username, password, (os.getenv("CML_LAB") or "").strip()


def _tags_from_cml(node_tags: list[str], group_tags: list[str]) -> list[str]:
    allow = {_normalize_tag(tag) for tag in group_tags}
    tags: list[str] = []
    for tag in node_tags:
        norm = _normalize_tag(tag)
        if norm in allow or tag in group_tags:
            tags.append(norm)
    return tags


def _resolve_ssh_target(
    node: Any,
    cml_host: str,
) -> tuple[str | None, int]:
    """Management IP/port from interfaces or CML PAT tags."""
    ssh_host: str | None = None
    ssh_port = 22

    for tag in node.tags():
        pat_match = re.search(r"^pat:(?:tcp|udp)?:?(\d+):(\d+)", tag)
        if pat_match:
            ssh_host = cml_host
            ssh_port = int(pat_match.group(1))
            break
        fact_match = re.search(r"^ansible:ansible_port=(\d+)$", tag)
        if fact_match:
            ssh_port = int(fact_match.group(1))

    if ssh_host:
        return ssh_host, ssh_port

    if node.state != "BOOTED":
        return None, ssh_port

    for interface in node.interfaces():
        if interface.discovered_ipv4:
            return interface.discovered_ipv4[0], ssh_port

    return None, ssh_port


def _load_cml_devices(config: dict[str, Any]) -> dict[str, RawDevice]:
    cml_host, username, password, env_lab = _cml_credentials()
    lab_name = (config.get("lab") or env_lab or "BGP EVPN Campus").strip()
    group_tags = [str(tag) for tag in (config.get("group_tags") or [])]
    node_defs = dict(DEFAULT_NODE_DEFINITIONS)
    node_defs.update(config.get("ssh_node_definitions") or {})

    device_username = str(config.get("device_username") or os.getenv("MCP_DEVICE_USERNAME", "net-admin"))
    password_env = str(config.get("device_password_env") or os.getenv("MCP_DEVICE_PASSWORD_ENV", "IOSXE_PASS"))
    device_password = os.getenv("MCP_DEVICE_PASSWORD") or f"env:{password_env}"

    client = ClientLibrary(
        f"https://{cml_host}",
        username=username,
        password=password,
        ssl_verify=False,
    )
    labs = client.find_labs_by_title(lab_name)
    if not labs:
        raise ValueError(f"CML lab not found: {lab_name!r}")

    lab = labs[0]
    lab.sync()
    devices: dict[str, RawDevice] = {}

    for node in lab.nodes():
        platform = node_defs.get(node.node_definition)
        if not platform:
            continue

        ssh_host, ssh_port = _resolve_ssh_target(node, cml_host)
        if not ssh_host:
            continue

        node_tags = list(node.tags())
        devices[node.label.lower()] = RawDevice(
            name=node.label,
            host=ssh_host,
            port=ssh_port,
            username=device_username,
            password=device_password,
            key_path=None,
            platform=platform,
            role=PLATFORM_ROLE.get(platform, "unknown"),
            tags=_tags_from_cml(node_tags, group_tags),
            proxy_jump=None,
        )

    return devices


def _load_static_hosts(static_path: Path) -> dict[str, RawDevice]:
    if not static_path.is_file():
        return {}

    data = _load_yaml(static_path)
    hosts_raw = data.get("hosts") or {}
    devices: dict[str, RawDevice] = {}

    for name, vars_ in hosts_raw.items():
        if not isinstance(vars_, dict):
            continue
        host = vars_.get("host") or vars_.get("ansible_host")
        username = vars_.get("username") or vars_.get("mcp_username")
        if not host or not username:
            continue

        tags = vars_.get("tags") or vars_.get("mcp_tags") or []
        platform = str(vars_.get("platform") or vars_.get("mcp_platform") or "linux").lower()
        role = str(vars_.get("role") or vars_.get("mcp_role") or "unknown").lower()

        devices[name.lower()] = RawDevice(
            name=name,
            host=str(host),
            port=int(vars_.get("port") or vars_.get("mcp_port") or vars_.get("ansible_port") or 22),
            username=str(username),
            password=vars_.get("password") or vars_.get("mcp_password"),
            key_path=vars_.get("key_path") or vars_.get("mcp_key_path"),
            platform=platform,
            role=role,
            tags=[_normalize_tag(t) for t in tags],
            proxy_jump=vars_.get("proxy_jump") or vars_.get("mcp_proxy_jump"),
        )

    return devices


def default_static_hosts_path() -> Path:
    env_path = os.getenv("MCP_SSH_STATIC_HOSTS")
    if env_path:
        return resolve_server_path(env_path)
    legacy_overlay = os.getenv("MCP_SSH_OVERLAY")
    if legacy_overlay:
        return resolve_server_path(legacy_overlay)
    return _SERVER_DIR / "inventory" / "static_hosts.yml"


def load_mcp_inventory(
    cml_config_path: Path,
    *,
    static_hosts_path: Path | None = None,
) -> dict[str, RawDevice]:
    """Return devices keyed by lowercased name from CML + static MCP hosts."""
    cml_config_path = cml_config_path.expanduser().resolve()
    if not cml_config_path.is_file():
        raise FileNotFoundError(f"CML config not found: {cml_config_path}")

    static_path = static_hosts_path or default_static_hosts_path()
    config = _load_yaml(cml_config_path)

    devices = _load_cml_devices(config)
    devices.update(_load_static_hosts(static_path))

    if not devices:
        raise ValueError(
            f"No SSH devices resolved from {cml_config_path} "
            f"(static: {static_path}). Is the CML lab running?"
        )
    return devices
