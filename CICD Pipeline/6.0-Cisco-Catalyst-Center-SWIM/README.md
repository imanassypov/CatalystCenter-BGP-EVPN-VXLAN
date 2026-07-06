> **Deprecated:** Playbooks moved to [`../ansible/playbooks/`](../ansible/playbooks/). See [`../ansible/README.md`](../ansible/README.md).

# Catalyst Center SWIM Automation for Catalyst 9000 (Virtual)

Operationalize **Software Image Management (SWIM)** on Cisco Catalyst Center using the
`cisco.catalystcenter` Ansible collection. This repository delivers an opinionated,
phase-by-phase upgrade pipeline — import, golden tagging, distribution, activation, post-validation,
and rollback — driven entirely from a single declarative data file.

Validated against **Cisco Catalyst Center 2.3.7.6** with `cisco.catalystcenter` collection
`2.9.0` and `catalystcentersdk` `3.1.6.x`, targeting Cisco Catalyst 9000 Series Virtual switches
(`cat9kv`).

---

## Table of Contents

1. [SWIM on Catalyst Center — methodology](#1-swim-on-catalyst-center--methodology)
2. [The Cisco Catalyst Center Ansible collection](#2-the-cisco-catalyst-center-ansible-collection)
   - [2.1 Installation](#21-installation)
   - [2.2 Workflow Manager modules — high-level abstraction with data models](#22-workflow-manager-modules--high-level-abstraction-with-data-models)
   - [2.3 Why Workflow Manager modules](#23-why-workflow-manager-modules)
3. [Mapping SWIM operations to workflow modules](#3-mapping-swim-operations-to-workflow-modules)
4. [Repository layout](#4-repository-layout)
5. [Install dependencies](#5-install-dependencies)
6. [Configure credentials (Ansible Vault)](#6-configure-credentials-ansible-vault)
7. [The data model — the `swim` block in `settings.json`](#7-the-data-model--the-swim-block-in-settingsjson)
8. [The playbooks, explained](#8-the-playbooks-explained)
9. [Run sequence](#9-run-sequence)
10. [Evidence and logging](#10-evidence-and-logging)
11. [Troubleshooting](#11-troubleshooting)
12. [Appendix A: Image distribution (HTTP) server setup](#appendix-a-image-distribution-http-server-setup)
13. [Appendix B: Alternative approach — individual API modules (no Workflow Manager)](#appendix-b-alternative-approach--individual-api-modules-no-workflow-manager)

---

## 1. SWIM on Catalyst Center — methodology

**Software Image Management (SWIM)** is the Catalyst Center function that centralizes the storage,
validation, and lifecycle of network operating-system images. Rather than copying `.bin` files to
devices by hand and reloading them one at a time, SWIM lets you define a *desired* software state
per device family and role, then drives every managed device toward it with built-in pre/post
validation. This automation mirrors the GUI workflow documented in the
[Catalyst Center 2.3.7 User Guide — Manage Software Images](https://www.cisco.com/c/en/us/td/docs/cloud-systems-management/network-automation-and-management/catalyst-center/2-3-7/user_guide/b_cisco_catalyst_center_user_guide_237/b_cisco_dna_center_ug_2_3_7_chapter_0100.html).

### 1.1 The image repository

Catalyst Center maintains a central **image repository** that stores every unique software image,
SMU, subpackage, and ROMMON image by type and version. During import, Catalyst Center performs
**Integrity Verification (IV)** — comparing the software/hardware checksum of the imported image
against a **Known Good Values (KGV)** file — to detect tampering or corruption before the image is
ever pushed to a device.

### 1.2 Golden images and device roles

A **golden image** is a validated, standardized image that an operator designates as the
*compliance target* for a given **device family** — and optionally narrowed to a specific
**device role** (e.g. `CORE`, `DISTRIBUTION`, `ACCESS`, `BORDER ROUTER`, or `ALL`). Designating an
image as golden is how you tell Catalyst Center "this is what these devices *should* be running."
Catalyst Center then continuously compares each device's running image against its golden tag and
flags any device that is **outdated**.

> **Key idea:** the golden tag is the contract. Distribution and activation simply move devices
> toward that contract; compliance reporting measures how far each device is from it.

### 1.3 The upgrade lifecycle

A SWIM upgrade is a sequence of distinct, independently observable operations:

| Stage | What Catalyst Center does |
|---|---|
| **Import** | Pulls the image into the repository (from cisco.com, a URL/file server, or local upload) and runs Integrity Verification. |
| **Golden tag** | Marks the image as the compliance target for a device family + role + site. |
| **Upgrade readiness prechecks** | File-transfer reachability, NTP clock, flash space (with auto-cleanup), config register, crypto/TLS, startup config, image compatibility, and version-support checks. A device that fails prechecks is blocked from upgrade. |
| **Distribute** | Copies (`install add`) the image to device flash. **No reboot** — the running image is untouched. |
| **Activate** | Makes the new image the running image (`install activate` + `install commit`). **This reboots the device.** Can be scheduled, ordered (parallel/sequential), and gated by pre/post activation checks. |
| **Postchecks** | CPU usage, route summary, interface state, and image-activation verification to confirm the network state is unchanged. |

Separating **distribute** from **activate** is deliberate and operationally important: you can
stage the binary onto every device during business hours (zero impact), then activate (reboot)
inside a maintenance window. This repository preserves that separation as two distinct playbooks.

### 1.4 Image distribution server

For at-scale or remote-site distribution, Catalyst Center can hand off image transfer to an
external **image distribution server** (SFTP/SCP/HTTPS), or — as in this lab — pull a remotely
hosted image over HTTP during import. See [Appendix A](#appendix-a-image-distribution-http-server-setup).

---

## 2. The Cisco Catalyst Center Ansible collection

[![cisco.catalystcenter on Ansible Galaxy](images/cisco.catalystcenter.collection.png)](https://galaxy.ansible.com/ui/repo/published/cisco/catalystcenter/)

The [`cisco.catalystcenter`](https://galaxy.ansible.com/ui/repo/published/cisco/catalystcenter/)
collection is Cisco's **officially supported** Ansible content for Catalyst Center, published on
[Ansible Galaxy](https://galaxy.ansible.com/ui/repo/published/cisco/catalystcenter/) and
[Red Hat Automation Hub](https://console.redhat.com/ansible/automation-hub/repo/published/cisco/catalystcenter/).

> **Important:** `cisco.catalystcenter` is the **only** collection that will receive new features
> and Catalyst Center version support going forward. The legacy `cisco.dnac` collection is
> deprecated — all new development, bug fixes, and releases are delivered exclusively through
> `cisco.catalystcenter`. Use `cisco.catalystcenter` for all new automation.

It ships two distinct families of modules:

- **SDK / "intent" modules** — thin, one-to-one wrappers around individual Catalyst Center Intent
  API endpoints (e.g. `swim_import_local`, `swim_trigger_distribution`). These are granular and
  imperative: you orchestrate the ordering, polling, and idempotency yourself.
- **Workflow Manager modules** (the `*_workflow_manager` family) — Cisco's higher-level,
  **declarative** automation. You describe the *desired end state*, and the module performs the
  multi-step API choreography (lookups, ID resolution, submission, task polling, and verification)
  to reach it. These are the modules Cisco recommends for day-2 operations, and the ones this
  repository is built on.

### 2.1 Installation

Install the collection from Ansible Galaxy:

```bash
ansible-galaxy collection install cisco.catalystcenter
```

Install the required Python SDK (needed by every module at runtime):

```bash
pip install catalystcentersdk
```

> **Python version:** `catalystcentersdk` requires **Python ≥ 3.12**. Build your virtualenv with a
> 3.12+ interpreter. Pin the exact collection version for reproducible automation:
>
> ```bash
> ansible-galaxy collection install cisco.catalystcenter:==2.9.0
> ```
>
> or declare it in a `requirements.yml` and install with
> `ansible-galaxy collection install -r requirements.yml`.

### 2.2 Workflow Manager modules — high-level abstraction with data models

The `*_workflow_manager` family (39 modules as of v2.9.0) provides a **declarative, data-model-driven**
interface over the full Catalyst Center API surface. Rather than calling individual REST endpoints,
you pass a structured `config:` data model that describes *desired state*, and the module handles
the entire multi-step API interaction to reach it.

[![cisco.catalystcenter workflow manager modules](images/cisco.catalystcenter.workflows.png)](https://galaxy.ansible.com/ui/repo/published/cisco/catalystcenter/content/module/swim_workflow_manager/)

**Key benefits:**

- **Declarative data models** — express intent (`import_image_details`, `tagging_details`,
  `image_activation_details`) rather than imperative API calls; the module resolves all UUIDs and
  endpoint routing internally
- **Built-in task polling** — submits asynchronous Catalyst Center tasks and blocks until
  completion, success, or configurable timeout (`catalystcenter_api_task_timeout`)
- **Idempotency** — re-running against an already-converged state returns `ok: changed=false`
  without issuing redundant API calls
- **State verification** — `config_verify: true` re-reads Catalyst Center state post-apply to
  confirm the change landed, not just that the API accepted the request
- **Bulk and site-scoped operations** — target entire sites, device families, and roles in a single
  `config:` entry rather than looping over individual device IPs
- **Comprehensive error handling** — surfaces per-device failure detail, skipped devices, and
  task-level errors as structured Ansible output suitable for downstream `assert` or evidence tasks

The coverage spans three domains — Base Automation, SDA Fabric, and Operations — across all major
industry verticals. **SWIM** falls under the **Operations** domain, covering golden image tagging
per site/role/device and the full update process (import → tag → distribute → activate →
postcheck).

![Cisco Validated Ansible Workflows Coverage](images/cisco.catalystcenter.workflows.coverage.png)

### 2.3 Why Workflow Manager modules

Every playbook here uses `cisco.catalystcenter.swim_workflow_manager` (and
`inventory_workflow_manager` / `network_compliance_workflow_manager` for supporting phases).
Full parameter reference and annotated examples are available in the
[`swim_workflow_manager` module documentation on Ansible Galaxy](https://galaxy.ansible.com/ui/repo/published/cisco/catalystcenter/content/module/swim_workflow_manager/).
Workflow Manager modules give us:

- **Declarative `config:`** — you pass the same data structures the Catalyst Center GUI builds
  internally (`import_image_details`, `tagging_details`, `image_distribution_details`,
  `image_activation_details`).
- **Built-in task polling** — the module submits the asynchronous Catalyst Center task and blocks
  until it completes, succeeds, or times out, governed by `catalystcenter_api_task_timeout` and
  `catalystcenter_task_poll_interval`.
- **`config_verify: true`** — after applying, the module re-reads Catalyst Center state to confirm
  the change actually landed, rather than trusting the submit response alone.
- **Idempotency** — re-running a play that imports an already-present image, or tags an
  already-golden image, reports `ok` instead of failing or duplicating work.

### 2.4 Connection model

Catalyst Center modules run with `connection: local` against the control node — Ansible talks to
the Catalyst Center REST API over HTTPS; there is no SSH to the appliance. A single placeholder
host (`catalyst_center`, in group `catc`) carries the connection variables. Authentication and
endpoint parameters are supplied to every task from
[`inventory/group_vars/catc/connection.yml`](inventory/group_vars/catc/connection.yml) and the
encrypted vault.

---

## 3. Mapping SWIM operations to workflow modules

Each SWIM stage from [§1.3](#13-the-upgrade-lifecycle) maps to a specific Workflow Manager module
invocation. The table below is the Rosetta Stone for this repository. See the
[`swim_workflow_manager` module docs](https://galaxy.ansible.com/ui/repo/published/cisco/catalystcenter/content/module/swim_workflow_manager/)
for the full parameter schema and the
[annotated examples](https://galaxy.ansible.com/ui/repo/published/cisco/catalystcenter/content/module/swim_workflow_manager/?keywords=swim#examples)
for each `config:` sub-key.

| SWIM operation | Module | `config:` key | Playbook |
|---|---|---|---|
| Import image to repository | `swim_workflow_manager` | `import_image_details` | [`10_import_and_tag.yml`](playbooks/10_import_and_tag.yml) |
| Mark image golden | `swim_workflow_manager` | `tagging_details` | [`10_import_and_tag.yml`](playbooks/10_import_and_tag.yml) |
| Distribute image to devices | `swim_workflow_manager` | `image_distribution_details` | [`20_distribute.yml`](playbooks/20_distribute.yml) |
| Activate image (reload) | `swim_workflow_manager` | `image_activation_details` | [`30_activate.yml`](playbooks/30_activate.yml) |
| Rollback (re-tag + activate prior image) | `swim_workflow_manager` | `tagging_details` → `image_activation_details` | [`35_rollback.yml`](playbooks/35_rollback.yml) |
| Inventory resync (refresh device state) | `inventory_workflow_manager` | `ip_address_list` / `site_name` | [`00_preflight.yml`](playbooks/00_preflight.yml) |
| IMAGE compliance check | `network_compliance_workflow_manager` | `run_compliance_categories: [IMAGE]` | [`00_preflight.yml`](playbooks/00_preflight.yml), [`40_postcheck.yml`](playbooks/40_postcheck.yml) |

### 3.1 The three different "device family" names — a critical distinction

The single most common source of SWIM automation failures is conflating three *different* names
that Catalyst Center uses in three different contexts. This repository keeps them explicit:

| Where | Field | Value on this cluster | Source of truth |
|---|---|---|---|
| **Golden tag** (`tagging_details`) | `device_image_family_name` | `Cisco Catalyst 9000 UADP 8 Port Virtual Switch` (id `999999901`) | `GET /dna/intent/api/v1/image/importation/device-family-identifiers` |
| **Distribute / activate** | `device_family_name` | `Switches and Hubs` | Inventory (network-device API `family`) |
| **Distribute / activate** | `device_series_name` | `Cisco Catalyst 9000 Series Virtual Switches` | Inventory (network-device API `series`) |

> **Why this matters:** tagging is keyed to the **SWIM device-family identifier**, while
> distribution and activation select devices using the **inventory** family/series. Using the
> golden-tag identifier in a distribute call returns *"no eligible devices."* Both names are
> pre-resolved in the `swim` block of `settings.json` so operators never have to guess.

---

## 4. Repository layout

```
6.0-Cisco-Catalyst-Center-SWIM/
├── ansible.cfg                       # inventory path, callbacks, vault settings
├── requirements.txt                  # Python deps (ansible-core, ansible-lint, catalystcentersdk)
├── requirements.yml                  # cisco.catalystcenter collection pin (2.9.0)
├── .ansible-lint                     # lint profile
├── inventory/
│   ├── hosts.yml                     # 'catalyst_center' host in group 'catc' (connection: local)
│   └── group_vars/catc/
│   ├── connection.yml            # catalystcenter_* connection + settings_json_path
│       └── vault.yml                 # ENCRYPTED: catalystcenter_username / _password
├── tasks/
│   └── load_swim_details.yml         # synthesises swim_details from settings.json (imported by every playbook)
├── playbooks/
│   ├── 00_preflight.yml              # resync + baseline IMAGE compliance
│   ├── 10_import_and_tag.yml         # import images + mark golden
│   ├── 20_distribute.yml             # copy image to flash (no reload)
│   ├── 30_activate.yml               # activate image (reloads devices)
│   ├── 35_rollback.yml               # re-tag + activate prior-stable image
│   └── 40_postcheck.yml              # post-activation IMAGE compliance
└── logs/                             # SDK log + per-phase JSON evidence (gitignored)
```

> **Source of truth:** image details are **not** stored in this folder. They live in the central
> data model at [`../Settings/settings.json`](../Settings/settings.json) under each project entry's
> `swim` block, shared with stages 1.0 (site hierarchy), 4.0 (discovery) and 9.0 (provisioning).
> [`tasks/load_swim_details.yml`](tasks/load_swim_details.yml) synthesises the `swim_details`
> structure at run time — see [section 7](#7-the-data-model--the-swim-block-in-settingsjson).

---

## 5. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml
```

> **Python version:** `catalystcentersdk` requires **Python ≥ 3.12**. Build the virtualenv with a
> 3.12+ interpreter.

---

## 6. Configure credentials (Ansible Vault)

Catalyst Center credentials live in [`inventory/group_vars/catc/vault.yml`](inventory/group_vars/catc/vault.yml)
(`catalystcenter_username`, `catalystcenter_password`) as a **whole-file Ansible Vault** blob.
Nothing is committed in plaintext; the file is decrypted at run time when you supply the vault
password.

Edit the stored credentials in place (you'll be prompted for the vault password):

```bash
ansible-vault edit inventory/group_vars/catc/vault.yml
```

Supply the vault password at run time — interactively:

```bash
ansible-playbook playbooks/00_preflight.yml --ask-vault-pass
```

…or from a password file (keep it out of version control; `.vault_pass` is in `.gitignore`):

```bash
ansible-playbook playbooks/00_preflight.yml --vault-password-file .vault_pass
```

### 6.1 Connection parameters

[`inventory/group_vars/catc/connection.yml`](inventory/group_vars/catc/connection.yml) holds the
non-secret connection settings applied to every task:

| Variable | Value | Purpose |
|---|---|---|
| `catalystcenter_host` | `198.18.129.100` | Catalyst Center IP/FQDN |
| `catalystcenter_port` | `443` | HTTPS port |
| `catalystcenter_version` | `2.3.7.6` | Targets the correct API surface |
| `catalystcenter_verify` | `false` | Skip TLS verification (self-signed lab cert) |
| `catalystcenter_log` / `_log_level` | `true` / `INFO` | SDK logging to `logs/catc-swim.log` |
| `catalystcenter_api_task_timeout` | `3600` | Max seconds to wait on an async task |
| `catalystcenter_task_poll_interval` | `30` | Seconds between task-status polls |
| `validate_response_schema` | `true` | Validate API responses against the SDK schema |
| `settings_json_path` | `../../Settings/settings.json` | Central data model consumed by every playbook; relative paths resolve from the playbook directory |

> Activation tasks override the timeout/poll values inline (`7200` / `60`) because device reloads
> take longer than import or distribution.

---

## 7. The data model — the `swim` block in `settings.json`

SWIM intent lives in the **central data model**, [`../Settings/settings.json`](../Settings/settings.json) —
the same file consumed by stages 1.0 (site hierarchy), 4.0 (discovery) and 9.0 (provisioning).
Each `project` entry carries a `swim` block holding the irreducible image facts; everything the
`swim_workflow_manager` modules need is **synthesised at run time** by
[`tasks/load_swim_details.yml`](tasks/load_swim_details.yml), which every playbook imports as its
first task.

```json
"swim": {
  "image_server_base_url": "http://198.18.134.28/images",
  "device_family_identifier": "Cisco Catalyst 9000 UADP 8 Port Virtual Switch",
  "device_family_name": "Switches and Hubs",
  "device_series_name": "Cisco Catalyst 9000 Series Virtual Switches",
  "device_role": "ALL",
  "upgrade_image": "cat9kv-universalk9.BLD_V262_THROTTLE_LATEST_20260529_003538.SSA.bin",
  "rollback_image": "cat9kv-universalk9.17.15.03.SPA.bin",
  "activation": {
    "device_upgrade_mode": "install",
    "distribute_if_needed": true,
    "schedule_validate": false
  }
}
```

| `swim` field | Purpose |
|---|---|
| `image_server_base_url` | HTTP base URL of the file server (see [Appendix A](#appendix-a-image-distribution-http-server-setup)). Image URLs are `base_url/<image>`. |
| `device_family_identifier` | **SWIM device-family identifier** used for golden tagging (`Cisco Catalyst 9000 UADP 8 Port Virtual Switch`, id `999999901`). |
| `device_family_name` | **Inventory** family used for distribute/activate targeting (`Switches and Hubs`). |
| `device_series_name` | **Inventory** series used for distribute/activate targeting. |
| `device_role` | Role filter for tag/distribute/activate (e.g. `ALL`). |
| `upgrade_image` | Filename of the image to import, tag golden, distribute and activate. |
| `rollback_image` | Filename of the prior-stable image (imported alongside the upgrade; used by `35_rollback.yml`). |
| `activation.device_upgrade_mode` | `install` (banked — install-mode) upgrade. |
| `activation.distribute_if_needed` | Distribute first if the image isn't already on the device. |
| `activation.schedule_validate` | **Must be `false`** to trigger real activation (see §7.2). |

### 7.1 How `swim_details` is synthesised

[`tasks/load_swim_details.yml`](tasks/load_swim_details.yml) loads `settings.json`, derives the
`site_name` from each entry's `HierarchyParent/Area/Bldg/Floor` fields (exactly like stages 1.0 and
9.0 — no hardcoded site path), and builds the `swim_details` structure the playbooks loop over:

```yaml
swim_details:
  import_images:        # → 10: { name, import_image_details }  (upgrade + rollback images)
  golden_tag_images:    # → 10: { name, tagging_details }
  distribute_images:    # → 20: { name, image_distribution_details }
  activate_images:      # → 30: { name, image_activation_details }
  rollback_images:
    tag:                # → 35: { name, tagging_details }
    activate:           # → 35: { name, image_activation_details }
```

| Synthesised section | Consumed by | Module config key | Built from |
|---|---|---|---|
| `import_images` | `10` | `import_image_details` | `upgrade_image` **and** `rollback_image` (deduplicated), each as `base_url/<image>`. |
| `golden_tag_images` | `10` | `tagging_details` | `upgrade_image` + `device_family_identifier` + derived `site_name` + `device_role`. |
| `distribute_images` | `20` | `image_distribution_details` | `upgrade_image` + `device_family_name`/`device_series_name` + derived `site_name`. |
| `activate_images` | `30` | `image_activation_details` | `upgrade_image` + inventory family/series + `activation.*` flags. |
| `rollback_images.tag` | `35` | `tagging_details` | `rollback_image` + `device_family_identifier`. |
| `rollback_images.activate` | `35` | `image_activation_details` | `rollback_image` (`activate_lower_image_version: true`). |

### 7.2 Design principles

- **Single source of truth, no duplication.** Each fact (image filename, family names, base URL) is
  declared **once** in the `swim` block. The five per-phase config blocks are derived, so image
  names and family identifiers can never drift out of sync.
- **`site_name` is derived, not typed.** The target site path is composed from the same
  `Hierarchy*` fields used by site-hierarchy and provisioning — change the hierarchy once and SWIM
  follows automatically.
- **Multi-site by construction.** Every `project` entry with a `swim` block yields its own image
  set, so a multi-site `settings.json` upgrades each site to its declared image with no extra work.
- **Targets derive from the data, not from CLI args.** Pre-flight and post-check derive their site
  list from the synthesised `golden_tag_images[*].tagging_details.site_name`.
- **Rollback is first-class.** The `rollback_image` is imported alongside the upgrade image so it is
  always present in the repository, never scrambled for after a failure.

### 7.3 Activation flags worth knowing

| Flag | This repo | Meaning |
|---|---|---|
| `activate_lower_image_version` | `false` (upgrade) / `true` (rollback) | Allow activating an image *older* than what's running. Required for rollback. |
| `distribute_if_needed` | `true` | If the image isn't already on the device, distribute it first as part of activation. |
| `schedule_validate` | `false` | **Must be `false`** to trigger real activation. When `true`, CatC runs pre-validation only and the activation task returns `SUCCESS` immediately as a no-op — devices are never reloaded. |

### 7.4 Adding a site or role

Edit the `swim` block (and, for a new site, add another `project` entry with its own `Hierarchy*`
fields and `swim` block) in [`../Settings/settings.json`](../Settings/settings.json). No playbook
edits required — the synthesis and the derived compliance-site list pick it up automatically.

---

## 8. The playbooks, explained

All playbooks target `hosts: catc`, run `connection: local`, import
[`tasks/load_swim_details.yml`](tasks/load_swim_details.yml) to synthesise `swim_details` from
`settings.json`, and stamp a `run_id` (`YYYYMMDD-HHMMSS`) onto their evidence file. Each phase is
independently runnable and idempotent (except activation/rollback, which reboot devices).

### 8.1 `00_preflight.yml` — resync + baseline compliance

**Purpose:** establish a known-good starting point and a *before* compliance snapshot.

1. **Derive `target_sites`** from `golden_tag_images[*].tagging_details.site_name` (deduplicated).
2. **Resync devices** at those sites (`inventory_workflow_manager`, `device_resync: true`) so
   Catalyst Center's view of running images is current before any decisions are made.
3. **Run IMAGE compliance** (`network_compliance_workflow_manager`,
   `run_compliance_categories: [IMAGE]`) per site to record the baseline.
4. **Evaluate results** — surfaces skipped devices and hard failures, writes evidence, and **fails
   fast** on a resync failure or a compliance task error so you don't upgrade on a broken baseline.

> Compliance categories supported by the module: `INTENT`, `RUNNING_CONFIG`, `IMAGE`, `PSIRT`,
> `EOX`, `NETWORK_SETTINGS`. This phase scopes to `IMAGE` only.

### 8.2 `10_import_and_tag.yml` — import + golden tag

**Purpose:** populate the repository and set the compliance contract.

1. **Import** — loops `swim_details.import_images`, passing `import_image_details` to
   `swim_workflow_manager`. Catalyst Center pulls each `.bin` over HTTP and runs Integrity
   Verification. Both the upgrade and rollback images are imported here.
2. **Golden tag** — loops `swim_details.golden_tag_images`, passing `tagging_details` to mark the
   upgrade image golden for the target site + role using the SWIM device-family identifier.

Idempotent: an already-imported image or already-golden tag returns `ok`.

> **Module reference:**
> [`swim_workflow_manager` — `import_image_details` / `tagging_details` examples](https://galaxy.ansible.com/ui/repo/published/cisco/catalystcenter/content/module/swim_workflow_manager/?keywords=swim#examples)

### 8.3 `20_distribute.yml` — stage the binary (no reload)

**Purpose:** copy the image to device flash with **zero service impact**.

Loops `swim_details.distribute_images`, passing `image_distribution_details` (targeted by
**inventory** family/series). Catalyst Center runs upgrade-readiness prechecks (flash space with
auto-cleanup, reachability, checksum) and copies the image. Devices keep running their current
image. Safe to run during business hours.

> **Module reference:**
> [`swim_workflow_manager` — `image_distribution_details` examples](https://galaxy.ansible.com/ui/repo/published/cisco/catalystcenter/content/module/swim_workflow_manager/?keywords=swim#examples)

### 8.4 `30_activate.yml` — activate (reloads devices)

**Purpose:** make the new image the running image. **This reboots devices** — run inside a
maintenance window.

Loops `swim_details.activate_images`, passing `image_activation_details` with
`distribute_if_needed: true` (distributes first if needed) and `schedule_validate: false`.
Uses an extended timeout (`7200s`) and poll interval (`60s`) to accommodate reloads.

> **Critical — `schedule_validate: false` is mandatory for real activation.**
> When set to `true`, Catalyst Center interprets the request as a *pre-validation only* run:
> the activation API task returns `SUCCESS` immediately without issuing `install activate`
> to the device. Devices are never reloaded and remain in `IMG I` (Inactive) state.
> Only `schedule_validate: false` causes CatC to proceed through the full
> `install-activate` → reload → `install-commit` sequence.
> This behaviour was confirmed via live SDK log analysis (`catc-swim.log`) on CatC 2.3.7.6.

> **Module reference:**
> [`swim_workflow_manager` — `image_activation_details` examples](https://galaxy.ansible.com/ui/repo/published/cisco/catalystcenter/content/module/swim_workflow_manager/?keywords=swim#examples)

#### IOS-XE install-mode three-step sequence

Catalyst Center drives the activation as three sequential CLI operations on each device,
as documented in the
[Catalyst Center 2.3.7 User Guide — View image update workflow](https://www.cisco.com/c/en/us/td/docs/cloud-systems-management/network-automation-and-management/catalyst-center/2-3-7/user_guide/b_cisco_catalyst_center_user_guide_237/b_cisco_dna_center_ug_2_3_7_chapter_0100.html):

> *"For Cisco Catalyst 9000 Series Switches running on IOS-XE software, the software image is
> upgraded in three steps: `install-add` (Distribution), `install-activate` (Activation), and
> `install-commit` (Activation)."*
>
> *"If the device is in Inactive state, the `install-add` command is executed first.
> Subsequently, the `install-activate` and `install-commit` commands are executed."*

| CLI step | Phase | Device state after | Reboots? |
|---|---|---|---|
| `install add` | **Distribute** (phase 20) | `IMG I <new-version>` — Inactive | No |
| `install activate` | **Activate** (phase 30) | `IMG U <new-version>` — Activated & Uncommitted | **Yes** |
| `install commit` | **Activate** (phase 30, post-reload) | `IMG C <new-version>` — Activated & Committed | No |

> **Important for `cat9kv` (virtual switches):** In some virtual/simulated environments,
> Catalyst Center's activate task may report `SUCCESS` after submitting the `install-activate`
> API call, before confirming that the device has actually reloaded. If `show install summary`
> shows `IMG I` (Inactive) after the playbook completes with no errors, the `install-activate`
> step did not trigger the reload. Manually run:
>
> ```
> switch# install activate version <new-version>
> switch# install commit
> ```
>
> on each affected device, then proceed to phase 40.

### 8.5 `40_postcheck.yml` — post-activation compliance

**Purpose:** confirm the upgrade achieved the golden state.

Derives the same site list from `golden_tag_images`, runs an `IMAGE` compliance check per site, and
asserts the workflow executed successfully. The *after* snapshot to compare against `00`'s baseline.

### 8.6 `35_rollback.yml` — return to prior-stable (reloads devices)

**Purpose:** recover from a bad upgrade by activating the previously known-good image.

> **Module reference:**
> [`swim_workflow_manager` — rollback (`activate_lower_image_version: true`) examples](https://galaxy.ansible.com/ui/repo/published/cisco/catalystcenter/content/module/swim_workflow_manager/?keywords=swim#examples)

Guarded by **two explicit confirmation gates** — the play refuses to run without both:

```bash
-e rollback_confirm=YES -e rollback_reload_ack=RELOAD_OK
```

1. **Re-tag** the prior-stable image golden (`rollback_images.tag`).
2. **Activate** the prior-stable image (`rollback_images.activate`) with
   `activate_lower_image_version: true` — required because the rollback image's version is *lower*
   than the currently running upgrade. Reboots devices.

---

## 9. Run sequence

Standard upgrade, end to end:

```bash
ansible-playbook playbooks/00_preflight.yml      --ask-vault-pass   # resync + baseline compliance
ansible-playbook playbooks/10_import_and_tag.yml --ask-vault-pass   # import + golden tag
ansible-playbook playbooks/20_distribute.yml     --ask-vault-pass   # stage binary (no reload)
ansible-playbook playbooks/30_activate.yml       --ask-vault-pass   # activate (RELOADS devices)
ansible-playbook playbooks/40_postcheck.yml      --ask-vault-pass   # post-activation compliance
```

Rollback (double confirmation, reboots devices):

```bash
ansible-playbook playbooks/35_rollback.yml \
  -e rollback_confirm=YES \
  -e rollback_reload_ack=RELOAD_OK \
  --ask-vault-pass
```

> Substitute `--vault-password-file .vault_pass` for `--ask-vault-pass` for non-interactive runs.
> Run `20` during business hours; gate `30` and `35` behind a maintenance window.

---

## 10. Evidence and logging

- **SDK / module log:** `logs/catc-swim.log` (appended; level `INFO`).
- **Per-phase JSON evidence:** every playbook writes a timestamped artifact, e.g.
  `logs/<run_id>-00_preflight.json`, `-10_import_and_tag.json`, `-20_distribute.json`,
  `-30_activate.json`, `-40_postcheck.json`, `-35_rollback.json`. Each captures the full module
  result (registered output) for audit and post-incident review.

---

## 11. Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Import fails / image never appears | File-server URL wrong, or CatC can't reach it | Verify the exact URL from CatC's perspective (see [Appendix A.5](#a5-verify)); confirm `application/octet-stream`. |
| Golden tag "succeeds" but image absent in UI device-family view | THROTTLE/engineering builds have empty `applicableDevicesForImage` | Expected for unverifiable builds — the tag is set via API; the device-family view shows the *running* image only. |
| Distribute reports "no eligible devices" | Used the **golden-tag identifier** as `device_family_name` | Use the **inventory** family (`Switches and Hubs`) + series, not the SWIM identifier. |
| Activation times out | Reload exceeds default timeout | Confirm the phase uses the extended `catalystcenter_api_task_timeout: 7200`. |
| Compliance check skips devices | Devices unreachable or not fully managed | Re-run `00_preflight.yml` to resync; inspect `skipped_devices` in the evidence JSON. |
| `catalystcentersdk` import error | Python < 3.12 | Rebuild the virtualenv with Python 3.12+. |

---

## Appendix B: Alternative approach — individual API modules (no Workflow Manager)

The playbooks in this repository use `swim_workflow_manager` because it is the recommended,
declarative path. However, the `cisco.catalystcenter` collection also ships lower-level,
**individual API modules** — thin wrappers around single REST endpoints that expose every parameter
explicitly. Understanding these modules deepens your knowledge of what the Workflow Manager
actually orchestrates under the hood, and is essential if you need fine-grained control (e.g.
per-device targeting, custom scheduling, or integration with an external ITSM workflow).

This appendix describes how to rebuild the same pipeline using individual modules while keeping
**the same `settings.json` `swim` data model** as the source of truth.

---

### B.1 Module families at a glance

The collection ships two generations of individual SWIM modules:

| Generation | Module pattern | API surface | Status |
|---|---|---|---|
| **Legacy (v1 API)** | `swim_import_via_url`, `swim_trigger_distribution`, `swim_trigger_activation`, `golden_image_create` | `/dna/intent/api/v1/...` | Available; works on 2.3.7.x |
| **Modern (v2 API)** | `images_download`, `images_id_sites_site_id_tag_golden`, `network_device_images_id_distribute`, `network_device_images_id_activate` | `/dna/intent/api/v1/images/...` | Newer endpoint; added in CatC 2.3.7+ |

Both generations require you to **manage ID resolution and task polling yourself** — what
`swim_workflow_manager` absorbs internally you must now write explicitly.

---

### B.2 The additional orchestration burden

With individual modules, every step that the Workflow Manager handles automatically becomes a
task you own:

| Responsibility | Workflow Manager | Individual modules |
|---|---|---|
| Look up `imageId` UUID from image name | ✅ Resolved internally | ❌ Must query `images_info` or `swim_image_details_info` |
| Look up `siteId`, `deviceFamilyIdentifier` | ✅ Resolved internally | ❌ Must query site and family APIs |
| Look up device UUIDs from site / family / series | ✅ Resolved internally | ❌ Must query `network_device_by_ip_info` or `intent_network_devices_query` |
| Submit async task and poll until complete | ✅ Built-in (`catalystcenter_api_task_timeout`) | ❌ Must loop on `task_info` until `endTime` or `isError` |
| Verify state after apply | ✅ `config_verify: true` | ❌ Must re-query and assert manually |
| Idempotency (skip if already done) | ✅ Handled by module | ❌ Must guard with `when:` checks on info-module results |

---

### B.3 Sequence diagram — individual modules

The diagram below maps each pipeline phase to the exact individual module(s) required, including
the lookup and polling steps that the Workflow Manager hides.

![Individual modules sequence diagram](images/appendix-b-individual-modules-sequence.png)

> Diagram source: [`images/appendix-b-individual-modules-sequence.mmd`](images/appendix-b-individual-modules-sequence.mmd)
> — edit the `.mmd` file and re-run `mmdc` to update the PNG (see [Regenerating diagrams](#regenerating-diagrams)).

---

### B.4 Phase-by-phase module reference

#### Phase 00 — Preflight

| Step | Module | Key parameters | Notes |
|---|---|---|---|
| Force device resync | `cisco.catalystcenter.network_devices_resync_interval_settings_override` | `id` (device UUID) | No direct `site_name` input — must resolve device UUIDs from site first using `network_device_by_ip_info` or `intent_network_devices_query` |
| Poll resync task | `cisco.catalystcenter.task_info` | `task_id` | Loop with `until: result.dnacResponse.endTime is defined` |
| Trigger IMAGE compliance | `cisco.catalystcenter.compliance_device` | `deviceUuids: [...]`, `complianceType: IMAGE` | Takes a list of device UUIDs — requires lookup first |
| Poll compliance task | `cisco.catalystcenter.task_info` | `task_id` | |
| Retrieve results | `cisco.catalystcenter.compliance_device_details_info` | `deviceUuid`, `complianceType: IMAGE` | Parse `status` field per device |

#### Phase 10 — Import + golden tag

| Step | Module | Key parameters | Notes |
|---|---|---|---|
| Import image from URL | `cisco.catalystcenter.swim_import_via_url` | `payload: [{sourceURL, urlType: GITHUB/HTTP}]` | `sourceURL` from `import_images[].import_image_details.url_path` |
| Poll import task | `cisco.catalystcenter.task_info` | `task_id` | Import can take several minutes |
| Resolve `imageId` by name | `cisco.catalystcenter.swim_image_details_info` | `name: "{{ image_name }}"` | Returns UUID needed for golden-tag call |
| Resolve `siteId` | `cisco.catalystcenter.sites_info` or `site_by_name_info` | `name: "{{ site_name }}"` | Returns `siteId` UUID |
| Apply golden tag | `cisco.catalystcenter.golden_image_create` | `imageId`, `siteId`, `deviceFamilyIdentifier`, `deviceRole` | `deviceFamilyIdentifier` = `999999901` for cat9kv; `deviceRole: ALL` |

> **Alternative (v2 API):** `images_id_sites_site_id_tag_golden` — takes `id` (imageId) and
> `siteId` path parameters directly, no `deviceFamilyIdentifier` needed at this layer.

#### Phase 20 — Distribute

| Step | Module | Key parameters | Notes |
|---|---|---|---|
| Resolve `imageId` | `cisco.catalystcenter.swim_image_details_info` | `name: "{{ image_name }}"` | |
| Resolve device UUIDs by site/family/series | `cisco.catalystcenter.intent_network_devices_query` | `siteHierarchy`, `family`, `series` | Returns list of device UUIDs to loop over |
| Trigger distribution (legacy) | `cisco.catalystcenter.swim_trigger_distribution` | `payload: [{deviceUuid, imageUuid}]` | Accepts a list — can bulk-submit all 6 devices in one call |
| — or — trigger distribution (modern) | `cisco.catalystcenter.network_device_images_id_distribute` | `id` (deviceId), `distributedImages: [imageId]` | One call per device — loop required |
| Poll distribution task | `cisco.catalystcenter.task_info` | `task_id` | Poll `GET /dna/intent/api/v1/networkDeviceImageUpdates?parentId={taskId}` via `network_device_image_updates_info` for per-device status |

#### Phase 30 — Activate

| Step | Module | Key parameters | Notes |
|---|---|---|---|
| Resolve `imageId` | `cisco.catalystcenter.swim_image_details_info` | `name: "{{ image_name }}"` | |
| Resolve device UUIDs | `cisco.catalystcenter.intent_network_devices_query` | `siteHierarchy`, `family`, `series` | |
| Pre-activation readiness check | `cisco.catalystcenter.network_device_images_id_readiness_checks` | `id` (deviceId), `imageId` | New v2 API — checks flash, NTP, reachability before activating |
| Trigger activation (legacy) | `cisco.catalystcenter.swim_trigger_activation` | `payload: [{deviceUuid, imageUuidList, activateLowerImageVersion: false}]` | Reboots devices |
| — or — trigger activation (modern) | `cisco.catalystcenter.network_device_images_id_activate` | `id` (deviceId), `installedImages: [imageId]` | Combines distribute+activate in one call if needed |
| Poll activation task | `cisco.catalystcenter.task_info` | `task_id` | Extend poll timeout ≥ 7200 s; devices are offline during reload |

#### Phase 40 — Postcheck

Same as Phase 00 compliance steps — `compliance_device` + `task_info` + `compliance_device_details_info`. Assert `status == "COMPLIANT"` for all device UUIDs.

---

### B.5 Mapping `swim_details` keys to individual-module parameters

The synthesised `swim_details` keys (see [§7.1](#71-how-swim_details-is-synthesised)) map to
individual-module parameters as follows — allowing you to reuse the same data model with minimal
Jinja2 transformation:

| `swim_details` key | Field | Maps to individual-module parameter |
|---|---|---|
| `import_images[].import_image_details` | `url_path` | `swim_import_via_url` → `payload[].sourceURL` |
| `golden_tag_images[].tagging_details` | `site_name` | → resolve `siteId` via `sites_info` |
| | `device_image_family_name` | → `deviceFamilyIdentifier` in `golden_image_create` (resolve via family-identifier API or hardcode `999999901`) |
| | `device_role` | → `deviceRole` in `golden_image_create` |
| `distribute_images[].image_distribution_details` | `image_name` | → resolve `imageId` via `swim_image_details_info` |
| | `site_name` + `device_family_name` + `device_series_name` | → resolve `deviceId` list via `intent_network_devices_query` |
| `activate_images[].image_activation_details` | `activate_lower_image_version` | → `swim_trigger_activation` payload `activateLowerImageVersion` |
| | `distribute_if_needed` | → only applicable in `network_device_images_id_activate` (`installedImages` combines both) |

---

### B.6 Why this repository uses Workflow Manager instead

| Consideration | Individual modules | `swim_workflow_manager` |
|---|---|---|
| Lines of playbook code | ~150–200 per phase (lookups + polling loops + guards) | ~30 per phase |
| ID resolution | Manual (3–5 extra tasks per phase) | Automatic |
| Task polling | Manual `until:` loop on `task_info` | Built-in |
| Idempotency | Manual `when:` guards on info-module output | Built-in |
| Readability | Low — imperative, stateful | High — declarative config blocks |
| Debuggability | High — every API call visible | Medium — single module call |
| Appropriate when | Fine-grained per-device logic, ITSM integration, custom scheduling | Standard bulk-site upgrade pipeline |

> **Bottom line:** reach for individual modules when you need per-device branching logic,
> dynamic scheduling decisions, or integration with an external state machine. For the standard
> "upgrade this site to this image" use case, `swim_workflow_manager` is always the right choice.

---

### Regenerating diagrams

All Mermaid diagram sources live in [`images/`](images/) as `.mmd` files alongside their rendered
PNGs. Regenerate after any logic or sequence change:

```bash
# Re-render and resize (enforces GitHub 4000 px / 1.2 MB limits)
mmdc -i images/appendix-b-individual-modules-sequence.mmd \
     -o images/appendix-b-individual-modules-sequence.png --scale 3
/usr/bin/sips -Z 4000 images/appendix-b-individual-modules-sequence.png \
              --out images/appendix-b-individual-modules-sequence.png

# Verify dimensions and file size
/usr/bin/sips -g pixelWidth -g pixelHeight images/appendix-b-individual-modules-sequence.png
ls -lh images/appendix-b-individual-modules-sequence.png
```

Commit both the `.mmd` source and the regenerated `.png` together.

---

## Appendix A: Image distribution (HTTP) server setup

The `swim` block in `settings.json` sets `image_server_base_url`, so imports use `type: remote` and
**Catalyst Center itself** pulls the `.bin` image over HTTP from the Ubuntu host `198.18.134.28`.
The URL must resolve exactly to:

```
http://198.18.134.28/images/cat9kv-universalk9.BLD_V262_THROTTLE_LATEST_20260529_003538.SSA.bin
```

The image must live in an `/images/` web-root directory. The steps below use **nginx**;
Apache or a quick `python3 -m http.server` work too.

### A.1 Install nginx (on 198.18.134.28)

```bash
sudo apt update
sudo apt install -y nginx
systemctl status nginx --no-pager
```

### A.2 Create the image directory and stage the file

```bash
sudo mkdir -p /var/www/html/images
# upload from your workstation:
#   scp cat9kv-universalk9.<release>.SSA.bin user@198.18.134.28:/tmp/
sudo mv /tmp/cat9kv-universalk9.BLD_V262_THROTTLE_LATEST_20260529_003538.SSA.bin \
        /var/www/html/images/
sudo chown -R www-data:www-data /var/www/html/images
sudo chmod 0755 /var/www/html/images
sudo chmod 0644 /var/www/html/images/*.bin
```

### A.3 (Optional) Dedicated server block with directory browsing

```bash
sudo tee /etc/nginx/sites-available/swim-images >/dev/null <<'CONF'
server {
    listen 80 default_server;
    server_name 198.18.134.28;
    root /var/www/html;

    location /images/ {
        autoindex on;
        sendfile on;
        default_type application/octet-stream;
    }
}
CONF
sudo ln -sf /etc/nginx/sites-available/swim-images /etc/nginx/sites-enabled/swim-images
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### A.4 Open the firewall (if ufw is active)

```bash
sudo ufw status
sudo ufw allow 80/tcp   # only if ufw is active
```

### A.5 Verify

```bash
# on the file server:
curl -I http://localhost/images/cat9kv-universalk9.BLD_V262_THROTTLE_LATEST_20260529_003538.SSA.bin

# from the Catalyst Center side (the route that actually matters):
curl -I http://198.18.134.28/images/cat9kv-universalk9.BLD_V262_THROTTLE_LATEST_20260529_003538.SSA.bin
```

Both must return `HTTP/1.1 200 OK` with a `Content-Length` matching the file size.

> **Gotchas**
> - The URL path must match the `swim` block's `image_server_base_url` + image filename exactly — wrong subdir or trailing slash fails the import.
> - Serve as `application/octet-stream` so the `.bin` downloads instead of rendering.
> - Use anonymous HTTP (no basic-auth) — CatC remote import expects an unauthenticated URL.
> - Reachability that matters is **CatC → 198.18.134.28:80**, not your workstation; verify with the second `curl`.
> - Confirm integrity after copy: `md5sum /var/www/html/images/*.bin`.
