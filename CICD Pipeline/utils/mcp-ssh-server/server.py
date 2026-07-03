#!/usr/bin/env python3
"""MCP SSH server for IOS-XE routers and Splunk/Telegraf troubleshooting.

Environment variables:
- MCP_SSH_INVENTORY: Absolute/relative path to CSV inventory file.
                     Defaults to ./devices.csv
- MCP_SSH_DEFAULT_TIMEOUT: Per-command timeout in seconds (default: 30)

CSV columns:
- name (required)
- host (required)
- port (optional, default: 22)
- username (required)
- password (optional, plain value or env:VAR_NAME)
- key_path (optional, plain value or env:VAR_NAME)
- platform (optional, e.g. iosxe, linux)
- role (optional, e.g. router, hf)
- tags (optional, pipe-delimited)
- proxy_jump (optional, name of another inventory device to SSH-tunnel through)
"""

from __future__ import annotations

import csv
import os
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import paramiko
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("ssh-inventory-server")


@dataclass
class Device:
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


def _resolve_secret(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value.startswith("env:"):
        env_name = value.split(":", 1)[1]
        return os.getenv(env_name)
    return value


def _load_inventory() -> dict[str, Device]:
    inventory_path = os.getenv("MCP_SSH_INVENTORY", "devices.csv")
    csv_path = Path(inventory_path).expanduser().resolve()
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Inventory file not found: {csv_path}. "
            "Set MCP_SSH_INVENTORY or create devices.csv"
        )

    devices: dict[str, Device] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("name") or "").strip()
            host = (row.get("host") or "").strip()
            username = (row.get("username") or "").strip()
            if not name or not host or not username:
                continue

            port_raw = (row.get("port") or "22").strip()
            try:
                port = int(port_raw)
            except ValueError:
                port = 22

            platform = (row.get("platform") or "unknown").strip().lower()
            role = (row.get("role") or "unknown").strip().lower()
            tags_raw = (row.get("tags") or "").strip()
            tags = [t.strip().lower() for t in tags_raw.split("|") if t.strip()]

            devices[name.lower()] = Device(
                name=name,
                host=host,
                port=port,
                username=username,
                password=_resolve_secret((row.get("password") or "").strip()),
                key_path=_resolve_secret((row.get("key_path") or "").strip()),
                platform=platform,
                role=role,
                tags=tags,
                proxy_jump=((row.get("proxy_jump") or "").strip() or None),
            )

    if not devices:
        raise ValueError(f"No valid devices found in inventory: {csv_path}")

    return devices


def _is_iosxe(device: Device) -> bool:
    return device.platform in {"iosxe", "ios_xe", "ios", "cisco_ios", "cat9k"}


def _load_private_key(key_path: str) -> paramiko.PKey:
    """Load a private key, trying each supported type.

    Passing ``key_filename`` to ``SSHClient.connect`` lets paramiko guess the
    key type, which can surface confusing errors like
    "encountered RSA key, expected OPENSSH key" when the guesses are tried in an
    unhelpful order. Loading explicitly avoids that.
    """
    path = os.path.expanduser(key_path)
    last_exc: Exception | None = None
    for key_cls in (
        paramiko.Ed25519Key,
        paramiko.RSAKey,
        paramiko.ECDSAKey,
        paramiko.DSSKey,
    ):
        try:
            return key_cls.from_private_key_file(path)
        except paramiko.SSHException as exc:
            last_exc = exc
    raise paramiko.SSHException(
        f"Unable to load private key '{key_path}': {last_exc}"
    )


