#!/usr/bin/env python3
"""Deploy campus_evpn_assurance .spl to Splunk via jump-host SSH (paramiko)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import paramiko
except ImportError as exc:
    print(
        "ERROR: paramiko is required. Install with:\n"
        '  pip install -r "CICD Pipeline/utils/mcp-ssh-server/requirements.txt"',
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[assignment,misc]

# Jump host and Splunk EC2 — mirrors devices.csv (splunk → script-server)
JUMP_HOST = "198.18.134.28"
JUMP_PORT = 22
JUMP_USER = "root"

SPLUNK_HOST = "18.224.25.161"
SPLUNK_PORT = 22
SPLUNK_USER = "ec2-user"

SPLUNK_BIN = "/opt/splunk/bin/splunk"
APP_CONF_REMOTE = "/opt/splunk/etc/apps/campus_evpn_assurance/default/app.conf"
RESTART_POLL_SECONDS = 90
RESTART_POLL_INTERVAL = 5

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_ENV_FILE = _REPO_ROOT / "CICD Pipeline" / "utils" / "mcp-ssh-server" / ".env"


def _load_env(env_file: Path | None) -> None:
    if env_file and env_file.is_file():
        if load_dotenv is not None:
            load_dotenv(env_file, override=False)
        else:
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERROR: {name} is not set (check .env)", file=sys.stderr)
        raise SystemExit(1)
    return value


def _resolve_key_path(env_file: Path | None) -> Path:
    raw = os.environ.get("SPLUNK_SSH_KEY_PATH", "splunk-creds/ec2user-splunk.pem")
    key = Path(raw).expanduser()
    if not key.is_absolute() and env_file:
        key = (env_file.parent / key).resolve()
    if not key.is_file():
        print(f"ERROR: SSH key not found: {key}", file=sys.stderr)
        raise SystemExit(1)
    return key


def _load_private_key(key_path: Path) -> paramiko.PKey:
    last_exc: Exception | None = None
    for key_cls in (
        paramiko.Ed25519Key,
        paramiko.RSAKey,
        paramiko.ECDSAKey,
        paramiko.DSSKey,
    ):
        try:
            return key_cls.from_private_key_file(str(key_path))
        except paramiko.SSHException as exc:
            last_exc = exc
    raise paramiko.SSHException(f"Unable to load private key '{key_path}': {last_exc}")


def _connect_via_jump(
    jump_password: str,
    pkey: paramiko.PKey,
    timeout: int = 60,
) -> paramiko.SSHClient:
    jump_client = paramiko.SSHClient()
    jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    jump_client.connect(
        hostname=JUMP_HOST,
        port=JUMP_PORT,
        username=JUMP_USER,
        password=jump_password,
        timeout=timeout,
        look_for_keys=False,
        allow_agent=False,
    )

    transport = jump_client.get_transport()
    if transport is None:
        jump_client.close()
        raise RuntimeError("Jump host transport unavailable")

    channel = transport.open_channel(
        "direct-tcpip",
        (SPLUNK_HOST, SPLUNK_PORT),
        ("127.0.0.1", 0),
        timeout=timeout,
    )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=SPLUNK_HOST,
            port=SPLUNK_PORT,
            username=SPLUNK_USER,
            pkey=pkey,
            sock=channel,
            timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )
    except Exception:
        jump_client.close()
        raise

    client._jump_client = jump_client  # type: ignore[attr-defined]
    return client


def _close_client(client: paramiko.SSHClient) -> None:
    jump = getattr(client, "_jump_client", None)
    try:
        client.close()
    finally:
        if jump is not None:
            jump.close()


def _run(client: paramiko.SSHClient, command: str, timeout: int = 120) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def _parse_build(app_conf_text: str) -> str | None:
    for line in app_conf_text.splitlines():
        if line.strip().startswith("build"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                return parts[1].strip()
    return None


def _read_local_build(app_conf: Path) -> str | None:
    if not app_conf.is_file():
        return None
    return _parse_build(app_conf.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy campus_evpn_assurance .spl to Splunk")
    parser.add_argument("--spl", required=True, type=Path, help="Path to .spl package")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=_DEFAULT_ENV_FILE if _DEFAULT_ENV_FILE.is_file() else None,
        help="Path to mcp-ssh-server .env (loads SPLUNK_* and SCRIPT_SERVER_SSH_PASS)",
    )
    parser.add_argument(
        "--local-app-conf",
        type=Path,
        default=None,
        help="Local app.conf for expected build comparison",
    )
    parser.add_argument(
        "--verify-marker",
        default="",
        help="Optional substring to verify in executive_overview REST view",
    )
    args = parser.parse_args()

    spl_path = args.spl.resolve()
    if not spl_path.is_file():
        print(f"ERROR: .spl not found: {spl_path}", file=sys.stderr)
        return 1

    _load_env(args.env_file)

    jump_pass = _require_env("SCRIPT_SERVER_SSH_PASS")
    admin_user = _require_env("SPLUNK_ADMIN_USER")
    admin_pass = _require_env("SPLUNK_ADMIN_PASS")
    auth = f"{admin_user}:{admin_pass}"

    key_path = _resolve_key_path(args.env_file)
    pkey = _load_private_key(key_path)

    remote_name = spl_path.name
    remote_tmp = f"/tmp/{remote_name}"
    expected_build = _read_local_build(args.local_app_conf) if args.local_app_conf else None

    print(f"Connecting: {JUMP_USER}@{JUMP_HOST} → {SPLUNK_USER}@{SPLUNK_HOST}")
    client = _connect_via_jump(jump_pass, pkey)

    try:
        # Upload
        print(f"Uploading {spl_path.name} ({spl_path.stat().st_size} bytes) → {remote_tmp}")
        sftp = client.open_sftp()
        try:
            sftp.put(str(spl_path), remote_tmp)
        finally:
            sftp.close()

        # Install
        install_cmd = (
            f"sudo {SPLUNK_BIN} install app {remote_tmp} -update 1 -auth {auth!r}"
        )
        print("Installing app (-update 1)…")
        code, out, err = _run(client, install_cmd, timeout=300)
        combined = (out + err).strip()
        if combined:
            print(combined)
        if code != 0:
            print(f"ERROR: splunk install app failed (exit {code})", file=sys.stderr)
            return 1

        # Remove temp package
        _run(client, f"rm -f {remote_tmp!r}")

        # Restart and wait
        print("Restarting splunkd…")
        code, out, err = _run(
            client,
            f"sudo {SPLUNK_BIN} restart -auth {auth!r} 2>&1",
            timeout=300,
        )
        restart_out = (out + err).strip()
        if restart_out:
            print(restart_out[-2000:])

        deadline = time.monotonic() + RESTART_POLL_SECONDS
        running = False
        while time.monotonic() < deadline:
            code, out, err = _run(client, f"sudo {SPLUNK_BIN} status splunkd 2>&1", timeout=60)
            status = (out + err).lower()
            if "splunkd is running" in status:
                running = True
                break
            time.sleep(RESTART_POLL_INTERVAL)

        if not running:
            print(
                f"ERROR: splunkd did not report running within {RESTART_POLL_SECONDS}s",
                file=sys.stderr,
            )
            return 1
        print("splunkd is running")

        # Verify remote build
        code, out, err = _run(client, f"sudo cat {APP_CONF_REMOTE!r}", timeout=60)
        if code != 0:
            print(f"ERROR: could not read remote app.conf (exit {code})", file=sys.stderr)
            return 1

        remote_build = _parse_build(out)
        print(f"Remote build: {remote_build}")
        if expected_build:
            print(f"Expected build: {expected_build}")
            if remote_build != expected_build:
                print(
                    f"ERROR: build mismatch (remote={remote_build}, expected={expected_build})",
                    file=sys.stderr,
                )
                return 1
            print("Build number verified")

        # Optional REST marker check
        if args.verify_marker:
            marker = args.verify_marker
            py_check = (
                "import sys,json,urllib.request;"
                f"u='https://localhost:8089/servicesNS/nobody/campus_evpn_assurance/"
                "data/ui/views/executive_overview?output_mode=json';"
                f"req=urllib.request.Request(u);"
                f"import base64; b=base64.b64encode({auth!r}.encode()).decode();"
                "req.add_header('Authorization','Basic '+b);"
                "ctx=__import__('ssl').create_default_context();"
                "ctx.check_hostname=False; ctx.verify_mode=__import__('ssl').CERT_NONE;"
                "data=json.load(urllib.request.urlopen(req,context=ctx));"
                "body=data['entry'][0]['content']['eai:data'];"
                f"m={marker!r};"
                "print('OK' if m in body else 'STALE');"
                "sys.exit(0 if m in body else 2)"
            )
            code, out, err = _run(client, f"python3 -c {py_check!r}", timeout=60)
            result = out.strip() or err.strip()
            print(f"REST verify ({marker!r}): {result}")
            if code != 0:
                print("ERROR: REST marker not found in executive_overview", file=sys.stderr)
                return 1

    finally:
        _close_client(client)

    print()
    print("=" * 60)
    print("SUCCESS: campus_evpn_assurance deployed and splunkd restarted")
    print(f"  Package: {spl_path.name}")
    if remote_build:
        print(f"  Build:   {remote_build}")
    print("  Operator: hard-refresh Splunk Web (Cmd+Shift+R / Ctrl+Shift+R)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
