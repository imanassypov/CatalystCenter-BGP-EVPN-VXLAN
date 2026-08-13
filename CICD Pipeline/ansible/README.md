# Ansible CI/CD Pipeline

Single Ansible project for Catalyst Center provisioning (stages 1–11), SWIM, and config backup. All automation runs from this directory.

## Setup

First-time environment setup — installer, vault password, group vaults, encryption, `.env` — lives in one place: **[GETTING_STARTED.md](GETTING_STARTED.md)**. Follow it once per jump host, then come back here for the playbook reference.

Already set up? Every session needs:

```bash
source ~/tecops-venv/bin/activate
cd "CICD Pipeline" && set -a && . ./.env && set +a
cd ansible
```

The optional group vaults for SWIM (`image_servers`) and YANG Suite (`yangsuite_servers`) are covered in [GETTING_STARTED.md](GETTING_STARTED.md#optional-group-vaults). Stage 11 device SSH credentials come from `Settings/settings.json` — there is no separate vault for them.

### Collection requirements files

| File | Target environment | Notes |
|------|--------------------|-------|
| `collections/requirements.yml` | Control node on ansible-core 2.17 (`../requirements-ansible.txt`) | Current releases |
| `collections/requirements-jumphost.yml` | dCloud jump host — Python 3.9 venv, ansible-core 2.15 | Newest release of each collection that still declares `requires_ansible: >=2.15` |

Python 3.9 caps ansible-core at 2.15, so the jump host cannot run the 2.16+ collection releases. Installing the wrong file produces `Collection <name> does not support Ansible version 2.15.x` for every 2.16-only collection.

`cisco.catalystcenter` is the one deliberate exception: both files pin **2.9.0**, and the jump host therefore emits that warning for it. Every role reads results from `catalystcenter_response`, a key 2.4.0 introduced; 2.3.1 — the newest 2.15-compatible release — still returns `dnac_response`, so downgrading yields an empty `site_id_map` and stage 01 fails with `[400] NCND00067: The request body is invalid` on an empty `parentId`. 2.9.0 is verified working on ansible-core 2.15.13.

## Layout

```
CICD Pipeline/
├── .vault_pass
├── Settings/settings.json       # SSOT for all stages
└── ansible/
    ├── GETTING_STARTED.md       # first-time jump host setup (students start here)
    ├── inventory/               # CML dynamic (cml.yml) + static_inventory + group_vars
    ├── playbooks/               # 00_site_deploy orchestrator, 01–11 stages, deploy_* utilities
    ├── roles/                   # site_hierarchy, swim, template_sync, http_image_server, yangsuite_docker, …
    ├── config-backups/          # stage 11 output (gitignored timestamps)
    ├── logs/                    # SWIM evidence JSON (gitignored)
    └── docs/swim/               # SWIM reference diagrams
```

## Pipeline Order

Full orchestrator (stages 1–10, excludes SWIM and backup):

```bash
ansible-playbook playbooks/00_site_deploy.yml
```

| Playbook | Stage | Description |
|----------|-------|-------------|
| `00_site_deploy.yml` | 0 | Orchestrator — imports stages 1–10 |
| `01_site_hierarchy.yml` | 1 | Build site hierarchy |
| `02_network_settings.yml` | 2 | Apply network settings |
| `03_credentials.yml` | 3 | CLI/SNMP/NETCONF credentials |
| `04_device_discovery.yml` | 4 | Device discovery |
| `05_assign_to_site.yml` | 5 | Assign devices to sites |
| `06.0`–`06.5_swim_*.yml` | 6 | SWIM lifecycle (run in order; see below) |
| `06.6_swim_rollback.yml` | 6 | SWIM rollback — manual, guarded (see Common Overrides) |
| `07_template_sync.yml` | 7 | Template sync from GitHub or a local directory |
| `08_network_profile.yml` | 8 | Network profiles |
| `09_provision_devices.yml` | 9 | Device provisioning |
| `10_deploy_composite.yml` | 10 | Composite template deploy |
| `11_backup_lab_configs.yml` | 11 | IOS-XE/NX-OS config backup |
| `deploy_yangsuite.yml` | util | Cisco YANG Suite (Docker) |

### Playbook annotation convention

Every playbook and role task file opens with a boxed header block. Read it
first — it is the fastest way to understand a stage without tracing the role.

```yaml
---
# =============================================================================
# <filename>  —  Pipeline stage <NN>
# =============================================================================
# What the stage does and why it exists.
#
# Sourced:
#   settings.json → settings_data.project[]: <exact keys consumed>
#   connection.yml / vault.yml: <exact vars consumed>
#
# Produced:
#   <exact facts set, with example values>
#   In Catalyst Center: <objects created or changed>
#
# Depends on: <prior stages>
# Module: <collection module driven via module_defaults>
#
# Run: ansible-playbook playbooks/<filename>
# =============================================================================
```

Rules:

- `Sourced:` / `Produced:` must name **real** variables and nested key paths, with example values — never a vague summary.
- Disruptive playbooks are marked `*DISRUPTIVE*` on the title line (`06.4`, `06.6`).
- Multi-play files (`11_backup_lab_configs.yml`) get a `# ── Play N: … ──` divider above each play.
- Inline `# ── section ── ` dividers separate logical blocks inside role task files.

### Data-manipulation task annotation

Any task that transforms data — `set_fact`, `json_query`, accumulator loops,
payload assembly — carries an `Example` block directly above it showing the
payload going **in** and the payload coming **out**:

```yaml
# Example — <scoping note, e.g. "single project entry, rollback image defined">
#   In : <var> = {
#          "key": "value"
#        }
#   Out: <var> = [
#          { "key": "value" }
#        ]
# <one or two lines stating what the filters did and why>
- name: <task name>
  ansible.builtin.set_fact:
```

Rules:

- **No elisions.** Never write `…`, `...`, or `and so on` inside an example
  data structure. Every key and every value is written out in full, including
  long image filenames, all six device IPs, and complete UUIDs. A reader must
  be able to copy the example into a scratch playbook and get the documented
  result.
- Values come from the **real** `Settings/settings.json` and
  `inventory/group_vars/catalyst_center/connection.yml` — not invented data.
- Where a task has branching outcomes (create vs update vs no-op), give one
  complete `In:`/`Out:` pair **per branch** and state which tasks fire.
- Opaque secrets (auth tokens, Git PATs, blob SHAs) use a complete
  well-formed literal of the right shape, never a truncated one.
- The trailing note explains the non-obvious filter behaviour — deduplication,
  `select('mapping')` guards, keys that get dropped, type coercions — not what
  the next line already says.

Coverage is complete: every data-manipulation task under `roles/*/tasks/` carries
an `Example` block. `defaults/` and `handlers/` are excluded by design — they hold
flat data and hook declarations with no transformation to document. When you add a
new `set_fact` or payload-assembly task, add its `Example` block in the same commit.

### Task naming convention

`ansible-lint`'s `name[template]` rule requires that a task name contain **at most one
Jinja expression, positioned at the very end**. The static leading text is what Ansible
callbacks, log aggregation and `--start-at-task` key off, so it must be stable across
loop iterations.

```yaml
# ✅ correct — static text first, one trailing template
- name: "Assert composite template found | {{ deploy_entry.template_name }}"
- name: "Resolve site UUID | {{ site_entry.key }}"

# ❌ violates name[template] — template leads the name
- name: "[{{ deploy_entry.template_name }}] Assert composite template found"

# ❌ violates name[template] — two templates separated by static text
- name: "Derive path | {{ _parent }}/{{ _name }}"
# ✅ fix — concatenate into a single expression
- name: "Derive path | {{ _parent ~ '/' ~ _name }}"

# ❌ violates name[template] — counts/state embedded mid-name
- name: "Phase B — Create/update sites ({{ site_configs_list | length }} total)"
# ✅ fix — keep the name static, report the count from the task's own output
- name: "Phase B — Create/update sites"
```

Rules:

- Loop-variable suffixes stay — they are the only thing disambiguating otherwise
  identical banners across iterations. They just move to the end after a ` | ` separator.
- Counts, states and derived values never belong in a name. Move them into the
  `debug`/`assert` message of the same task, where they are already visible.
- Lint rules the project deliberately suppresses live in
  [`.ansible-lint`](../../.ansible-lint) at the repository root — one file shared by
  the CLI and the VS Code Ansible extension, which lints from the workspace root.
  `name[template]` is **not** among them — fix violations rather than skipping the rule.

### SWIM (stage 6)

Run in numeric order — `06.0` stages the images on the HTTP server that `06.2` imports from:

```bash
ansible-playbook playbooks/06.0_swim_deploy_http_image_server.yml
ansible-playbook playbooks/06.1_swim_preflight.yml
ansible-playbook playbooks/06.2_swim_import_and_tag.yml
ansible-playbook playbooks/06.3_swim_distribute.yml
ansible-playbook playbooks/06.4_swim_activate.yml
ansible-playbook playbooks/06.5_swim_postcheck.yml
```

`06.4_swim_activate.yml` reloads devices. `06.6_swim_rollback.yml` is out-of-band and runs only on failure.

### Template sync (stage 7)

`07_template_sync.yml` reads the `.j2` templates and the composite YAML from one of two sources, selected by `template_source` in `inventory/group_vars/catalyst_center/connection.yml`. Both sources produce the same fact — `repo_tree_entries`, a list of `{path: <root-relative path>}` — so everything downstream (ordering, composite parsing, the `template_workflow_manager` payload) is identical either way.

| `template_source` | Reads from | Auth | Commit metadata | Diff header |
|---|---|---|---|---|
| `git` (default) | GitHub REST API on `git_repo` / `git_branch` | `git_token` (vault) — optional for public repos, lifts the 60 req/hr anonymous limit | Real commit message, author, SHA | Honours `include_diff_header` |
| `local` | `template_local_root` on the machine running Ansible | none | Synthesised `Synced from local directory <date> <time>` | Always off — there is no commit to diff |

```bash
ansible-playbook playbooks/07_template_sync.yml                          # GitHub
ansible-playbook playbooks/07_template_sync.yml -e template_source=local  # this working tree
ansible-playbook playbooks/07_template_sync.yml -e template_source=local \
  -e template_local_root=/abs/path/to/templates
```

| Variable | Default | Description |
|---|---|---|
| `template_source` | `git` | `git` or `local`. Any other value fails the run immediately. |
| `template_local_root` | repository root (derived from `playbook_dir`) | Directory the `local` source scans. Must exist and be a directory. |
| `git_repo_subfolders[].path` | see `connection.yml` | Relative to the repo root (`git`) **or** to `template_local_root` (`local`) — one list drives both. |
| `git_repo_subfolders[].project_name` | see `connection.yml` | Catalyst Center Template Programmer project each subfolder syncs into. |

**How the `template_local_root` default resolves.** `playbook_dir` is `<repo>/CICD Pipeline/ansible/playbooks`, so the three `dirname` calls in `template_local_root: "{{ playbook_dir | dirname | dirname | dirname }}"` walk up to the repository root:

| Step | Value |
|---|---|
| `playbook_dir` | `<repo>/CICD Pipeline/ansible/playbooks` |
| `\| dirname` | `<repo>/CICD Pipeline/ansible` |
| `\| dirname` | `<repo>/CICD Pipeline` |
| `\| dirname` | `<repo>` ← `template_local_root` |

The default therefore points at whichever clone the playbook is running from, with no absolute path hard-coded. Move `07_template_sync.yml` to a different directory depth and this expression must be adjusted, or `template_local_root` set explicitly. Note that `playbook_dir` only equals `playbooks/` under `ansible-playbook` — an ad-hoc `ansible ... -m debug -a var=template_local_root` sets it to the cwd and so reports a path one level too high.

Only the directories named in `git_repo_subfolders` are scanned in `local` mode — a recursive walk of the whole root would descend into `.git` and `.venv`, whose `.yml`/`.j2` files are noise. A subfolder with no `.j2` files logs a warning and is skipped, which is why the empty DMZ folder does not fail the run.

File contents are read with `slurp` + `b64decode` rather than the `file` lookup, so bytes — including trailing newlines — match what the Git path produces.

`local` mode still requires a reachable Catalyst Center and the `dnacentersdk` Python package in the interpreter running the play; only the *source* of the template text changes.

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
| `01`–`10`, `06.1`–`06.6_swim_*`, `00_site_deploy.yml` | `catalyst_center` | No — Catalyst Center REST API on localhost |
| `06.0_swim_deploy_http_image_server.yml` | `image_servers` | No — static host from `static_inventory.yml` |
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
ansible-playbook playbooks/07_template_sync.yml -e template_source=local
ansible-playbook playbooks/06.6_swim_rollback.yml -e rollback_confirm=YES -e rollback_reload_ack=RELOAD_OK
ansible-playbook playbooks/06.0_swim_deploy_http_image_server.yml \
  -e '{"image_local_paths":["/abs/cat9kv.SSA.bin","/abs/cat9kv.SPA.bin"]}'
```

Role task files include pre/post data structure comments for each API interaction.
