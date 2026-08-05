# 2026-08-05 — Playbook annotation standard

## What changed

All 19 playbooks in `CICD Pipeline/ansible/playbooks/` now carry a standardized
boxed header comment documenting purpose, the **exact** data each stage sources,
and the **exact** data each stage produces.

The style matches the annotation already used across the role task files (see
`roles/swim/tasks/import_and_tag.yml` and `roles/swim/tasks/load_swim_details.yml`).

## Motivation

Playbooks were the least-documented layer of the pipeline: 16 of 19 had no
header at all, and 3 had ad-hoc prose. Roles were already ~90% annotated, so a
reader could understand *how* a role worked but not *what* fed it or *what* it
left behind. The renumbering in
[`2026-08-05-playbook-renumbering.md`](2026-08-05-playbook-renumbering.md) made
this worse — stage numbers in comments no longer matched filenames.

## Header format

```yaml
---
# =============================================================================
# <filename>  —  Pipeline stage <NN>
# =============================================================================
# Purpose — what the stage does and why it exists.
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

Conventions:

| Rule | Applies to |
|---|---|
| `Sourced:` / `Produced:` name real variables and nested key paths with example values | all |
| `*DISRUPTIVE*` on the title line | `06.4_swim_activate.yml`, `06.6_swim_rollback.yml` |
| `# ── Play N: … ──` divider above each play | `11_backup_lab_configs.yml` |
| `Depends on:` lists prerequisite stages | stages 02–11 |
| `Run:` shows the canonical invocation plus common overrides | all |

## Affected files

### Playbooks (all annotated)

| File | Notes |
|---|---|
| `00_site_deploy.yml` | Documents the 01→10 import chain and why 06.x/11 are excluded |
| `01_site_hierarchy.yml` | `site_data`, `site_type_map`, `building_info_map`, `floor_info_map`, `all_site_paths`, `site_id_map` |
| `02_network_settings.yml` | Notes the raw `PUT /dna/intent/api/v1/network/{siteId}` workaround for NCND01243 |
| `03_credentials.yml` | Documents the three phases (CLI/SNMP WFM, NETCONF raw REST, NETCONF delete) and the `catc_*` → `dnac_*` param mapping |
| `04_device_discovery.yml` | `discovery_list` shape; credentials referenced by description only |
| `05_assign_to_site.yml` | `site_device_map` |
| `06.0_swim_deploy_http_image_server.yml` | Header normalized; documents `image_local_paths`, rsync-resume tuning, ufw |
| `06.1_swim_preflight.yml` | `swim_target_sites`, evidence `-00_preflight.json`, `swim_run_id` explained |
| `06.2_swim_import_and_tag.yml` | `import_images`, `golden_tag_images`, evidence `-10_import_and_tag.json` |
| `06.3_swim_distribute.yml` | `distribute_images`, evidence `-20_distribute.json` |
| `06.4_swim_activate.yml` | Marked `*DISRUPTIVE*`; `activation.*` keys; evidence `-30_activate.json` |
| `06.5_swim_postcheck.yml` | `swim_compliance_sites`, evidence `-40_postcheck.json` |
| `06.6_swim_rollback.yml` | Marked `*DISRUPTIVE*`; documents both confirmation gates; evidence `-35_rollback.json` |
| `07_template_sync.yml` | Notes that inputs come from inventory vars, **not** settings.json |
| `08_network_profile.yml` | `profile_list` shape (PascalCase JSON → WFM string lists) |
| `09_provision_devices.yml` | Explains why there is no `module_defaults` (raw REST + `_catc_token`) |
| `10_deploy_composite.yml` | `_deploy_entries` shape; `DeployTemplate` / `TemplateTarget` semantics |
| `11_backup_lab_configs.yml` | Per-play dividers; tag∩platform scoping; retention behavior |
| `deploy_yangsuite.yml` | Header normalized to the standard shape |

### Role task files (17 partial headers raised to full standard)

These had a banner and/or a one-line description but no `Pre:` / `Post:` data
contract. Each now documents the exact facts it consumes and produces, and the
non-obvious reason it exists.

