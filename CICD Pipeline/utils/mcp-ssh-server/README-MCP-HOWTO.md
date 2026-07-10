# EVPN SSH MCP Server — How-To

## Overview

This MCP server lets GitHub Copilot (or any MCP-compatible client) run SSH commands directly against the EVPN fabric routers and the Splunk Heavy Forwarder without leaving the editor.

The server is implemented as a Python stdio MCP process. VS Code launches it automatically when the workspace is loaded. Device inventory is loaded from **CML** (`inventory/cml.yml` via `virl2_client`) plus **static hosts** (`inventory/static_hosts.yml`), or from a plain **CSV** fallback (`devices.csv`).

**MCP inventory is independent of Ansible.** Playbooks use `CICD Pipeline/ansible/inventory/`; the MCP server uses only `mcp-ssh-server/inventory/`. Keep `group_tags` in sync manually when you add CML tags.

---

## Directory Structure

```
mcp-ssh-server/
├── server.py              # MCP stdio server
├── inventory_loader.py    # CML (virl2_client) + static hosts → Device
├── inventory/
│   ├── cml.yml            # MCP CML config (group_tags, ssh node types)
│   └── static_hosts.yml   # bastion, Splunk EC2
├── devices.csv            # CSV fallback inventory (offline / no CML)
├── devices.example.csv    # Annotated template
├── requirements.txt       # Python dependencies
└── README-MCP-HOWTO.md    # This file

CICD Pipeline/ansible/inventory/   # Ansible only (playbooks)
├── cml.yml                # cisco.cml.cml_inventory
├── static_inventory.yml   # Catalyst Center, image/YANG servers
└── platform_groups.yml    # iosxe/nxos parent groups

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
| `virl2_client` | ≥ 2.0.0, &lt; 2.10.0 (CML inventory mode) |
| CML lab running | Fabric nodes need mgmt IPs from CML API |

---

## Initial Setup

### 1. Install Python dependencies

```bash
/path/to/python -m pip install -r \
  "/path/to/CICD Pipeline/utils/mcp-ssh-server/requirements.txt"
