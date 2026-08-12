# 2026-08-11 — Fix macOS "A worker was found in a dead state" on playbook start

## Symptom

Running any Catalyst Center playbook on macOS aborts on the first API task:

```
TASK [site_hierarchy : Phase A — Fetch all existing sites from Catalyst Center] ***
ERROR! A worker was found in a dead state
```

The failure is not specific to `site_hierarchy` — it happens on whichever task
first calls the Catalyst Center SDK.

## Root cause

Ansible's `linear` strategy forks a worker process per task. The
`cisco.dnac`/`catalystcenter` SDK issues HTTPS calls through `requests`, which on
macOS performs a **SystemConfiguration proxy lookup** and a CoreFoundation-backed
DNS resolution. Both initialise the Objective-C runtime in the controller process.

Since macOS 10.13, calling `fork()` after the Objective-C runtime has been
initialised causes the child to abort immediately (`objc[...]: +[__NSCFConstantString
initialize] may have been in progress in another thread when fork() was called`).
Ansible sees the worker die before it reports a result and raises
`A worker was found in a dead state`.

Linux is unaffected — there is no Objective-C runtime.

## Change

`CICD Pipeline/.envrc` now exports the two variables that avoid the abort, guarded
to macOS only:

```bash
if [ "$(uname -s)" = "Darwin" ]; then
  export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
  export no_proxy='*'
fi
```

| Variable | Effect |
|---|---|
| `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` | Disables the post-`fork()` Objective-C initialisation check so forked workers survive |
| `no_proxy='*'` | Bypasses the macOS SystemConfiguration proxy lookup that loads CoreFoundation in the first place |

Because direnv walks up from the working directory, this applies to playbook runs
started from `CICD Pipeline/ansible` as well.

## Files changed

| File | Change |
|---|---|
| `CICD Pipeline/.envrc` | Added macOS-guarded fork-safety exports |
| `CICD Pipeline/README.md` | New *macOS fork-safety (required)* section under *Environment (direnv)* |

## Operational impact

- No change to playbook logic, inventory, or templates.
- macOS users must run `direnv allow` once in `CICD Pipeline/` after pulling, since
  `.envrc` content changed and direnv re-prompts for trust.
- Users not running direnv must export both variables manually (documented in the
  README) or add them to `~/.zshrc`.
- CI/Linux runners are unaffected — the block is skipped on non-Darwin hosts.

## Validation

```bash
cd "CICD Pipeline"
direnv allow
echo "$OBJC_DISABLE_INITIALIZE_FORK_SAFETY"   # -> YES
cd ansible && ansible-playbook playbooks/00_site_deploy.yml
```

Phase A completes and the play proceeds past the site hierarchy stage.
