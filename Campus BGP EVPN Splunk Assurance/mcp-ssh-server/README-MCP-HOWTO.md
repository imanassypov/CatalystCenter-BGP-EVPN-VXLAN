# EVPN SSH MCP Server — How-To

## Overview

This MCP server lets GitHub Copilot (or any MCP-compatible client) run SSH commands directly against the EVPN fabric routers and the Splunk Heavy Forwarder without leaving the editor.

The server is implemented as a Python stdio MCP process. VS Code launches it automatically when the workspace is loaded. The device inventory is a plain CSV file — add or remove devices there without touching code.

---

## Directory Structure

```
mcp-ssh-server/
├── server.py              # MCP stdio server
├── devices.csv            # Active inventory (edit this)
├── devices.example.csv    # Annotated template
├── requirements.txt       # Python dependencies
└── README-MCP-HOWTO.md    # This file

.vscode/
└── mcp.json               # VS Code MCP server registration
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python (pyenv) | 3.10.4 |
| `mcp` package | ≥ 1.10.0 |
| `paramiko` package | ≥ 3.4.0 |

---

## Initial Setup

### 1. Install Python dependencies

```bash
/path/to/python -m pip install -r \
  "/path/to/Campus BGP EVPN Splunk Assurance/mcp-ssh-server/requirements.txt"
