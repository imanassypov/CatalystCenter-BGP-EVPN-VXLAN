# 2026-08-05 — Playbook Renumbering for Execution-Order Discoverability

## What changed

The Ansible playbook collection under `CICD Pipeline/ansible/playbooks/` was renamed so that a
plain directory listing reflects the exact execution order. The SWIM stage previously spread its
six steps across an unnumbered utility playbook plus five `06_swim_*` files whose alphabetical
sort did **not** match the required run order.

| Old name | New name |
|---|---|
| `site.yml` | `00_site_deploy.yml` |
| `deploy_http_image_server.yml` | `06.0_swim_deploy_http_image_server.yml` |
| `06_swim_preflight.yml` | `06.1_swim_preflight.yml` |
| `06_swim_import_and_tag.yml` | `06.2_swim_import_and_tag.yml` |
| `06_swim_distribute.yml` | `06.3_swim_distribute.yml` |
| `06_swim_activate.yml` | `06.4_swim_activate.yml` |
| `06_swim_postcheck.yml` | `06.5_swim_postcheck.yml` |
| `06_swim_rollback.yml` | `06.6_swim_rollback.yml` |

`06.6_swim_rollback.yml` is numbered for visual consistency but is **not** part of the forward
sequence — it is an out-of-band recovery playbook run only on failure.

## Motivation

Alphabetical sort of the old names produced `activate → distribute → import_and_tag → postcheck
→ preflight`, the reverse of the correct order, and `deploy_http_image_server.yml` sorted at the
bottom of the directory despite being the mandatory first step. The `06.N` prefix makes `ls`
output authoritative and removes the need to consult the README to recall sequencing.

## Correct SWIM execution order

```bash
cd "CICD Pipeline/ansible"
ansible-playbook playbooks/06.0_swim_deploy_http_image_server.yml   # stage images on nginx
ansible-playbook playbooks/06.1_swim_preflight.yml                  # device readiness / flash
ansible-playbook playbooks/06.2_swim_import_and_tag.yml             # import to CatC, tag golden
ansible-playbook playbooks/06.3_swim_distribute.yml                 # push image to devices
ansible-playbook playbooks/06.4_swim_activate.yml                   # RELOADS DEVICES
ansible-playbook playbooks/06.5_swim_postcheck.yml                  # verify post-activation
```

Rollback (failure path only, guarded):

```bash
ansible-playbook playbooks/06.6_swim_rollback.yml -e rollback_confirm=YES -e rollback_reload_ack=RELOAD_OK
```

## Reference updates

| File | Change |
|---|---|
| `CICD Pipeline/ansible/playbooks/00_site_deploy.yml` | Header comment `06_swim_*` → `06.x_swim_*` |
| `CICD Pipeline/ansible/playbooks/06.0_swim_deploy_http_image_server.yml` | Two self-referencing `Run:` examples in the header |
| `CICD Pipeline/ansible/roles/http_image_server/tasks/main.yml` | `# Playbook:` pointer |
| `CICD Pipeline/ansible/roles/swim/tasks/main.yml` | Stub-entry comment `06_swim_*.yml` → `06.x_swim_*.yml` |
| `CICD Pipeline/ansible/roles/swim/tasks/import_and_tag.yml` | Prerequisite reference → "HTTP image server (stage 06.0)" |
| `CICD Pipeline/ansible/README.md` | Layout tree, orchestrator command, pipeline table (added stage 0 and rollback rows), SWIM order block, inventory "Loaded vs used" table, Common Overrides || `README.md` (root) | Stage table — added stage 0 row, rewrote stage 6 chain, updated supporting-directory link |
| `Release Notes/2026-07-02-readme-cicd-pipeline-expansion.md` | Added superseded annotation |
| `Release Notes/2026-07-02-swim-settings-json-data-model.md` | Updated historical-path annotation |

## Operational impact

Any external runner, cron entry, CI job, or shell history invoking the old filenames will fail
with `the playbook ... could not be found`. Update to the new paths. No change to playbook
content, role behaviour, variables, or rendered fabric configuration — the renames are
path-only.
