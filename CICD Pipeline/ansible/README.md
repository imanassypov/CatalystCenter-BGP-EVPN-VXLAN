# Ansible CI/CD Pipeline

Single Ansible project for Catalyst Center provisioning (stages 1–11), SWIM, and config backup. All automation runs from this directory.

## Quick Start

```bash
cd "CICD Pipeline/ansible"

ansible-galaxy collection install -r collections/requirements.yml
pip install 'virl2_client>=2.0.0,<2.10.0'

# CML fabric inventory (lab must be running; CML_* from CICD Pipeline/.env via direnv)
ansible-inventory -i inventory/cml.yml --graph

# Vault password (once): echo 'passphrase' > "../.vault_pass" && chmod 600 "../.vault_pass"

# Catalyst Center API (+ optional git_token for stage 7)
cp inventory/group_vars/catalyst_center/vault.yml.example inventory/group_vars/catalyst_center/vault.yml
ansible-vault encrypt inventory/group_vars/catalyst_center/vault.yml --vault-password-file ../.vault_pass

# Stage 11 device SSH creds come from Settings/settings.json (no separate vault)

# Image server (before SWIM import)
cp inventory/group_vars/image_servers/vars.yml.example inventory/group_vars/image_servers/vars.yml
cp inventory/group_vars/image_servers/vault.yml.example inventory/group_vars/image_servers/vault.yml
ansible-vault encrypt inventory/group_vars/image_servers/vault.yml --vault-password-file ../.vault_pass

# YANG Suite (NETCONF/YANG lab utility)
cp inventory/group_vars/yangsuite_servers/vars.yml.example inventory/group_vars/yangsuite_servers/vars.yml
cp inventory/group_vars/yangsuite_servers/vault.yml.example inventory/group_vars/yangsuite_servers/vault.yml
ansible-vault encrypt inventory/group_vars/yangsuite_servers/vault.yml --vault-password-file ../.vault_pass

ansible-playbook playbooks/01_site_hierarchy.yml
```

## Layout

```
CICD Pipeline/
├── .vault_pass
├── Settings/settings.json       # SSOT for all stages
└── ansible/
    ├── inventory/               # CML dynamic (cml.yml) + static_inventory + group_vars
    ├── playbooks/               # 01–11, site.yml, deploy_* utilities
    ├── roles/                   # site_hierarchy, swim, template_sync, http_image_server, yangsuite_docker, …
    ├── config-backups/          # stage 11 output (gitignored timestamps)
    ├── logs/                    # SWIM evidence JSON (gitignored)
    └── docs/swim/               # SWIM reference diagrams
```

## Pipeline Order

Full orchestrator (stages 1–10, excludes SWIM and backup):

```bash
ansible-playbook playbooks/site.yml
```

| Playbook | Stage | Description |
|----------|-------|-------------|
| `01_site_hierarchy.yml` | 1 | Build site hierarchy |
| `02_network_settings.yml` | 2 | Apply network settings |
| `03_credentials.yml` | 3 | CLI/SNMP/NETCONF credentials |
| `04_device_discovery.yml` | 4 | Device discovery |
| `05_assign_to_site.yml` | 5 | Assign devices to sites |
| `06_swim_*.yml` | 6 | SWIM lifecycle (run in order; see below) |
| `07_template_sync.yml` | 7 | GitHub template sync |
| `08_network_profile.yml` | 8 | Network profiles |
| `09_provision_devices.yml` | 9 | Device provisioning |
| `10_deploy_composite.yml` | 10 | Composite template deploy |
| `11_backup_lab_configs.yml` | 11 | IOS-XE/NX-OS config backup |
| `deploy_http_image_server.yml` | 6 prep | HTTP image server |
| `deploy_yangsuite.yml` | util | Cisco YANG Suite (Docker) |

### SWIM (stage 6)

```bash
ansible-playbook playbooks/deploy_http_image_server.yml
ansible-playbook playbooks/06_swim_preflight.yml
ansible-playbook playbooks/06_swim_import_and_tag.yml
ansible-playbook playbooks/06_swim_distribute.yml
ansible-playbook playbooks/06_swim_activate.yml
ansible-playbook playbooks/06_swim_postcheck.yml
```

