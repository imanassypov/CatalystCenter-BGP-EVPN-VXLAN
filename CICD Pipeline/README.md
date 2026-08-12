# CICD Pipeline

Ansible automation, MCP SSH tooling, and lab environment config.

## Environment (direnv)

Lab credentials and CML/MCP settings live in **`.env`** (gitignored). They load automatically when you enter this directory.

```bash
cp .env.example .env    # first time only — fill in secrets
direnv allow            # one-time trust for .envrc
cd .                    # or cd away and back — direnv loads .env
```

Requires [direnv](https://direnv.net/) with the shell hook enabled (`eval "$(direnv hook zsh)"` in `~/.zshrc`).

Without direnv, source manually:

```bash
set -a && source .env && set +a
```

### macOS fork-safety (required)

On macOS, Ansible forks a worker process per task. The `cisco.dnac`/`catalystcenter`
SDK triggers CoreFoundation proxy and DNS lookups in the parent process, which
initialises the Objective-C runtime. `fork()` after that aborts the child and
Ansible reports:

```
TASK [site_hierarchy : Phase A — Fetch all existing sites from Catalyst Center]
ERROR! A worker was found in a dead state
```

`.envrc` exports the two variables that prevent this, so with direnv enabled the
fix is automatic. Without direnv, export them in the shell that runs the playbook
(or add them to `~/.zshrc`):

```bash
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export no_proxy='*'
```

| Variable | Why |
|---|---|
| `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` | Stops the Objective-C runtime from aborting forked children |
| `no_proxy='*'` | Skips the macOS SystemConfiguration proxy lookup that loads CoreFoundation |

## Quick checks

```bash
bash verify-cml-inventory.sh          # CML inventory tree (--graph)
cd ansible && ../.venv/bin/ansible-inventory -i inventory/cml.yml --graph
```

More inventory CLI examples (merged inventory, `--list`, `--host`, reading groups): **`ansible/README.md`** → *Inspect inventory from the CLI*.