| File | Contract now documented |
|---|---|
| `deploy_composite/deploy_entry.yml` | `deploy_entry` loop var → `_template_version_map`, `_composite_template_id`/`_main_id`, `_member_templates`, `_device_uuid_map`, `_target_info`, `_member_deployment_info`, `_deploy_task_ids`, `_deployment_status_ids`, `_summary_lines`; steps A–G |
| `template_sync/process-subfolder.yml` | `subfolder_item` + `repo_tree_response` → `api_template_files`, `api_composite_files`, `projectName`, `enriched_*`, `sorted_template_files`, `sync_summary`; project-name resolution order |
| `template_sync/process-template.yml` | `template_file` → `template_content`, appended `template_workflow_configs[]`; `TEMPLATE_PROJECT_NAME` substitution |
| `template_sync/process-composite.yml` | `composite_file` → `composite_name`, `containing_templates_list`, appended `composite_workflow_configs[]` |
| `http_image_server/preflight.yml` | `image_local_paths` → `local_images.results[]`; why the example placeholder path is rejected |
| `http_image_server/install_nginx.yml` | `image_dir` → nginx installed, web root as `www-data:www-data 0755` |
| `http_image_server/stage_images.yml` | `local_images` → `remote_images`, `image_plan[{path, filename, local_exists, remote_exists}]`, `rsync_upload` |
| `http_image_server/configure_nginx.yml` | server block paths written; why the default site is removed |
| `http_image_server/configure_firewall.yml` | `manage_ufw` → `ufw_bin`, `ufw_status`; skipped when ufw absent/inactive |
| `http_image_server/verify.yml` | `image_plan` → `http_check`, `http_check_remote`; why both local and remote checks exist, and why `application/octet-stream` is asserted |
| `yangsuite_docker/preflight.yml` | the three fail-fast assertions and the failure each prevents |
| `yangsuite_docker/install_docker.yml` | `yangsuite_docker_cli_check.rc`, `yangsuite_docker_compose_check.rc`; why containerd is separate |
| `yangsuite_docker/clone_repository.yml` | `yangsuite_repo_stat`, `yangsuite_git.changed`; why re-clone is skipped by default |
| `yangsuite_docker/configure_env_and_certs.yml` | `yangsuite_cert_stats` → `setup.env` (0600), self-signed cert/key |
| `yangsuite_docker/patch_compose_ports.yml` | port vars → in-place compose edit; why an override file is **not** used (compose merges port lists) |
| `yangsuite_docker/deploy_compose.yml` | `yangsuite_compose_up`; why `changed` is derived from stdout verbs, not `rc` |
| `yangsuite_docker/configure_firewall.yml` | computed port list incl. gNMI/gRPC MDT extras → ufw allow rules |
| `yangsuite_docker/verify.yml` | `yangsuite_https_local`, `yangsuite_https_remote`; retry budgets and why both sides are checked |

### Role task files (stage labels corrected)

Headers still referenced the pre-renumbering `Stage 6.0` label:

| File | Before | After |
|---|---|---|
| `roles/swim/tasks/preflight.yml` | `Stage 6.0 (manual lifecycle)` | `Stage 06.1: pre-upgrade baseline` |
| `roles/swim/tasks/distribute.yml` | `Stage 6.0: push image …` | `Stage 06.3: push image …` |
| `roles/swim/tasks/activate.yml` | `Stage 6.0: activate golden image …` | `Stage 06.4: activate golden image …` |
| `roles/swim/tasks/postcheck.yml` | `Stage 6.0: post-activation …` | `Stage 06.5: post-activation …` |
| `roles/swim/tasks/rollback.yml` | `Stage 6.0: emergency rollback …` | `Stage 06.6: emergency rollback …` |

### Documentation

- `CICD Pipeline/ansible/README.md` — new **Playbook annotation convention**
  section under *Pipeline Order*, defining the header template and its rules.

## Validation

```bash
cd "CICD Pipeline/ansible"
for p in playbooks/*.yml; do ansible-playbook --syntax-check "$p"; done
python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('roles/*/tasks/*.yml')]"
```

All 19 playbooks pass syntax check and all 55 role task files parse cleanly.
Comment-only changes — no task, variable, or module behavior was modified.

## Coverage

| Layer | Before | After |
|---|---|---|
| Playbooks | 0 FULL / 3 PARTIAL / 16 NONE | **19 FULL** |
| Role task files | 38 FULL / 17 PARTIAL / 0 NONE | **55 FULL** |

## Operational impact

None at runtime. Reading impact only: each stage and each role task file is now
self-describing, so onboarding no longer requires tracing into the task bodies
to learn what is consumed and produced.

## Known follow-ups

- **SWIM evidence filenames still use the pre-renumbering prefixes** —
  `-00_preflight.json`, `-10_import_and_tag.json`, `-20_distribute.json`,
  `-30_activate.json`, `-35_rollback.json`, `-40_postcheck.json`. These are
  documented as-is in the new headers. Renaming them to `06.N_…` would change
  emitted artifact names and any downstream log tooling, so it is deliberately
  deferred.
- `defaults/` and `handlers/` files (5) remain unannotated. They are flat data
  and hook declarations, so the boxed contract format adds little there.
