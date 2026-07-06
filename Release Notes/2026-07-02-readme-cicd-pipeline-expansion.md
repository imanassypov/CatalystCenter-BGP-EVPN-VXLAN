# 2026-07-02 — README §8.1 Expanded to Full CICD Pipeline

## What changed

Rewrote root [`README.md`](../README.md) **§8.1 "GitOps Workflow (Ansible)"** so it references the
complete, numbered collection of CICD playbooks instead of only the template GitOps stage (7.0).

- Added an ordered stage table (1.0 → 11.0) with folder links, primary playbook filename, and a
  one-line purpose for each stage.
- Documented supporting directories: `Settings/` (`settings.json` source-of-truth) and
  `ansible/playbooks/deploy_http_image_server.yml` (HTTP image server for SWIM).
- Preserved the detailed Template GitOps (7.0) walkthrough as a nested subsection.

## Stage inventory (authoritative playbook filenames)

> **Superseded (2026-07):** Per-stage playbooks were consolidated under `CICD Pipeline/ansible/playbooks/`. The table below reflects the layout at the time of this note.

| Stage | Playbook |
|-------|----------|
| 1.0 Site Hierarchy | `playbooks/01_site_hierarchy.yml` |
| 2.0 Settings | `playbooks/02_network_settings.yml` |
| 3.0 Credentials | `playbooks/03_credentials.yml` |
| 4.0 Device Discovery | `playbooks/04_device_discovery.yml` |
| 5.0 Assign To Site | `playbooks/05_assign_to_site.yml` |
| 6.0 SWIM | `06_swim_preflight.yml` → `06_swim_import_and_tag.yml` → `06_swim_distribute.yml` → `06_swim_activate.yml` → `06_swim_postcheck.yml` (rollback: `06_swim_rollback.yml`) |
| 7.0 Templates (GitOps) | `playbooks/07_template_sync.yml` |
| 8.0 Network Profile | `playbooks/08_network_profile.yml` |
| 9.0 Provision Devices | `playbooks/09_provision_devices.yml` |
| 10.0 Provision Composite | `playbooks/10_deploy_composite.yml` |
| 11.0 Backup My Configs | `playbooks/11_backup_lab_configs.yml` |

## Motivation

The CICD Pipeline directory had grown from a single template-sync project into a full end-to-end
provisioning sequence (empty Catalyst Center → site hierarchy → settings → credentials → discovery →
site assignment → SWIM → templates → network profile → device provisioning → composite deploy →
config backup). §8.1 previously described only stage 7.0, understating the automation scope.

## Operational impact

Documentation only. No template, playbook, or provisioning behavior changed.
