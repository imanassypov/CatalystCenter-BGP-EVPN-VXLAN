# DEFN Template Editor

Web editor for Catalyst Center `DEFN-*.j2` data dictionaries. Loads templates from a mounted folder, edits them in AG Grid tables, and writes changes back with preamble preservation and `.bak` backups.

## Quick start (Docker)

**Recommended** — no Python venv required:

```bash
cd "CICD Pipeline/utils/defn-editor"
./start.sh
```

Or:

```bash
cd "CICD Pipeline/utils/defn-editor"
docker compose up --build
```

Open http://localhost:8080

Paste any **absolute host path** in **Project folder** and click **Load project**, or click **Browse…** to pick a folder:

- **macOS (app on host):** native Finder dialog fills the path field
- **Chrome / Edge:** reads and writes `DEFN-*.j2` directly in the picked folder
- **Safari / Firefox:** folder upload fallback (save downloads rendered files only via path mode)

Docker mounts `${HOME}` so pasted paths like `/Users/you/...` work for **Load**.

Default on first open: `/data/templates` (repo `Site BGP EVPN Templates`). To use paths outside `$HOME`, add a volume and `ALLOWED_PATH_ROOTS` in `docker-compose.yml`.

> **Troubleshooting:** If `pip` errors mention `.Trash/defn-editor`, your shell still has an old venv active. Run `deactivate` (or open a new terminal), `cd` into `defn-editor` again, then use Docker only. If you see `no configuration file provided`, you are not in the `defn-editor` directory.

Volume mounts:

- `Site BGP EVPN Templates` → `/data/templates` (default)
- `${HOME}` → `${HOME}` (any project folder under your profile)

## Architecture

| Path | Purpose |
|------|---------|
| `defn_core/` | Parse, normalize, serialize, validate DEFN files |
| `app/` | Flask API + AG Grid UI |
| `schema/defn_schema.yaml` | Variable bindings and column definitions |
| `defn_io.py` | CLI: `load`, `save`, `validate` |
| `docker-compose.yml` | Container + volume mount |

## CLI (no Docker)

```bash
cd "CICD Pipeline/utils/defn-editor"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=.

python defn_io.py load \
  --folder "../../Catalyst Center Templates/Site BGP EVPN Templates" \
  --out /tmp/session.json

python defn_io.py save \
  --folder "../../Catalyst Center Templates/Site BGP EVPN Templates" \
  --in /tmp/session.json

python defn_io.py validate \
  --folder "../../Catalyst Center Templates/Site BGP EVPN Templates"
```

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/schema` | Full schema + UI tab layout |
| GET | `/api/config` | Project root and file count |
| POST | `/api/project/load` | `{"folder": "/absolute/path"}` — load DEFN files |
| GET | `/api/session` | Current in-memory session |
| PUT | `/api/session` | Replace session after grid edits |
| POST | `/api/validate` | Cross-DEFN + Jinja2 checks |
| POST | `/api/save` | Write `.j2` files to project root |

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFN_PROJECT_ROOT` | `/data/templates` | Default mount inside container |
| `DEFN_DEFAULT_FOLDER` | same as above | Pre-filled path in the UI |
| `ALLOWED_PATH_ROOTS` | unset (local) / `$HOME` (Docker) | Colon-separated roots users may load |

## Tests

```bash
pytest tests/ -v
```

## Notes

- **Additive only:** Existing rows and scalar values are read-only. Add new rows with **Add row**; existing entries cannot be edited or deleted (enforced in UI and on save).
- `DEFN_CLIENT_PORT_DEVICES` is auto-derived from `DEFN_CLIENT_PORTS` on save (not shown in UI).
- Save creates timestamped `.bak.*` files before overwriting.