def _connect(
    device: Device,
    timeout: int,
    inventory: dict[str, Device] | None = None,
) -> paramiko.SSHClient:
    sock = None
    jump_client = None

    # If the device must be reached through a bastion, connect to the bastion
    # first and open a direct-tcpip channel to the target, used as the socket.
    if device.proxy_jump:
        if inventory is None:
            inventory = _load_inventory()
        jump = inventory.get(device.proxy_jump.strip().lower())
        if jump is None:
            raise ValueError(
                f"proxy_jump device '{device.proxy_jump}' for '{device.name}' "
                "not found in inventory"
            )
        # Recurse so chained jump hosts are supported.
        jump_client = _connect(jump, timeout, inventory)
        transport = jump_client.get_transport()
        sock = transport.open_channel(
            "direct-tcpip",
            (device.host, device.port),
            ("127.0.0.1", 0),
            timeout=timeout,
        )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: dict[str, Any] = {
        "hostname": device.host,
        "port": device.port,
        "username": device.username,
        "timeout": timeout,
        "look_for_keys": False,
        "allow_agent": False,
    }

    if sock is not None:
        connect_kwargs["sock"] = sock
    if device.key_path:
        connect_kwargs["pkey"] = _load_private_key(device.key_path)
    if device.password:
        connect_kwargs["password"] = device.password

    try:
        client.connect(**connect_kwargs)
    except Exception:
        if jump_client is not None:
            jump_client.close()
        raise

    # Tie the bastion connection's lifetime to this client (see _close_client).
    if jump_client is not None:
        client._jump_client = jump_client  # type: ignore[attr-defined]
    return client


def _close_client(client: paramiko.SSHClient) -> None:
    """Close a client and any bastion clients chained behind it."""
    jump = getattr(client, "_jump_client", None)
    try:
        client.close()
    finally:
        if jump is not None:
            _close_client(jump)


def _run_exec_command(client: paramiko.SSHClient, command: str, timeout: int) -> dict[str, Any]:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    return {
        "command": command,
        "stdout": out,
        "stderr": err,
        "exit_code": exit_code,
    }


def _read_channel_until_idle(channel: paramiko.Channel, idle_seconds: float, hard_timeout: int) -> str:
    chunks: list[str] = []
    start = time.time()
    last_data = time.time()

    while True:
        if channel.recv_ready():
            data = channel.recv(65535).decode("utf-8", errors="replace")
            if data:
                chunks.append(data)
                last_data = time.time()
        else:
            time.sleep(0.1)

        now = time.time()
        if (now - last_data) > idle_seconds and chunks:
            break
        if (now - start) > hard_timeout:
            break

    return "".join(chunks)


def _run_shell_command(client: paramiko.SSHClient, device: Device, command: str, timeout: int) -> dict[str, Any]:
    """Run one or more commands via interactive shell.

    If ``command`` contains newlines, all lines are flushed to the shell in a
    single send so that config-mode sequences (conf t / no ... / end) work
    correctly without losing context between calls.
    """
    channel = client.invoke_shell(width=200, height=1000)
    channel.settimeout(1.0)

    # Drain banner/prompt.
    time.sleep(0.4)
    if channel.recv_ready():
        channel.recv(65535)

    if _is_iosxe(device):
        channel.send("terminal length 0\n")
        _read_channel_until_idle(channel, idle_seconds=0.4, hard_timeout=3)

    # Send all lines at once so multi-line config sequences keep their context.
    payload = command.rstrip("\n") + "\n"
    channel.send(payload)
    # Use a longer idle window for config sequences that spawn process restarts.
    multi_line = "\n" in command.rstrip("\n")
    idle_secs = 3.0 if multi_line else 0.8
    output = _read_channel_until_idle(channel, idle_seconds=idle_secs, hard_timeout=timeout)
    channel.close()

    return {
        "command": command,
        "stdout": output,
        "stderr": "",
        "exit_code": 0,
    }


def _run_commands(
    device: Device,
    commands: list[str],
    timeout: int,
    inventory: dict[str, Device] | None = None,
) -> list[dict[str, Any]]:
    """Run each command as a separate shell invocation on the same SSH transport."""
    results: list[dict[str, Any]] = []
    client = _connect(device, timeout, inventory)
    try:
        for command in commands:
            if _is_iosxe(device):
                results.append(_run_shell_command(client, device, command, timeout))
            else:
                results.append(_run_exec_command(client, command, timeout))
    finally:
        _close_client(client)
    return results


def _find_hf(devices: dict[str, Device]) -> Device:
    for dev in devices.values():
        if dev.role in {"hf", "splunk_hf", "telegraf_hf"}:
            return dev
        if "splunk" in dev.tags or "telegraf" in dev.tags:
            return dev
    raise ValueError("No HF device found. Set role=hf or tag device with splunk/telegraf")


