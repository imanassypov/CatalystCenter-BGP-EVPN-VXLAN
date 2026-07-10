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

## Quick checks

```bash
bash verify-cml-inventory.sh          # CML inventory tree (--graph)
cd ansible && ../.venv/bin/ansible-inventory -i inventory/cml.yml --graph
```

More inventory CLI examples (merged inventory, `--list`, `--host`, reading groups): **`ansible/README.md`** → *Inspect inventory from the CLI*.