```

`virl2_client` is required for CML inventory mode. No Ansible install is needed for the MCP server.

### 2. Configure credentials (`CICD Pipeline/.env`)

```bash
cd "CICD Pipeline"
cp .env.example .env    # fill in secrets
direnv allow            # one-time — auto-loads .env on every cd
```

Paths in `.env` are relative to **`CICD Pipeline/`** (not `mcp-ssh-server/`).

### 3. Review `.cursor/mcp.json`

Use `envFile` pointing at `utils/mcp-ssh-server/.env` — inventory paths live in `.env`, not in `mcp.json`:

```json
{
  "mcpServers": {
    "evpn-ssh": {
      "command": "/path/to/python",
      "args": ["${workspaceFolder}/CICD Pipeline/utils/mcp-ssh-server/server.py"],
      "env": {
        "MCP_SSH_DEFAULT_TIMEOUT": "60"
      },
      "envFile": "${workspaceFolder}/CICD Pipeline/.env"
    }
  }
}
```

`IOSXE_PASS` — password for fabric devices (`net-admin`).  
`SCRIPT_SERVER_SSH_PASS` — dCloud jump host (`script-server`).  
`SPLUNK_SSH_KEY_PATH` — PEM for cloud Splunk EC2 (`splunk`, via jump host).

For offline use without CML, set `MCP_SSH_INVENTORY` to `devices.csv` instead.

### 4. Reload VS Code window

`Cmd+Shift+P` → `Developer: Reload Window`

The `evpn-ssh` server starts automatically. No manual process management required.

---

## CML Dynamic Inventory (`inventory/cml.yml`)

Fabric devices are discovered from the live CML lab via **`virl2_client`** (no Ansible subprocess). CML **tag assignments** on each node become MCP tags when listed in `group_tags`.

| Item | Location |
|---|---|
| MCP CML config | `mcp-ssh-server/inventory/cml.yml` |
| Tag allowlist | `group_tags` — edit when you add a new CML tag to target |
| Bastion / Splunk | `mcp-ssh-server/inventory/static_hosts.yml` |
| Ansible (separate) | `ansible/inventory/cml.yml` — for playbooks only |

**Verify Ansible CML inventory** (playbooks — not used by MCP):

From **`CICD Pipeline/`**:

```bash
bash verify-cml-inventory.sh
```

CML hostnames (e.g. `spine1`) are used as inventory names — they may differ from legacy CSV names (`spine01`).

---

## Device Inventory (`devices.csv` — fallback)

| Column | Required | Description |
|---|---|---|
| `name` | Yes | Unique device name used in MCP tool calls |
| `host` | Yes | IP address |
| `port` | No | SSH port (default: 22) |
| `username` | Yes | SSH username |
| `password` | No | Plain password or `env:VAR_NAME` to resolve from environment |
| `key_path` | No | Path to SSH private key or `env:VAR_NAME` |
| `platform` | No | `iosxe` for Catalyst IOS-XE routers, `nxos` for Nexus (NX-OS) cores, `linux` for the Splunk/OTel host |
| `role` | No | `router`, `core`, `splunk` — used by `run_command_by_role` and `run_hf_command` |
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
| core1 | 198.18.128.108 | net-admin | nxos | core | core |
| core2 | 198.18.128.109 | net-admin | nxos | core | core |
| dhcp-server | 198.18.128.110 | net-admin | iosxe | router | infra, dhcp |
| fw-shared-services | 198.18.134.200 | net-admin | iosxe | router | infra, firewall |
| splunk | 18.224.25.161 | ec2-user | linux | splunk | splunk, sh, hf, otel |

> **Splunk SSH path:** `splunk` reaches the EC2 host through the `script-server`
> jump host (password). EC2 auth is PEM-only — see `.env.example` and
> `splunk-creds/ec2user-splunk.pem`.

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

### `run_command_by_tag`

Run one command on **all devices** that have a CML inventory tag (from tag assignments in CML).

| Parameter | Type | Required | Description |
|---|---|---|---|
| `tag` | string | Yes | CML tag name (e.g. `spine`, `leaf`, `ip core`) |
| `command` | string | Yes | Command to run on all matching devices |
| `timeout` | int | No | Per-device timeout in seconds (default: 30) |

**Examples:**
```
run_command_by_tag tag=spine command="show ip interface brief"
run_command_by_tag tag=leaf command="show nve peers"
run_command_by_tag tag=border command="show bgp l2vpn evpn summary"
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

## Splunk App Update (`campus_evpn_assurance`)

> **Automated deploy:** Cursor skill `.cursor/skills/splunk-app-deploy/SKILL.md` and
> `Campus BGP EVPN Splunk Assurance/packaging/deploy-splunk-app.sh` (`--skip-build`,
> `--verify-marker`). Credentials: `CICD Pipeline/utils/mcp-ssh-server/.env`.

Use this workflow whenever dashboard views, lookups, or macros in the Splunk app
are changed in git and need to go live on the EC2 Splunk host (`device=splunk`).

### Why copying XML is not enough

Dashboard Studio stores view definitions as Splunk **knowledge objects**. Writing
files under `/opt/splunk/etc/apps/campus_evpn_assurance/default/data/ui/views/`
updates disk only — Splunk may keep serving the **cached** definition until the
app package is installed with `-update` and `splunkd` is restarted. Symptom: the
repo and on-disk XML look correct, but the browser still shows the old dashboard
(same tile count / layout).

### Prerequisites

Automated deploy: `./Campus BGP EVPN Splunk Assurance/packaging/deploy-splunk-app.sh` (see `.cursor/skills/splunk-app-deploy/SKILL.md`).

