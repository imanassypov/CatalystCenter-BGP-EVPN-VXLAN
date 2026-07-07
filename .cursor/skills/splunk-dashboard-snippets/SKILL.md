---
name: splunk-dashboard-snippets
description: >-
  Split full Splunk dashboard screenshots into horizontal row snippets for the
  Operator's Guide README. Use when the user recaptures splunk_executive,
  splunk_leafs, splunk_spines, or splunk_borders PNGs, asks to regenerate
  dashboard snippets, update README panel images, or split dashboard screenshots
  along panel row borders.
---

# Splunk Dashboard Snippets — campus_evpn_assurance

Split full-dashboard PNG captures into horizontal row crops aligned to Dashboard
Studio layout rows. Snippets embed in
`Campus BGP EVPN Splunk Assurance/README.md` (Operator's Guide).

**Primary execution path:** run `split_dashboard_snippets.py`. Do not hand-roll
crop coordinates unless the script fails and you are debugging.

## When to use

- User recaptured `splunk_*.png` dashboard screenshots
- User asks to regenerate, refresh, or split dashboard snippets
- Dashboard layout changed in `executive_overview.xml` or `node_details.xml` and
  README panel images need updating
- User mentions snippet splits, panel crops, or Operator's Guide screenshots

## Agent instructions

1. **Do not commit unless the user explicitly asks.**
2. Confirm which source PNG(s) changed (or run all four if unsure).
3. Run the split script from the workstation (needs Pillow).
4. Spot-check scorecard and one mid-dashboard snippet per view.
5. If panel rows were added/renamed in XML, update row names in the script
   before re-running.
6. If README panel text no longer matches layout, update the corresponding
   Operator's Guide subsection — do not only replace images.

## Paths (workspace-relative)

| Item | Path |
|------|------|
| Split script (canonical) | `Campus BGP EVPN Splunk Assurance/images/split_dashboard_snippets.py` |
| Skill symlink | `.cursor/skills/splunk-dashboard-snippets/scripts/split_dashboard_snippets.py` |
| Source screenshots | `Campus BGP EVPN Splunk Assurance/images/splunk_*.png` |
| Output snippets | `Campus BGP EVPN Splunk Assurance/images/snippets/` |
| Summary view XML | `campus_evpn_assurance/default/data/ui/views/executive_overview.xml` |
| Details view XML | `campus_evpn_assurance/default/data/ui/views/node_details.xml` |
| README embeds | `Campus BGP EVPN Splunk Assurance/README.md` — Operator's Guide |
| Images doc | `Campus BGP EVPN Splunk Assurance/images/README.md` |

## Source → output mapping

| Source PNG | Splunk view | Layout XML | Prefix | Rows |
|------------|-------------|------------|--------|------|
| `splunk_executive.png` | Summary | `executive_overview.xml` | `summary` | 9 |
| `splunk_leafs.png` | Details (Leafs) | `node_details.xml` | `leafs` | 11 |
| `splunk_spines.png` | Details (Spines) | `node_details.xml` | `spines` | 11 |
| `splunk_borders.png` | Details (Borders) | `node_details.xml` | `borders` | 11 |

Output files: `snippets/{prefix}_{row-name}.png` (e.g. `summary_scorecards.png`).

Row names are defined in `EXEC_NAMES` and `DETAIL_NAMES` inside the script — keep
them in sync with README `#### Row N` headings.

## Workflow

```
Task Progress:
- [ ] 1. Overwrite source splunk_<view>.png (user capture or provided file)
- [ ] 2. Normalize source PNG for GitHub if needed (see below)
- [ ] 3. Run split_dashboard_snippets.py
- [ ] 4. Verify snippet crops (scorecards + one chart row per view)
- [ ] 5. Update README Operator's Guide if panels changed
- [ ] 6. Commit source PNGs + snippets/ together (only if user asked)
```

### Step 1 — Capture / replace source PNG

Recapture against logged-in Splunk (`campus_evpn_assurance` app):

- Site: `Building P0` (or site shown in lab)
- Time range: populated window (e.g. Last 4 hours)
- Details view: set **Fabric Node Role** to `Leafs`, `Spines`, or `Borders` per file

Save over the matching file in `images/`:

- `splunk_executive.png` — Summary tab
- `splunk_leafs.png` — Details, role Leafs
- `splunk_spines.png` — Details, role Spines
- `splunk_borders.png` — Details, role Borders

### Step 2 — GitHub image normalization (source PNGs only)

Cap longest side ≤ 4000 px and file ≤ 1.2 MB before commit:

```bash
cd "Campus BGP EVPN Splunk Assurance/images"
/usr/bin/sips -Z 4000 splunk_executive.png --out splunk_executive.png
/usr/bin/sips -Z 4000 splunk_leafs.png --out splunk_leafs.png
/usr/bin/sips -Z 4000 splunk_spines.png --out splunk_spines.png
/usr/bin/sips -Z 4000 splunk_borders.png --out splunk_borders.png
```

Snippets are smaller; re-normalize only if a crop exceeds GitHub limits.

### Step 3 — Run split script (primary path)

```bash
cd "Campus BGP EVPN Splunk Assurance/images"
python3 split_dashboard_snippets.py
```

Or via skill symlink:

```bash
python3 ".cursor/skills/splunk-dashboard-snippets/scripts/split_dashboard_snippets.py"
```

**Prerequisite:** Pillow (`pip install Pillow`).

### What the script does

1. Parses Dashboard Studio `layout.structure` Y positions from view XML
2. Maps layout rows to pixel Y using chrome offset + vertical scale
3. Refines each cut by scanning for horizontal panel borders (±40 px)
4. Writes one PNG per layout row to `images/snippets/`

Missing source files are skipped with `SKIP missing` on stderr.

### Step 4 — Verify crops

Read at least these snippets after a split:

| Check | File |
|-------|------|
| Full scorecards + filters | `{prefix}_scorecards.png` |
| Mid-dashboard panel | e.g. `summary_bgp_health_matrix.png`, `leafs_nve_peer_adjacency.png` |

**Healthy crop:** row includes complete panel through bottom border; next row does
not include prior panel content. **Bad crop:** scorecard values split across two
files — re-check chrome detection or layout height in XML.

### Step 5 — README updates (when layout changes)

Operator's Guide subsections live in `Campus BGP EVPN Splunk Assurance/README.md`:

- **View 1 — Summary:** `images/snippets/summary_*.png` (9 rows)
- **View 2 — Details:** `leafs_*`, `spines_*`, `borders_*` (11 rows each)

Each subsection should have: snippet image, short interpretation, IOS-XE CLI block.
When adding/removing panels, update both the script row-name list and README text.

Embed pattern:

```markdown
![Short alt text](images/snippets/summary_scorecards.png)
```

## Layout change checklist

When `executive_overview.xml` or `node_details.xml` panel layout changes:

1. Read new `layout.structure` row Y values
2. Update `EXEC_NAMES` / `DETAIL_NAMES` in `split_dashboard_snippets.py` if row
   count or semantics changed
3. Re-capture affected `splunk_*.png`
4. Re-run split script
5. Add/remove/rename README Operator's Guide subsections to match

## Common failures

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: PIL` | `pip install Pillow` |
| `SKIP missing splunk_*.png` | Place source capture in `images/` |
| Scorecards cut mid-tile | Re-capture at consistent zoom; check layout `height` in XML |
| Wrong row count vs README | Sync `EXEC_NAMES`/`DETAIL_NAMES` with layout rows |
| Snippet shows two dashboard rows | Border refinement failed — inspect script output Y ranges |

## Do not

- Hand-edit snippet PNGs in an image editor for routine updates — re-run the script
- Commit only snippets without updated source `splunk_*.png`
- Paraphrase CLI blocks when updating README — use IOS-XE `show` commands consistent
  with existing Operator's Guide sections

## Canonical script location

The script lives only under `Campus BGP EVPN Splunk Assurance/images/`. The skill
exposes a symlink at
`.cursor/skills/splunk-dashboard-snippets/scripts/split_dashboard_snippets.py`.