### YANG Suite (Docker)

Deploys [Cisco YANG Suite](https://developer.cisco.com/docs/yangsuite/) from the upstream [CiscoDevNet/yangsuite](https://github.com/CiscoDevNet/yangsuite) repository. Replaces the interactive `start_yang_suite.sh` prompts with Ansible templates (`setup.env`, self-signed nginx certs, `docker compose up`).

```bash
ansible-playbook playbooks/deploy_yangsuite.yml
# UI: https://<yangsuite_server_ip>:8443/
```

**Operations (health / restart):** see project skill
`.cursor/skills/yangsuite-jumpserver/` — scripts `yangsuite-health.sh` and
`yangsuite-restart.sh`. Memory note: `MEMORY.md` in that folder.

If `:8443` is connection refused, the Compose stack is usually stopped; restart
with `docker compose up -d` in `/opt/yangsuite/docker` on the host.

## Inventory layout and CML coupling

### How inventory is loaded

`ansible.cfg` points Ansible at the entire `inventory/` directory:

```ini
inventory = inventory/
```

On **every** `ansible-playbook` or `ansible-inventory` run from `ansible/`, Ansible parses **all** inventory sources in that folder and merges them into one host graph. There is no per-playbook inventory switch — the merge happens at startup, before any play executes.

| File | Type | Purpose |
|------|------|---------|
| `inventory/cml.yml` | Dynamic (`cisco.cml.cml_inventory`) | Live fabric nodes from the CML lab API |
| `inventory/static_inventory.yml` | Static YAML | Catalyst Center (`localhost`), image server, YANG Suite |
| `inventory/platform_groups.yml` | Static YAML | Parent groups `iosxe` / `nxos` over CML `node_definition` children |
| `inventory/group_vars/` | Vars | Connection and vault vars per group |

`cml.yml` requires `CML_HOST`, `CML_USERNAME`, `CML_PASSWORD`, and `CML_LAB` in the environment (set via `CICD Pipeline/.env` and direnv — see `../README.md`).

### Loaded vs used

**Loaded** means Ansible contacts CML and builds groups at parse time. **Used** means a play actually targets those hosts.

| Playbook(s) | `hosts:` target | Uses CML fabric hosts? |
|-------------|-----------------|------------------------|
| `11_backup_lab_configs.yml` | `Campus Fabric`, `IP Core`, `dmz`, `dhcp-server` (→ `iosxe` / `nxos`) | **Yes** — SSH backup to CML-tagged fabric devices |
| `01`–`10`, `06_swim_*`, `site.yml` | `catalyst_center` | No — Catalyst Center REST API on localhost |
| `deploy_http_image_server.yml` | `image_servers` | No — static host from `static_inventory.yml` |
| `deploy_yangsuite.yml` | `yangsuite_servers` | No — static host from `static_inventory.yml` |

Only **stage 11** SSHs to fabric devices. Stages 1–10 and SWIM talk to Catalyst Center API only. Even so, if CML is unreachable, inventory parsing for `cml.yml` can **fail the whole run** — including playbooks that never touch a router.

Typical failure when the lab is down or `CML_*` is wrong:

```text
Failed to parse .../inventory/cml.yml ... Connection refused
Unable to parse .../inventory/cml.yml as an inventory source
```

### Running without a live CML lab

For Catalyst Center–only work (stages 1–10, SWIM, deploy playbooks), pass an explicit inventory that omits `cml.yml`:

```bash
ansible-playbook -i inventory/static_inventory.yml playbooks/01_site_hierarchy.yml
```

`platform_groups.yml` is not needed for those playbooks (no `iosxe` / `nxos` targets). Do **not** use this shortcut for stage 11 — it requires CML for fabric hostnames and addresses.

### CML fabric details

Fabric devices (spine/leaf/border/core/dmz) come from the live CML lab via `inventory/cml.yml` (`cisco.cml.cml_inventory`). CML **tag assignments** on each node become Ansible groups when the tag is listed in `group_tags` in `cml.yml`. `platform_groups.yml` rolls CML `node_definition` groups (`cat9000v-uadp`, `nxosv9000`, …) into `iosxe` and `nxos` so `group_vars/iosxe` and `group_vars/nxos` apply.

The **MCP SSH server** uses a separate inventory under `utils/mcp-ssh-server/inventory/` (not this directory). Keep `group_tags` aligned between Ansible `cml.yml` and MCP `inventory/cml.yml` when you add CML tags.

### Inspect inventory from the CLI

From **`CICD Pipeline/`** (direnv loads `CML_*` from `.env`) or after `set -a && source .env && set +a`.

Use the project venv when pyenv has `virl2_client` 2.10+ (breaks `cisco.cml` 1.2.0):

```bash
cd "CICD Pipeline"
INV="../.venv/bin/ansible-inventory"   # from ansible/
# or from CICD Pipeline/:
INV=".venv/bin/ansible-inventory"
```

**CML plugin only** — tag groups, `node_definition` groups, `@fabric`:

```bash
cd ansible
bash ../verify-cml-inventory.sh
# equivalent:
../.venv/bin/ansible-inventory -i inventory/cml.yml --graph
```

**Full merged inventory** (what playbooks load: CML + `static_inventory.yml` + `platform_groups.yml`):

```bash
cd ansible
../.venv/bin/ansible-inventory --graph
```

**Other useful views:**

```bash
# JSON hostvars + group membership
../.venv/bin/ansible-inventory -i inventory/cml.yml --list

# One host (ansible_host, cml_facts, …)
../.venv/bin/ansible-inventory -i inventory/cml.yml --host spine1

# Members of one tag group
../.venv/bin/ansible-inventory -i inventory/cml.yml --graph | grep -A12 '@client:'

# iosxe/nxos parents from platform_groups.yml (stage 11, group_vars)
../.venv/bin/ansible-inventory --graph | grep -E '@iosxe|@nxos|@catalyst'
```

**Reading `--graph` output:**

| Group prefix | Meaning |
|--------------|---------|
| `@fabric` | All lab nodes (`group: fabric` in `cml.yml`) |
| `@cat9000v-uadp`, `@nxosv9000`, `@cat8000v`, `@alpine` | CML `node_definition` (image type) |
| `@Campus Fabric`, `@spine`, `@dmz`, `@client`, … | CML tags listed in `group_tags` |
| `@iosxe`, `@nxos` | Platform parents in `platform_groups.yml` (not from CML alone) |

Stage 11 backup uses the union of `Campus Fabric`, `IP Core`, `dmz`, and `dhcp-server`, then ∩ `iosxe` / `nxos`.

**Common warnings (usually safe to ignore):**

- `Invalid characters … in group names` — spaces/parens in names like `Campus Fabric`, `green02(dhcp)`; quote limits: `--limit "Campus Fabric"`.
- `Found both group and host with same name: dhcp-server` — node label equals tag name; `--limit dhcp-server` can be ambiguous.
- `Node.config is deprecated` — `virl2_client` 2.9.x with `cisco.cml` 1.2.0; pin `<2.10.0` (see `../requirements-ansible.txt`).

**Run stage 11 after verifying groups:**

```bash
ansible-playbook playbooks/11_backup_lab_configs.yml
ansible-playbook playbooks/11_backup_lab_configs.yml --limit spine
# Override tag scope:
ansible-playbook playbooks/11_backup_lab_configs.yml -e '{"backup_cml_tags":["dmz","dmz01"]}'
```

`virl2_client` must be `<2.10.0` for the `cisco.cml` 1.2.0 inventory plugin (`node.config` compatibility). See `../requirements-ansible.txt`.


## Common Overrides

```bash
DEBUG=true ansible-playbook playbooks/04_device_discovery.yml
ansible-playbook playbooks/01_site_hierarchy.yml -e state=deleted
ansible-playbook playbooks/06_swim_rollback.yml -e rollback_confirm=YES -e rollback_reload_ack=RELOAD_OK
ansible-playbook playbooks/deploy_http_image_server.yml \
  -e '{"image_local_paths":["/abs/cat9kv.SSA.bin","/abs/cat9kv.SPA.bin"]}'
```

Role task files include pre/post data structure comments for each API interaction.
