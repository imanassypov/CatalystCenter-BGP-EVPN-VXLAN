# 2026-07-02 — README §8.1 Expanded to Full CICD Pipeline

## What changed

Rewrote root [`README.md`](../README.md) **§8.1 "GitOps Workflow (Ansible)"** so it references the
complete, numbered collection of CICD playbooks instead of only the template GitOps stage (7.0).

- Added an ordered stage table (1.0 → 11.0) with folder links, primary playbook filename, and a
  one-line purpose for each stage.
- Documented supporting directories: `Settings/` (`settings.json` source-of-truth) and
  `utils/ansible-image-server-setup/` (HTTP image server for SWIM).
- Preserved the detailed Template GitOps (7.0) walkthrough as a nested subsection.

## Stage inventory (authoritative playbook filenames)

| Stage | Playbook |
|-------|----------|
| 1.0 Site Hierarchy | `site_hierarchy.yml` |
| 2.0 Settings | `network_settings.yml` |
| 3.0 Credentials | `credentials.yml` |
| 4.0 Device Discovery | `device_discovery.yml` |
| 5.0 Assign To Site | `assign_to_site.yml` |
| 6.0 SWIM | `playbooks/00_preflight.yml` → `10_import_and_tag.yml` → `20_distribute.yml` → `30_activate.yml` → `40_postcheck.yml` (rollback: `35_rollback.yml`) |
| 7.0 Templates (GitOps) | `ansible-git-catc.yml` |
| 8.0 Network Profile | `network_profile.yml` |
| 9.0 Provision Devices | `provision_devices.yml` |
| 10.0 Provision Composite | `deploy_composite_template.yml` |
| 11.0 Backup My Configs | `backup-lab-configs.yml` |

## Motivation

The CICD Pipeline directory had grown from a single template-sync project into a full end-to-end
provisioning sequence (empty Catalyst Center → site hierarchy → settings → credentials → discovery →
site assignment → SWIM → templates → network profile → device provisioning → composite deploy →
config backup). §8.1 previously described only stage 7.0, understating the automation scope.

## Operational impact

Documentation only. No template, playbook, or provisioning behavior changed.
