---
name: splunk-app-deploy
description: >-
  Build, deploy, and verify the campus_evpn_assurance Splunk app on the EC2
  Splunk host via jump-host SSH. Use when the user asks to deploy, push to
  Splunk, install the app, restart splunkd, or update dashboards after
  editing campus_evpn_assurance views or app.conf.
---

# Splunk App Deploy — campus_evpn_assurance

Deploy the **Campus EVPN Assurance** Splunk app to the cloud Splunk EC2 host.
**Primary execution path:** run the packaging deploy script. Do not hand-roll SSH
or MCP commands unless the script fails and you are debugging.

## When to use

- User says: deploy, push to Splunk, install app, restart splunkd, update dashboard
- After editing `campus_evpn_assurance/` views, `app.conf`, or static assets
- When Dashboard Studio shows stale tiles after on-disk XML was updated

## Agent instructions

1. **Do not deploy or bump `build` unless the user explicitly asks.**
2. Read `campus_evpn_assurance/default/app.conf` for current `version` and `build`.
3. If the user asked to deploy, bump `build` only when that is part of the task.
4. Run `packaging/deploy-splunk-app.sh` from the workstation (not on the Splunk host).
5. On success, tell the operator to hard-refresh Splunk Web (Cmd+Shift+R / Ctrl+Shift+R).
6. Never commit `.env`, PEM keys, or passwords.

## Paths (workspace-relative)

| Item | Path |
|------|------|
| App source | `Campus BGP EVPN Splunk Assurance/campus_evpn_assurance/` |
| `app.conf` | `campus_evpn_assurance/default/app.conf` |
| Build script | `Campus BGP EVPN Splunk Assurance/packaging/build-app.sh` |
| **Deploy script** | `Campus BGP EVPN Splunk Assurance/packaging/deploy-splunk-app.sh` |
| Python helper | `Campus BGP EVPN Splunk Assurance/packaging/scripts/deploy_splunk.py` |
| Skill symlink | `.cursor/skills/splunk-app-deploy/scripts/deploy-splunk-app.sh` |
| Output `.spl` | `packaging/dist/campus_evpn_assurance-<version>.spl` |
| Credentials | `CICD Pipeline/utils/mcp-ssh-server/.env` |
| SSH key | `CICD Pipeline/utils/mcp-ssh-server/splunk-creds/ec2user-splunk.pem` |
| MCP inventory | `CICD Pipeline/utils/mcp-ssh-server/devices.csv` (`splunk` device) |
| Studio validator | `Campus BGP EVPN Splunk Assurance/tools/validate_studio.py` |

## Connectivity

| Hop | Host | Auth |
|-----|------|------|
| Jump (bastion) | `root@198.18.134.28` | `SCRIPT_SERVER_SSH_PASS` from `.env` |
| Splunk EC2 | `ec2-user@18.224.25.161` | PEM at `SPLUNK_SSH_KEY_PATH` (via jump) |

MCP device name: **`splunk`** (`proxy_jump=script-server` in `devices.csv`).

## Required `.env` variables

Never hardcode or commit passwords. Load from `.env`:

- `SCRIPT_SERVER_SSH_PASS` — jump host
- `SPLUNK_ADMIN_USER` / `SPLUNK_ADMIN_PASS` — Splunk CLI/REST `-auth`
- `SPLUNK_SSH_KEY_PATH` — defaults to `splunk-creds/ec2user-splunk.pem` (relative to `.env` dir)

Copy template: `cp "CICD Pipeline/utils/mcp-ssh-server/.env.example" "CICD Pipeline/utils/mcp-ssh-server/.env"`

## Workflow

```
Task Progress:
- [ ] 1. Bump build in app.conf (only if user asked or change warrants it)
- [ ] 2. Run deploy script (builds .spl unless --skip-build)
- [ ] 3. Script uploads, install -update 1, restart, verifies build
- [ ] 4. Optional REST marker verify (--verify-marker)
- [ ] 5. Tell user to hard-refresh Splunk Web
```

### Step 1 — Bump build (when needed)

Edit `[app]` → `build` in `campus_evpn_assurance/default/app.conf`.
**Only bump when the user requests a deploy or a version/build change is part of the task.**

### Step 2 — Deploy (primary path)

```bash
cd "Campus BGP EVPN Splunk Assurance/packaging"
chmod +x deploy-splunk-app.sh build-app.sh
./deploy-splunk-app.sh
```

Skip rebuild if a current `.spl` already exists in `dist/`:

```bash
./deploy-splunk-app.sh --skip-build
```

Verify a dashboard change is live via Splunk REST (`executive_overview`):

```bash
./deploy-splunk-app.sh --verify-marker "viz_executive_overview_18"
```

Use a unique substring from your change (panel id, title, or new field name).

### What the script does

1. Sources `CICD Pipeline/utils/mcp-ssh-server/.env` when present
2. Runs `build-app.sh` (unless `--skip-build`)
3. Uploads `.spl` via paramiko through jump host (`deploy_splunk.py`)
4. `splunk install app /tmp/campus_evpn_assurance-*.spl -update 1 -auth USER:PASS`
5. Removes temp `.spl` on server
6. `splunk restart`, polls up to 90s for `splunkd` running
7. Compares remote `build` in `app.conf` to local expected value
8. Optional `--verify-marker` REST check on `executive_overview`

### Step 3 — Optional full validator

After deploy, run Dashboard Studio validation locally (needs Splunk admin creds):

```bash
python3 "Campus BGP EVPN Splunk Assurance/tools/validate_studio.py" \
  "$SPLUNK_ADMIN_USER" "$SPLUNK_ADMIN_PASS"
```

### Step 4 — Tell the operator

Dashboard Studio caches in the browser. After successful deploy:

1. **Hard-refresh**: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
2. If still stale: log out/in or use a private/incognito window

## Prerequisites

```bash
pip install -r "CICD Pipeline/utils/mcp-ssh-server/requirements.txt"
```

Needs `paramiko` and `python-dotenv`.

## MCP fallback (manual steps)

If the deploy script is unavailable, follow
`CICD Pipeline/utils/mcp-ssh-server/README-MCP-HOWTO.md` § *Splunk App Update*.
Always use `install app … -update 1` and restart `splunkd`.

Copying view XML directly to `/opt/splunk/etc/apps/campus_evpn_assurance/...`
updates disk only — Splunk may keep serving cached knowledge objects until
`install -update` and restart.

## Common failures

| Symptom | Fix |
|---------|-----|
| Browser unchanged after deploy | Hard-refresh; confirm REST marker with `--verify-marker` |
| `install app` object exists | Use `-update 1` (script does this) |
| SSH/key errors | Check `.env`, PEM path, jump password |
| Build mismatch after deploy | Re-run without `--skip-build`; confirm `app.conf` build bumped |
| `paramiko` missing | Install MCP server requirements |
| `sudo` hangs on Splunk host | Ensure `ec2-user` has NOPASSWD for splunk commands |

## Do not

- Commit `.env`, PEM keys, or passwords
- Deploy or bump build unless the user asked
- Copy view XML directly to `/opt/splunk/etc/apps/...` without `install -update` + restart

## Canonical script location

The deploy script lives only under `packaging/`. The skill exposes a symlink at
`.cursor/skills/splunk-app-deploy/scripts/deploy-splunk-app.sh` for convenience.