| Item | Location / value |
|---|---|
| App source | `Campus BGP EVPN Splunk Assurance/campus_evpn_assurance/` |
| Build script | `Campus BGP EVPN Splunk Assurance/packaging/build-app.sh` |
| Output package | `packaging/dist/campus_evpn_assurance-<version>.spl` |
| Installed path | `/opt/splunk/etc/apps/campus_evpn_assurance/` |
| Splunk CLI auth | `SPLUNK_ADMIN_USER` / `SPLUNK_ADMIN_PASS` in `.env` (format: `user:pass` for `-auth`) |

### Step 1 — Build the `.spl` package (local workstation)

```bash
cd "Campus BGP EVPN Splunk Assurance/packaging"
./build-app.sh
# -> packaging/dist/campus_evpn_assurance-1.5.0.spl
```

### Step 2 — Copy the package to the Splunk host

Upload via MCP (base64 over SSH is reliable through the jump host):

```
run_command device=splunk command="ls -la /tmp/campus_evpn_assurance*.spl 2>/dev/null || echo 'not yet uploaded'"
```

From the agent/workstation, base64-encode the `.spl` and write it on the host, e.g.:

```bash
# On the workstation — produce a one-liner the MCP run_command can execute:
base64 -i "packaging/dist/campus_evpn_assurance-1.5.0.spl" | \
  ssh … 'base64 -d > /tmp/campus_evpn_assurance-1.5.0.spl'
```

Or ask the MCP agent to push the file the same way it deploys config (base64 pipe
to `tee /tmp/campus_evpn_assurance-<version>.spl`).

### Step 3 — Install with `-update 1` (MCP)

Replace `<version>` and credentials from `.env`:

```
run_commands device=splunk commands=[
  "sudo /opt/splunk/bin/splunk install app /tmp/campus_evpn_assurance-1.5.0.spl -update 1 -auth $SPLUNK_ADMIN_USER:$SPLUNK_ADMIN_PASS",
  "rm -f /tmp/campus_evpn_assurance-1.5.0.spl"
]
```

> **Always use `-update 1`** for in-place upgrades. A plain `install app` without
> `-update` on an existing app name may fail or leave stale knowledge objects.

### Step 4 — Restart Splunk

Install prints *"You need to restart the Splunk Server (splunkd) for your changes
to take effect."* — do this every time after an app update:

```
run_command device=splunk command="sudo /opt/splunk/bin/splunk restart -auth $SPLUNK_ADMIN_USER:$SPLUNK_ADMIN_PASS 2>&1 | tail -5"
```

Allow ~30–60 s for `splunkd` to come back before verifying.

### Step 5 — Verify the new definition is live (MCP)

Check that Splunk REST serves the updated view (not just the file on disk):

```
run_command device=splunk command="curl -sk -u '$SPLUNK_ADMIN_USER:$SPLUNK_ADMIN_PASS' 'https://localhost:8089/servicesNS/nobody/campus_evpn_assurance/data/ui/views/executive_overview?output_mode=json' | python3 -c \"import sys,json; d=json.load(sys.stdin)['entry'][0]['content']['eai:data']; print('OK' if '<your-new-panel-id-or-title>' in d else 'STALE')\""
```

Replace the marker string with something unique to your change (e.g.
`viz_executive_overview_18` or a new panel title).

Optional — run the full Dashboard Studio validator on the host:

```bash
python3 Campus\ BGP\ EVPN\ Splunk\ Assurance/tools/validate_studio.py \
  "$SPLUNK_ADMIN_USER" "$SPLUNK_ADMIN_PASS"
```

### Step 6 — Browser refresh (tell the operator)

Dashboard Studio caches on the client. After a successful server-side verify:

1. Hard-refresh the dashboard: **Cmd+Shift+R** (Mac) or **Ctrl+Shift+R** (Windows).
2. If still stale: log out of Splunk Web and back in, or open the view in a
   private/incognito window.

### Quick reference — full MCP sequence