```

### 2. Review credentials in `.vscode/mcp.json`

```json
{
  "servers": {
    "evpn-ssh": {
      "type": "stdio",
      "command": "/path/to/python",
      "args": [
        "/path/to/Campus BGP EVPN Splunk Assurance/mcp-ssh-server/server.py"
      ],
      "env": {
        "MCP_SSH_INVENTORY": "/path/to/Campus BGP EVPN Splunk Assurance/mcp-ssh-server/devices.csv",
        "IOSXE_PASS": "<iosxe-password>",
        "HF_PASS": "<hf-password>"
      }
    }
  }
}
```

`IOSXE_PASS` — password for all IOS-XE routers (`net-admin` user).  
`HF_PASS` — password for the Splunk Heavy Forwarder (`cisco` user).

### 3. Reload VS Code window

`Cmd+Shift+P` → `Developer: Reload Window`

The `evpn-ssh` server starts automatically. No manual process management required.

---

## Device Inventory (`devices.csv`)

| Column | Required | Description |
|---|---|---|
| `name` | Yes | Unique device name used in MCP tool calls |
| `host` | Yes | IP address |
| `port` | No | SSH port (default: 22) |
| `username` | Yes | SSH username |
| `password` | No | Plain password or `env:VAR_NAME` to resolve from environment |
| `key_path` | No | Path to SSH private key or `env:VAR_NAME` |
| `platform` | No | `iosxe` for Cisco routers, `linux` for the Splunk/OTel host |
| `role` | No | `router`, `splunk` — used by `run_command_by_role` and `run_hf_command` |
| `tags` | No | Pipe-delimited tags for filtering (e.g. `evpn\|spine`) |

### Current Inventory

| Name | Host | Username | Platform | Role | Tags |
|---|---|---|---|---|---|
| spine01 | 198.18.128.101 | net-admin | iosxe | router | evpn, spine |
| spine02 | 198.18.128.102 | net-admin | iosxe | router | evpn, spine |
| leaf1 | 198.18.128.103 | net-admin | iosxe | router | evpn, leaf |
| leaf2 | 198.18.128.104 | net-admin | iosxe | router | evpn, leaf |
| border1 | 198.18.128.105 | net-admin | iosxe | router | evpn, border |
| border2 | 198.18.128.106 | net-admin | iosxe | router | evpn, border |
| dmz1 | 198.18.128.107 | net-admin | iosxe | router | evpn, dmz |
| core1 | 198.18.128.108 | net-admin | iosxe | router | evpn, core |
| core2 | 198.18.128.109 | net-admin | iosxe | router | evpn, core |
| dhcp-server | 198.18.128.110 | net-admin | iosxe | router | infra, dhcp |
| fw-shared-services | 198.18.134.200 | net-admin | iosxe | router | infra, firewall |
| splunk | 18.224.25.161 | cisco | linux | splunk | splunk, sh, hf, otel |

### Add a Device

Append a row to `devices.csv` and reload the window. No code changes needed.

```csv
new-switch,10.0.1.120,22,net-admin,env:IOSXE_PASS,iosxe,router,evpn|leaf
```

---

## MCP Tools Reference

### `list_inventory`

List all devices. Optionally filter by role or tag.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `role` | string | No | Filter by role (e.g. `router`, `hf`) |
| `tag` | string | No | Filter by tag (e.g. `spine`, `otel`) |

**Examples:**
```
list_inventory
list_inventory role=router
list_inventory tag=spine
list_inventory tag=otel
```

---

### `run_command`

Run one command on one device.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `device` | string | Yes | Device name from inventory |
| `command` | string | Yes | Command to run |
| `timeout` | int | No | Per-command timeout in seconds (default: 30) |

**Examples:**
```
run_command device=spine01 command="show telemetry connection all"
run_command device=spine02 command="show telemetry ietf subscription all"
run_command device=spine01 command="show nve peers"
run_command device=spine01 command="show bgp l2vpn evpn summary"
run_command device=splunk command="sudo ss -ltnp | grep 57444"
```

---

### `run_commands`

Run multiple commands on one device in sequence.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `device` | string | Yes | Device name from inventory |
| `commands` | list | Yes | List of commands to run |
| `timeout` | int | No | Per-command timeout in seconds (default: 30) |

**Examples:**
```
run_commands device=spine01 commands=["show telemetry connection all", "show telemetry ietf subscription all", "show nve peers"]
run_commands device=splunk commands=["sudo systemctl status splunk-otel-collector --no-pager", "sudo ss -ltnp | grep 57444"]
```

---

### `run_command_by_role`

Run one command on **all devices** matching a role simultaneously.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `role` | string | Yes | Role name (e.g. `router`) |
| `command` | string | Yes | Command to run on all matching devices |
| `timeout` | int | No | Per-device timeout in seconds (default: 30) |

**Examples:**
```
run_command_by_role role=router command="show telemetry ietf subscription all"
run_command_by_role role=router command="show nve peers"
run_command_by_role role=router command="show bgp l2vpn evpn summary"
run_command_by_role role=router command="show ip interface brief"
```

---

### `run_hf_command`

Run a command on the Splunk / OTel collector host (role=`splunk`, tagged `splunk`).

| Parameter | Type | Required | Description |
|---|---|---|---|
| `command` | string | Yes | Shell command to run on the Splunk/OTel host |
| `timeout` | int | No | Timeout in seconds (default: 30) |

**Examples:**
```
run_hf_command command="sudo systemctl status splunk-otel-collector --no-pager"
run_hf_command command="sudo journalctl -u splunk-otel-collector -n 100 --no-pager"
run_hf_command command="sudo ss -ltnp | grep 57444"
run_hf_command command="sudo tcpdump -ni any host 198.18.128.102 and tcp port 57444 -c 30"
run_hf_command command="ps aux | grep otelcol | grep -v grep"
run_hf_command command="sudo systemctl restart splunk-otel-collector"
```

---

## Troubleshooting Workflows

### Check telemetry session state across all routers
```
run_command_by_role role=router command="show telemetry connection all"
```

### Check a specific subscription on one device
```
run_commands device=spine01 commands=["show telemetry ietf subscription 40107 detail", "show telemetry ietf subscription 40107 receiver"]
```

### Force reconnect a subscription
```
run_commands device=spine02 commands=[
  "conf t",
  "telemetry ietf subscription 40107",
  "no receiver ip address 18.224.25.161 57444 protocol grpc-tcp",
  "receiver ip address 18.224.25.161 57444 protocol grpc-tcp",
  "end",
  "show telemetry connection all"
]
```

### Check OTel collector MDT listener and logs
```
run_commands device=splunk commands=[
  "sudo ss -ltnp | grep 57444",
  "sudo journalctl -u splunk-otel-collector -n 100 --no-pager"
]
```

### Check NETCONF status on all routers
```
run_command_by_role role=router command="show netconf-yang status"
```

### Verify NVE peers across fabric
```
run_command_by_role role=router command="show nve peers"
```

### Verify EVPN subscription states across fabric
```
run_command_by_role role=router command="show telemetry ietf subscription all"
```

---

## Platform Behavior Notes

### IOS-XE devices (`platform=iosxe`)
- The server opens an interactive shell and sends `terminal length 0` before each command to suppress `--More--` pagination.
- Output includes the shell prompt lines; strip or grep as needed.

### Linux/HF devices (`platform=linux`)
- The server uses SSH exec mode (non-interactive).
- `sudo` commands that require a password will fail unless NOPASSWD sudoers is configured on the HF.
- If `sudo` prompts for password, add the HF user to sudoers:
  ```bash
  echo "cisco ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/cisco
  ```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MCP_SSH_INVENTORY` | `./devices.csv` | Absolute or relative path to CSV inventory |
| `MCP_SSH_DEFAULT_TIMEOUT` | `30` | Per-command SSH timeout in seconds |
| `IOSXE_PASS` | — | Password resolved by `env:IOSXE_PASS` in CSV |
| `HF_PASS` | — | Password resolved by `env:HF_PASS` in CSV |

---

## Known Issues

| Symptom | Cause | Resolution |
|---|---|---|
| `sudo` commands hang or fail on HF | Interactive sudo password prompt | Add NOPASSWD sudoers entry for `cisco` user |
| IOS-XE output includes prompt/echo lines | Interactive shell mode | Filter output with `grep` in your query |
| `Unknown device 'X'` error | Device name not in CSV or casing mismatch | Names are lowercased — check `list_inventory` |
| Server not starting after reload | Missing Python dependency | Re-run `pip install -r requirements.txt` |
| `HF_PASS` or `IOSXE_PASS` not resolved | Env var not set in `mcp.json` | Verify `.vscode/mcp.json` env block |
