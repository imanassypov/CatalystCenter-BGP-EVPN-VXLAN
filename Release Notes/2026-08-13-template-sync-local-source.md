# 2026-08-13 — Stage 07 template sync can read from a local directory

## Summary

`07_template_sync.yml` previously had exactly one source of templates: the GitHub REST API. Every iteration on a `.j2` template therefore required a commit and a push before it could be pushed into Catalyst Center Template Programmer.

A new `template_source` variable adds a second source — a directory on the machine running Ansible. `template_source: git` remains the default and its behaviour is byte-identical to before.

```bash
ansible-playbook playbooks/07_template_sync.yml                          # GitHub (default)
ansible-playbook playbooks/07_template_sync.yml -e template_source=local # working tree
ansible-playbook playbooks/07_template_sync.yml -e template_source=local \
  -e template_local_root=/abs/path/to/templates
```

## Motivation

Template authoring is an edit/render/inspect loop. Forcing a commit + push between every iteration made the loop slow, polluted history with "fix typo" commits, and meant a broken template had to be committed before it could be observed failing in Catalyst Center. Reading from the working tree collapses that loop to a single playbook run.

## Design — one discovery contract, two producers

Both sources now converge on a single fact:

```
repo_tree_entries = [ {path: "<root-relative path>"}, ... ]
```

`process-subfolder.yml`, `process-template.yml`, and `process-composite.yml` consume `repo_tree_entries` and never reference the source again. Ordering, composite parsing, and the `cisco.dnac.template_workflow_manager` payload are therefore shared code with no branching.

```
                 ┌─ template_source: git ──→ GitHub tree API ──┐
git_repo_subfolders                                             ├─→ repo_tree_entries ─→ process-subfolder.yml
                 └─ template_source: local ─→ ansible.builtin.find ┘
```

`git_repo_subfolders` drives both producers. Its `path` values are relative to the repository root under `git`, and relative to `template_local_root` under `local` — one list, no duplication.

## Configuration

`CICD Pipeline/ansible/inventory/group_vars/catalyst_center/connection.yml`:

```yaml
# Template sync / GitHub (stage 7)
# template_source selects where the .j2 templates and composite YAML are read from:
#   git   — GitHub REST API, using git_repo / git_branch / git_token below
#   local — a directory on the machine running Ansible, rooted at template_local_root
# git_repo_subfolders applies to both: its paths are relative to the repository
# root (git) or to template_local_root (local).
template_source: git
# playbook_dir is <repo>/CICD Pipeline/ansible/playbooks, so three dirname calls
# walk up to the repository root:
#   playbook_dir            <repo>/CICD Pipeline/ansible/playbooks
#   | dirname               <repo>/CICD Pipeline/ansible
#   | dirname               <repo>/CICD Pipeline
#   | dirname               <repo>
template_local_root: "{{ playbook_dir | dirname | dirname | dirname }}"
git_repo: "https://github.com/imanassypov/CatalystCenter-BGP-EVPN-VXLAN.git"
git_branch: main
git_repo_subfolders:
  - path: "Catalyst Center Templates/Site BGP EVPN Templates"
    project_name: "Building P0"
  - path: "Catalyst Center Templates/DMZ BGP EVPN Templates"
    project_name: "DMZ 01"
template_extension: j2
include_diff_header: false
```

The default points at whichever clone the playbook runs from, with no absolute path hard-coded. If `07_template_sync.yml` ever moves to a different directory depth, the `dirname` chain must be adjusted or `template_local_root` set explicitly.

| Variable | Default | Description |
|---|---|---|
| `template_source` | `git` | `git` or `local`. Any other value fails the run at the first task. |
| `template_local_root` | repository root | Directory scanned in `local` mode. Must exist and be a directory. |

## Behavioural differences in `local` mode

| Aspect | `git` | `local` |
|---|---|---|
| Version description | Real commit message, truncated to `catc_template_summary_maxchar` | `Synced from local directory <date> <time>` |
| Diff header | Honours `include_diff_header` | Always off — there is no commit to diff |
| `git_token` | Optional; lifts the 60 req/hr anonymous limit | Unused |
| Network to GitHub | Required | Not required |
| Network to Catalyst Center | Required | Required |

## Changed files

