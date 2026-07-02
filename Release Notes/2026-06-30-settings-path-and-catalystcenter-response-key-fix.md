# Release Note — 2026-06-30

## CICD Pipeline: settings.json relocation, missing `catc_host`, and `catalystcenter_response` key fixes

### Summary

Three related changes were made to the Catalyst Center CICD Pipeline playbooks:

1. **`settings.json` relocated** into the pipeline at `CICD Pipeline/Settings/settings.json`.
   All playbook inventories and docs were repointed from the old external
   `../../../../Projects/BGP_EVPN/Settings/settings.json` path to the new in-pipeline
   relative path `../Settings/settings.json`.
2. **Playbook 1.0 had `catc_host` commented out**, causing an undefined-variable failure in
   `module_defaults`. It was restored to match every other playbook.
3. **The `cisco.catalystcenter` registered-response key was wrong** in playbooks 1.0 and 2.0.
   The code read `catalyst_response`, but the collection returns its data under
   `catalystcenter_response`. In 1.0 this produced an empty Global UUID and a hard
   `400 NCND00067` failure; in 2.0 it silently built an empty site map (masked by
   `| default([])`).

All three were validated live against Catalyst Center `198.18.129.100` (appliance 2.3.7.10,
SDK 2.3.7.9). Playbooks 1.0 and 2.0 now complete successfully.

### Root Cause

| # | Fault | Effect |
|---|-------|--------|
| 1 | `settings_json_path` default pointed to an external `Projects/BGP_EVPN/Settings/settings.json` tree that no longer holds the canonical file | Playbooks would read a stale/missing settings file after the move |
| 2 | `catc_host` was commented out (`#catc_host: ...`) in `1.0-.../inventory.yml` only | `module_defaults` referenced an undefined `catc_host`, failing every `cisco.catalystcenter` task at parse time |
| 3 | Playbooks read `catalyst_response.response`, but `cisco.catalystcenter.*` modules register results under `catalystcenter_response` (confirmed keys: `catalystcenter_response`, `dnac_response`, `result`, `status`) | 1.0: Global site UUID resolved to `""` → empty `parentId` → `400 NCND00067: request body invalid` on first area create. 2.0: site name-to-ID map came back empty (silenced by `| default([])`) |

### What Changed

| Area | Before | After |
|------|--------|-------|
| `settings_json_path` default (all playbooks) | `../../../../Projects/BGP_EVPN/Settings/settings.json` | `../Settings/settings.json` |
| 1.0 inventory `catc_host` | `#catc_host: 198.18.129.100` (commented) | `catc_host: 198.18.129.100` |
| 1.0 + 2.0 response key | `catalyst_response.response` | `catalystcenter_response.response` |

### Files Modified

**`settings_json_path` repointed to `../Settings/settings.json`:**

- `CICD Pipeline/1.0-Cisco-Catalyst-Center-Site-Hierarchy/inventory.yml`
- `CICD Pipeline/2.0-Cisco-Catalyst-Center-Settings/inventory.yml`
- `CICD Pipeline/3.0-Cisco-Catalyst-Center-Credentials/inventory.yml`
- `CICD Pipeline/4.0-Cisco-Catalyst-Center-Device-Discovery/inventory.yml`
- `CICD Pipeline/5.0-Cisco-Catalyst-Center-Assign-To-Site/inventory.yml`
- `CICD Pipeline/8.0-Cisco-Catalyst-Center-Network-Profile/inventory.yml`
- `CICD Pipeline/9.0-Cisco-Catalyst-Center-Provision-Devices/inventory.yml`
- `CICD Pipeline/10.0-Cisco-Catalyst-Center-Provision-Composite/inventory.yml`
- Matching READMEs for 1.0–5.0 and 8.0–10.0 (inventory snippets, variable tables,
  and the 7.0 `playbook_dir` resolution example). Alternate-project override examples
  in 3.0/4.0/5.0 were updated to the new `../Settings/<file>.json` convention.

> Playbooks 6.0 (templates GitHub sync) and 10.0 (config backup) do not consume
> `settings.json` and were not affected.

**`catc_host` restored:**

- `CICD Pipeline/1.0-Cisco-Catalyst-Center-Site-Hierarchy/inventory.yml`

**`catalyst_response` → `catalystcenter_response`:**

- `CICD Pipeline/1.0-Cisco-Catalyst-Center-Site-Hierarchy/site_hierarchy.yml`
- `CICD Pipeline/1.0-Cisco-Catalyst-Center-Site-Hierarchy/tasks/create_or_update_site.yml`
- `CICD Pipeline/2.0-Cisco-Catalyst-Center-Settings/network_settings.yml` (and corrected
  the misleading inline comment that claimed the key was `catalyst_response`)
- `CICD Pipeline/2.0-Cisco-Catalyst-Center-Settings/README.md`

> Playbooks 3.0–9.0 use the `cisco.dnac` collection, which correctly returns
> `dnac_response`; they were not affected by the key typo.

### Validation Evidence

- **1.0** — `PLAY RECAP: ok=37 changed=4 failed=0` → "Successfully provisioned 4 site(s)."
  (`Global/PODS`, `POD 0`, `Building P0`, `Floor 1`). The Global UUID now resolves to a
  real value and the first area create no longer returns `400 NCND00067`.
- **2.0** — Site name-to-ID map now populates with all four sites
  (e.g. `Global/PODS → bdb6fc0e-...`, `Global/PODS/POD 0/Building P0/Floor 1 → 5bb99d19-...`)
  instead of an empty `{}`, and the v1 network-settings payload list builds correctly.

### Operational Impact

- The pipeline is now self-contained: the canonical `settings.json` lives under
  `CICD Pipeline/Settings/` and resolves relative to each `playbook_dir`.
- Playbook 1.0 site-hierarchy provisioning and 2.0 network-settings application are
  functional again. No fabric/device behavior changed — these are control-plane
  automation fixes only.
