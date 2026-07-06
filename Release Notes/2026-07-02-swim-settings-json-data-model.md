# Release Note — 2026-07-02

## SWIM — Centralize image details into the `settings.json` data model

### Summary

The 6.0 SWIM pipeline previously sourced all image intent from a standalone
`vars/images.yml` file that duplicated image filenames, device family/series names, the
file-server URL, and hardcoded the target `site_name`. Those details now live in the
**central data model** (`CICD Pipeline/Settings/settings.json`) — the same file consumed
by stages 1.0 (site hierarchy), 4.0 (discovery) and 9.0 (provisioning) — under a new
per-project `swim` block. Each fact is declared once; the target `site_name` is derived
from the existing `HierarchyParent/Area/Bldg/Floor` fields instead of being hardcoded.

A new task file, `tasks/load_swim_details.yml`, synthesises the exact `swim_details`
structure the playbooks already loop over, so every `loop:` in the six playbooks is
unchanged — only the *source* of `swim_details` changed.

### Root cause / motivation

- `vars/images.yml` repeated the same facts across five sections (image name ×5, site_name
  ×5, device family/series ×3, family identifier ×2, base URL ×N), inviting drift.
- `site_name` was hardcoded (`Global/PODS/POD 0/Building P0/Floor 1`) rather than derived
  from the hierarchy that stages 1.0/9.0 already own, so a hierarchy change silently broke
  SWIM targeting.
- No single source of truth linked the image-server base URL to the rest of the pipeline.

### What changed

| Area | Before | After |
|------|--------|-------|
| Image source of truth | `vars/images.yml` (`swim_details`) | `settings.json` `project[].swim` block |
| `site_name` | Hardcoded string in each section | Derived from `HierarchyParent/Area/Bldg/Floor` |
| Image URLs | Full URLs typed per image | `image_server_base_url` + filename |
| Duplication | Facts repeated across 5 sections | Declared once, synthesised at run time |
| Playbook loading | `vars_files: [../vars/images.yml]` | `import_tasks: ../tasks/load_swim_details.yml` |
| Multi-site | One hardcoded site | Every `project` entry with a `swim` block upgrades its own site |

### Files added

> **Note (2026-07):** Numbered stage directories (`1.0`–`11.0`) were removed; paths below are historical. Current code lives under `CICD Pipeline/ansible/roles/swim/` and `playbooks/06_swim_*.yml`.

- `CICD Pipeline/ansible/roles/swim/tasks/load_swim_details.yml`
  - Resolves `settings_json_path`, loads and validates `settings.json`, derives `site_name`
    from the hierarchy fields, and synthesises `swim_details` (`import_images`,
    `golden_tag_images`, `distribute_images`, `activate_images`, `rollback_images.{tag,activate}`).

### Files changed

- `CICD Pipeline/Settings/settings.json`
  - Added a `swim` block to the project entry: `image_server_base_url`,
    `device_family_identifier`, `device_family_name`, `device_series_name`, `device_role`,
    `upgrade_image`, `rollback_image`, and an `activation` sub-block.
- `CICD Pipeline/ansible/inventory/group_vars/catalyst_center/connection.yml`
  - Added `settings_json_path: "../../Settings/settings.json"`.
- `CICD Pipeline/ansible/playbooks/06_swim_{preflight,import_and_tag,distribute,activate,rollback,postcheck}.yml`
  - Removed `vars_files: [../vars/images.yml]`; added
    `import_tasks: ../tasks/load_swim_details.yml` as the first task.
- `CICD Pipeline/ansible/README.md`
  - Rewrote §7 to describe the `swim` block and the synthesis task; updated the TOC,
    repository layout, connection-params table, and Appendix A/B references.

### Files removed

- Removed standalone `vars/images.yml` — image paths are in `settings.json` `swim` section and `inventory/group_vars/image_servers/vars.yml`
  - No longer consumed; superseded by the `swim` block in `settings.json`.

### Validation evidence

- `ansible-playbook --syntax-check` passes for all six SWIM playbooks.
- `ansible-lint tasks/load_swim_details.yml playbooks/` — **0 failures** at the `production`
  profile.
- Offline render test asserted the synthesised `swim_details` is byte-for-byte equivalent to
  the retired `images.yml`: two `import_images` (upgrade + rollback), one each of
  `golden_tag_images`/`distribute_images`/`activate_images`, and `rollback_images.{tag,activate}`
  with `site_name = "Global/PODS/POD 0/Building P0/Floor 1"` derived from the hierarchy fields,
  and the correct image URL under `http://198.18.134.28/images/`.

### Operational impact

- To change images, versions, family names, or the file-server URL, edit the `swim` block in
  `settings.json` — do not edit the playbooks.
- Adding a new SWIM site is now a matter of adding a `project` entry (with its `Hierarchy*`
  fields and a `swim` block); the synthesis and derived compliance-site list pick it up
  automatically.
- The image-server base URL in `settings.json` (`image_server_base_url`) should match the host
  provisioned by `CICD Pipeline/ansible/playbooks/deploy_http_image_server.yml` (role: `http_image_server`).