```
# 1. Build locally: ./packaging/build-app.sh
# 2. Upload .spl to /tmp/ on splunk host
# 3. Install + remove temp file
run_commands device=splunk commands=[
  "sudo /opt/splunk/bin/splunk install app /tmp/campus_evpn_assurance-1.5.0.spl -update 1 -auth ${SPLUNK_ADMIN_USER}:${SPLUNK_ADMIN_PASS}",
  "rm -f /tmp/campus_evpn_assurance-1.5.0.spl"
]
# 4. Restart
run_command device=splunk command="sudo /opt/splunk/bin/splunk restart -auth ${SPLUNK_ADMIN_USER}:${SPLUNK_ADMIN_PASS} 2>&1 | tail -3"
# 5. REST verify (see Step 5)
# 6. Operator hard-refreshes browser
```

### Splunk app update — common failures

| Symptom | Cause | Fix |
|---|---|---|
| Browser unchanged after file copy | Knowledge-object cache; REST still stale | `install app … -update 1` + restart |
| `install app` 409 / object exists | Normal for updates | Use `-update 1`, not a fresh install name |
| REST POST to view returns 409 | POST creates; cannot overwrite in place | Use `install app -update` or DELETE+POST |
| `reload app` CLI error | Not a valid `splunk reload` target | Use `install app -update` instead |
| MCP `sudo` hangs on Splunk host | sudo password prompt | Ensure `ec2-user` has NOPASSWD for splunk commands |

---

## Platform Behavior Notes

### IOS-XE devices (`platform=iosxe`)
- The server opens an interactive shell and sends `terminal length 0` before each command to suppress `--More--` pagination.
- Output includes the shell prompt lines; strip or grep as needed.

### NX-OS devices (`platform=nxos`)
- Handled through the same interactive-shell path as IOS-XE: the server sends `terminal length 0` to disable paging and shares the `configure terminal` / `end` config grammar, so multi-line config sequences work the same way.
- Recognized platform aliases: `nxos`, `nx-os`, `nx_os`, `cisco_nxos`, `nexus`, `n9kv`, `n9k`.
- Save running config with `copy running-config startup-config` (NX-OS has no `write memory` alias by default).
- The Nexus 9000v cores use `role=core`; target them together with `run_command_by_role role=core ...`.

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
| `MCP_SSH_INVENTORY` | `inventory/cml.yml` | MCP CML config YAML or `devices.csv` (fallback) |
| `MCP_SSH_STATIC_HOSTS` | `inventory/static_hosts.yml` | Bastion/Splunk hosts merged with CML inventory |
| `MCP_SSH_OVERLAY` | — | Deprecated alias for `MCP_SSH_STATIC_HOSTS` |
| `MCP_SSH_DEFAULT_TIMEOUT` | `30` | Per-command SSH timeout in seconds |
| `CML_HOST` | — | CML controller (required for `cml.yml`) |
| `CML_USERNAME` | — | CML API user |
| `CML_PASSWORD` | — | CML API password |
| `CML_LAB` | `BGP EVPN Campus` | Lab title in CML |
| `IOSXE_PASS` | — | Fabric device password (`net-admin`) |
| `SCRIPT_SERVER_SSH_PASS` | — | Jump-host password for `script-server` |
| `SPLUNK_SSH_KEY_PATH` | `splunk-creds/ec2user-splunk.pem` | PEM for EC2 Splunk SSH (via jump host) |
| `SPLUNK_ADMIN_USER` | — | Splunk Web / REST / CLI `-auth` username |
| `SPLUNK_ADMIN_PASS` | — | Splunk Web / REST / CLI `-auth` password |

---

## Known Issues

| Symptom | Cause | Resolution |
|---|---|---|
| `sudo` commands hang or fail on HF | Interactive sudo password prompt | Add NOPASSWD sudoers entry for `cisco` user |
| IOS-XE output includes prompt/echo lines | Interactive shell mode | Filter output with `grep` in your query |
| `Unknown device 'X'` error | Device name not in CSV or casing mismatch | Names are lowercased — check `list_inventory` |
| Server not starting after reload | Missing Python dependency | Re-run `pip install -r requirements.txt` |
| `HF_PASS` or `IOSXE_PASS` not resolved | Env var not set in `mcp.json` | Verify `.vscode/mcp.json` env block |
