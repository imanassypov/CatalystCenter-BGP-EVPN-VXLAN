# Release Note — 2026-06-26

## Campus EVPN Assurance — Installable Splunk App Package & Customer Handoff Bundle

### Summary

The `campus_evpn_assurance` Splunk app is now packaged as a self-contained, installable
deliverable that a customer can install through the Splunk UI ("Install app from file")
with no piece-by-piece file injection. A repeatable build produces a clean `.spl` package
plus a full **handoff bundle** that also ships the patched OpenTelemetry collector source,
the systemd integration, the IOS-XE telemetry subscriptions, a blank inventory template,
and a step-by-step setup guide.

### What Changed

| Area | Before | After |
|------|--------|-------|
| App metadata | `app.conf` version mismatch (launcher 1.0.2 / app 1.5.0) | Unified to **1.5.0** (build 56), `[install] state = enabled` |
| In-app docs | none | `campus_evpn_assurance/README.md` shown to installers |
| Packaging manifest | none | `campus_evpn_assurance/app.manifest` (AppInspect 2.0, requires Splunk 8.0+) |
| Launcher icons | none | `static/appIcon[_2x].png` + `appIconAlt[_2x].png` (spine-leaf glyph) |
| Inventory template | lab-populated CSV reused as "template" | dedicated blank `evpn_device_inventory.template.csv` |
| Collector source | tarball gitignored (`*.tar.gz`) and untracked | committed via `.gitignore` negation, shipped in the bundle |
| Build tooling | manual | `packaging/build-app.sh` + `packaging/build-handoff-bundle.sh` |

### Files Added

- `Campus BGP EVPN Splunk Assurance/campus_evpn_assurance/README.md`
  - In-app documentation: capabilities, requirements, layout, the device-inventory
    lookup contract, macros, and a post-install data-verification query.
- `Campus BGP EVPN Splunk Assurance/campus_evpn_assurance/app.manifest`
  - Splunk packaging manifest (schemaVersion 2.0.0), `platformRequirements.splunk.Enterprise = 8.0`.
- `Campus BGP EVPN Splunk Assurance/campus_evpn_assurance/static/appIcon.png`,
  `appIcon_2x.png`, `appIconAlt.png`, `appIconAlt_2x.png`
  - 36×36 / 72×72 launcher icons rendering a spine-leaf fabric glyph.
- `Campus BGP EVPN Splunk Assurance/packaging/make_icons.py`
  - Pure-PIL generator that re-renders all four icons.
- `Campus BGP EVPN Splunk Assurance/packaging/evpn_device_inventory.template.csv`
  - Blank inventory template (header + commented column reference + example rows).

### Files Modified

- `Campus BGP EVPN Splunk Assurance/packaging/build-handoff-bundle.sh`
  - Now ships the dedicated `evpn_device_inventory.template.csv` (instead of copying the
    lab-populated lookup as the template).
- `Campus BGP EVPN Splunk Assurance/.gitignore`
  - Added a negation so the patched receiver source bundle
    `otel-collector/receiver_yang_26_05_27.tar.gz` is committed despite the `*.tar.gz` rule.
- `Campus BGP EVPN Splunk Assurance/README.md`
  - Updated the repository layout to include the in-app README, `app.manifest`, `static/`
    icons, `ui-prefs.conf`, `make_icons.py`, the template CSV, and the `dist/` output.

### Deliverables (from `packaging/build-handoff-bundle.sh`)

- `packaging/dist/campus_evpn_assurance-1.5.0.spl` — installable app package, containing
  `app.manifest`, in-app `README.md`, all five Dashboard Studio v2 views, macros/transforms,
  lookup, metadata, and `static/` launcher icons.
- `packaging/dist/campus-bgp-evpn-splunk-assurance-bundle-1.5.0.tar.gz` — handoff bundle:
  the `.spl`, `SETUP_GUIDE.md`, `README.md`, `evpn_device_inventory.template.csv`,
  `telemetry-subscriptions.ios-xe.cfg`, and the full `otel-collector/` tree
  (`builder.yaml`, `receiver_yang_26_05_27.tar.gz`, `agent_config.running.yaml`,
  `systemd/override.conf.example`, receiver notes).

### Impact

- Customers can install the app entirely through the Splunk UI; no manual file placement.
- The collector is reproducible from committed source: `builder.yaml` + the receiver tarball
  build `otelcol-yangfix` via `ocb`, per `SETUP_GUIDE.md` §4.
- Build output under `packaging/dist/` remains gitignored (`*.spl`, `*.tar.gz`); only the
  receiver source tarball is force-tracked.

### Validation

- `app.manifest` parses as valid JSON.
- `.spl` top level is the single `campus_evpn_assurance/` directory (UI install requirement)
  and includes `app.manifest`, `README.md`, and `static/` icons.
- Handoff bundle includes the `.spl`, setup guide, template CSV, and the receiver tarball.
- `git check-ignore` confirms the receiver tarball is no longer ignored.
- Launcher icons verified at 36×36 and 72×72.