@mcp.tool()
def list_inventory(role: str | None = None, tag: str | None = None) -> list[dict[str, Any]]:
    """List inventory devices, optionally filtered by role or tag."""
    devices = _load_inventory()
    role_filter = role.strip().lower() if role else None
    tag_filter = tag.strip().lower() if tag else None

    out: list[dict[str, Any]] = []
    for dev in devices.values():
        if role_filter and dev.role != role_filter:
            continue
        if tag_filter and tag_filter not in dev.tags:
            continue
        out.append(
            {
                "name": dev.name,
                "host": dev.host,
                "port": dev.port,
                "platform": dev.platform,
                "role": dev.role,
                "tags": dev.tags,
            }
        )
    return sorted(out, key=lambda x: x["name"].lower())


@mcp.tool()
def run_command(device: str, command: str, timeout: int | None = None) -> dict[str, Any]:
    """Run one command on one device from inventory."""
    devices = _load_inventory()
    key = device.strip().lower()
    if key not in devices:
        return {"error": f"Unknown device '{device}'", "available": sorted(devices.keys())}

    timeout_value = timeout or int(os.getenv("MCP_SSH_DEFAULT_TIMEOUT", "30"))
    target = devices[key]

    try:
        results = _run_commands(target, [command], timeout_value, devices)
        return {
            "device": target.name,
            "host": target.host,
            "platform": target.platform,
            "result": results[0],
        }
    except (paramiko.SSHException, socket.error, TimeoutError, ValueError) as exc:
        return {
            "device": target.name,
            "host": target.host,
            "error": str(exc),
            "command": command,
        }


@mcp.tool()
def run_commands(device: str, commands: list[str], timeout: int | None = None) -> dict[str, Any]:
    """Run multiple commands on one device from inventory."""
    devices = _load_inventory()
    key = device.strip().lower()
    if key not in devices:
        return {"error": f"Unknown device '{device}'", "available": sorted(devices.keys())}

    timeout_value = timeout or int(os.getenv("MCP_SSH_DEFAULT_TIMEOUT", "30"))
    target = devices[key]

    try:
        return {
            "device": target.name,
            "host": target.host,
            "platform": target.platform,
            "results": _run_commands(target, commands, timeout_value, devices),
        }
    except (paramiko.SSHException, socket.error, TimeoutError, ValueError) as exc:
        return {
            "device": target.name,
            "host": target.host,
            "error": str(exc),
            "commands": commands,
        }


@mcp.tool()
def run_command_by_role(role: str, command: str, timeout: int | None = None) -> list[dict[str, Any]]:
    """Run one command on all devices matching a role."""
    devices = _load_inventory()
    target_role = role.strip().lower()
    timeout_value = timeout or int(os.getenv("MCP_SSH_DEFAULT_TIMEOUT", "30"))

    selected = [dev for dev in devices.values() if dev.role == target_role]
    if not selected:
        return [{"error": f"No devices found with role '{role}'"}]

    responses: list[dict[str, Any]] = []
    for dev in selected:
        try:
            result = _run_commands(dev, [command], timeout_value, devices)[0]
            responses.append({"device": dev.name, "host": dev.host, "result": result})
        except (paramiko.SSHException, socket.error, TimeoutError, ValueError) as exc:
            responses.append({"device": dev.name, "host": dev.host, "error": str(exc)})

    return responses


@mcp.tool()
def run_hf_command(command: str, timeout: int | None = None) -> dict[str, Any]:
    """Run one troubleshooting command on the Splunk/Telegraf HF device."""
    devices = _load_inventory()
    timeout_value = timeout or int(os.getenv("MCP_SSH_DEFAULT_TIMEOUT", "30"))

    try:
        hf = _find_hf(devices)
    except ValueError as exc:
        return {"error": str(exc)}

    try:
        result = _run_commands(hf, [command], timeout_value, devices)[0]
        return {"device": hf.name, "host": hf.host, "result": result}
    except (paramiko.SSHException, socket.error, TimeoutError, ValueError) as exc:
        return {"device": hf.name, "host": hf.host, "error": str(exc), "command": command}


if __name__ == "__main__":
    mcp.run()