| File | Change |
|---|---|
| `inventory/group_vars/catalyst_center/connection.yml` | Added `template_source`, `template_local_root` above the existing Git block, with a comment explaining that `git_repo_subfolders` serves both. |
| `roles/template_sync/tasks/main.yml` | Added a `template_source` validation task; moved the `git_repo_subfolders` guard ahead of discovery (local discovery needs it for `paths`); wrapped the eight GitHub tasks in a `Discover templates in GitHub repository` block; added a `Discover templates in local directory` block; both blocks terminate in a `set_fact` producing `repo_tree_entries`. |
| `roles/template_sync/tasks/process-subfolder.yml` | Reads `repo_tree_entries` instead of `repo_tree_response.json.tree`; the GitHub content/commit/diff tasks gained `when: template_source == 'git'`; added `slurp`-based readers for local template and composite content; enrichment picks content and commit message per source. |
| `playbooks/07_template_sync.yml` | Header block documents both sources; `Run:` examples cover local mode. |
| `CICD Pipeline/ansible/README.md` | New "Template sync (stage 7)" section with the source-comparison table, variable table, and caveats; pipeline table row updated; local example added to Common Overrides. |
| `README.md` | Stage 7 row and "Template GitOps (Stage 7.0) in detail" updated for the second source. |

`process-template.yml` and `process-composite.yml` are unchanged — they were already source-agnostic.

## Implementation notes

- **Scoped `find`, not a recursive walk.** `ansible.builtin.find` does not prune hidden directories, so a walk of `template_local_root` descends into `.git` and `.venv` and returns noise such as `galaxy.yml.j2` and `container.yml.j2`. `paths:` is therefore built from `git_repo_subfolders` only:

  ```yaml
  paths: "{{ git_repo_subfolders | map(attribute='path') | map('regex_replace', '^', template_local_root + '/') | list }}"
  ```

- **`slurp`, not the `file` lookup.** The `file` lookup strips trailing newlines; `slurp` + `b64decode` reproduces bytes exactly, so a template synced from local is identical to the same template synced from Git.

- **Lazy Jinja guards.** `A if cond else B` is lazily evaluated, so referencing `template_commit_results` inside the enrichment expression is safe even when the GitHub commit task was skipped.

## Validation

Run from the control node (pyenv 3.10.4 interpreter — it has `dnacentersdk 2.11.0`; the `.venv` does not), with the macOS fork-safety prefix:

```bash
cd "CICD Pipeline/ansible"
no_proxy='*' OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES \
  ansible-playbook playbooks/07_template_sync.yml -e template_source=local
```

Result:

```
PLAY RECAP
catalyst_center_api : ok=131  changed=2  unreachable=0  failed=0  skipped=52
```

Task-level evidence that the local path was the one exercised:

| Task | Result |
|---|---|
| `Find template and composite files under local template root` | ok |
| `Fetch template file contents from GitHub` | skipped |
| `Read template file contents from local directory` | ok (24 items) |
| `Fetch last commit info for each template file` | skipped |
| `Fetch composite definition file contents from GitHub` | skipped |
| `Read composite definition file contents from local directory` | ok (`BGP-EVPN-BUILD.yml`) |

Sync summary:

```
Subfolder synced: Catalyst Center Templates/Site BGP EVPN Templates
Project: Building P0
Regular templates synced: 24
Composite templates synced: 1
No 'j2' templates found under 'Catalyst Center Templates/DMZ BGP EVPN Templates' - skipping this subfolder.
Projects synced: 1
```

The DMZ warning is expected — that folder is currently empty, and an empty subfolder warns and skips rather than failing.

`ansible-playbook playbooks/07_template_sync.yml --syntax-check` passes.

## Operational impact

- **None for existing runs.** `template_source` defaults to `git`; the GitHub code path and its API calls are unchanged.
- `local` mode is a development convenience. Production/CI runs should stay on `git` so that Catalyst Center template versions carry real commit provenance.
- A `local` sync overwrites the Catalyst Center template with working-tree content that may not exist in any commit. Follow it with a `git` sync once the change is committed, so the recorded version description points at a real SHA.

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| `template_local_root '<path>' does not exist or is not a directory.` | `template_local_root` override is wrong, or the play ran from an unexpected directory | Pass an absolute path with `-e template_local_root=/abs/path` |
| Unexpected templates such as `galaxy.yml.j2` appear | `paths:` was widened to the whole root | Keep `paths:` derived from `git_repo_subfolders` |
| `Exception: DNA Center Python SDK is not installed` | Ran with `../.venv/bin/ansible-playbook`, which has no `dnacentersdk` | Use the PATH `ansible-playbook` (pyenv 3.10.4) |
| `[Errno 51] Network is unreachable` to `198.18.129.100:443` | dCloud VPN is down — unrelated to `template_source` | Reconnect AnyConnect; confirm with `nc -z 198.18.129.100 443` |
| `template_source must be 'git' or 'local' (got '<value>')` | Typo in the override | Use exactly `git` or `local` |
