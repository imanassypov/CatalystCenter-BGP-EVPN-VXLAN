# 2026-08-05 — In/Out payload examples on every data-manipulation task

## What changed

Every Ansible task in `CICD Pipeline/ansible/` that transforms data — `set_fact`,
`json_query`, namespace accumulator loops, REST payload assembly — now carries an
`Example` comment block directly above it showing the **exact payload going in**
and the **exact payload coming out**, followed by a short note on what the filters
actually did.

This extends the boxed-header annotation standard introduced in
[`2026-08-05-playbook-annotation-standard.md`](2026-08-05-playbook-annotation-standard.md)
from the file level down to the individual task level.

## Motivation

The boxed headers explain *what a stage does*. They do not explain *how a specific
Jinja expression reshapes the data*. Several of the transformations in this pipeline
are non-obvious:

- `settings.json` uses `snake_case`; the Catalyst Center REST API expects `camelCase`,
  and `null` values must be **omitted entirely** rather than sent as `null` (NCND01243).
- `select('mapping')` in the SWIM pre-flight walk exists solely to drop result rows
  whose `msg` is a plain error string instead of a dict.
- `selectattr('nameHierarchy','defined')` in `build_site_id_map.yml` exists because
  the `Global` root site is the one row in the API response with no `nameHierarchy`.
- NETCONF credentials are keyed by **port**, not description, so a rename is a `PUT`
  on the existing port entry rather than a `POST`.
- L3VNI uses string concatenation while L2VNI uses integer addition.

Reading the Jinja alone does not surface any of this. A concrete before/after payload does.

## The convention

```yaml
# Example — <scoping note>
#   In : <var> = {
#          "key": "value"
#        }
#   Out: <var> = [
#          { "key": "value" }
#        ]
# <one or two lines on what the filters did and why>
- name: <task name>
  ansible.builtin.set_fact:
```

### No elisions

Examples are written out **completely**. `…`, `...`, `and so on`, truncated image
filenames, shortened UUIDs and `[…]` placeholders are not permitted inside an example
data structure. A reader must be able to copy the `In:` payload into a scratch
playbook and reproduce the documented `Out:` value.

Concretely this means:

| Before | After |
|---|---|
| `"TemplateTarget": ["198.19.1.1", …]` | all six management IPs listed |
| `"upgrade_image": "cat9kv-….SSA.bin"` | `cat9kv-universalk9.BLD_V262_THROTTLE_LATEST_20260529_003538.SSA.bin` |
| `"network_settings": { "dhcp_server": […], "dns_server": {…}, … }` | the full nested block, every key |
| `site_id_map = { …unchanged keys…, "…/Building P0": "3333-3333" }` | all five paths with full 36-char UUIDs |
| `{ "Token": "eyJhbGciOiJIUzI1NiIsInR5cCI6…" }` | a complete, well-formed three-segment JWT literal |
| `"sha": "a1b2c3…"` | a complete 40-character hex SHA |

### Branching tasks

Where a task drives a create / update / no-op decision, one complete `In:`/`Out:`
pair is given **per branch**, with an explicit note of which downstream tasks fire.
`create_or_update_site.yml`, `delete_site.yml` and `netconf_create_or_update.yml`
each document all of their branches this way.

### Real data only

All example values are taken from the live `CICD Pipeline/Settings/settings.json`
and `inventory/group_vars/catalyst_center/connection.yml` — the same
`Global/PODS/POD 0/Building P0/Floor 1` hierarchy, the same
`198.19.1.1`–`198.19.1.6` device list, the same `BGP-EVPN-Switching` profile and
the same SWIM image names the pipeline actually runs against. Nothing is invented.

## Files annotated

| Role | Task files |
|---|---|
| `catc_common` | `load_settings.yml`, `build_hierarchy_paths.yml`, `build_site_id_map.yml`, `auth_token.yml` |
| `site_hierarchy` | `main.yml`, `create_or_update_site.yml`, `delete_site.yml` |
| `network_settings` | `main.yml`, `apply_network_settings.yml` |
| `network_profile` | `main.yml` |
| `credentials` | `main.yml`, `netconf_create_or_update.yml`, `netconf_delete.yml` |
| `device_discovery` | `main.yml` |
| `assign_to_site` | `main.yml` |
| `template_sync` | `main.yml` |
| `swim` | `load_swim_details.yml`, `preflight.yml`, `postcheck.yml` |

Remaining files (`template_sync/process-*.yml`, `provision_devices`,
`deploy_composite`, `backup_configs`, `http_image_server`, `yangsuite_docker`)
retain their boxed headers and are queued for the same treatment.

## Defects fixed along the way

Three role task files had comment blocks whose newlines had been collapsed by an
earlier bulk edit, producing lines such as:

```yaml
#   Out: _exists = true, _site_id = "3333-3333"
#                                  → UPDATE tasks fire- name: "Derive path / IDs / exists"
```

The `- name:` was still parsed correctly by YAML because the whole line begins with
`#`, but the task itself had silently become part of the comment. Affected files:

- `roles/site_hierarchy/tasks/create_or_update_site.yml`
- `roles/site_hierarchy/tasks/delete_site.yml`
- `roles/credentials/tasks/netconf_create_or_update.yml`

All three were repaired and re-verified.

## Validation

```bash
cd "CICD Pipeline/ansible"

# 1. Every role task file, playbook, defaults and handlers file parses as YAML
python3 -c "
import yaml,glob
bad=0
for f in (sorted(glob.glob('roles/*/tasks/*.yml'))
        + sorted(glob.glob('playbooks/*.yml'))
        + sorted(glob.glob('roles/*/defaults/*.yml'))
        + sorted(glob.glob('roles/*/handlers/*.yml'))):
    try: yaml.safe_load(open(f))
    except Exception as e: bad+=1; print('FAIL',f,e)
print('yaml ok' if bad==0 else f'{bad} failures')
"
# → yaml ok

# 2. Every playbook passes Ansible syntax-check
fail=0
for p in playbooks/*.yml; do
  ansible-playbook --syntax-check "$p" >/dev/null 2>&1 || { fail=1; echo "FAIL $p"; }
done
echo "fail=$fail"
# → fail=0

# 3. No elisions remain inside example data structures
grep -rn "…" --include="*.yml" roles playbooks
# → only prose/schema summaries in not-yet-annotated files
```

## Operational impact

None. All changes are comments. No task names, module arguments, `when:`
conditions, variable names or REST payloads were modified. Rendered IOS-XE
configuration and Catalyst Center API behaviour are unchanged.

## Known follow-ups

- `template_sync/process-subfolder.yml`, `process-composite.yml` and
  `process-template.yml` still need In/Out examples (24 `set_fact` tasks between them).
- `provision_devices`, `deploy_composite`, `backup_configs`, `http_image_server`
  and `yangsuite_docker` task files still need In/Out examples.
- SWIM evidence artifacts still use pre-renumbering filename prefixes
  (`-00_preflight.json`, `-10_import_and_tag.json`, `-20_distribute.json`,
  `-30_activate.json`, `-35_rollback.json`, `-40_postcheck.json`). Renaming these
  to match the `06.N` stage numbering would change emitted artifact names and is
  deferred pending approval.
