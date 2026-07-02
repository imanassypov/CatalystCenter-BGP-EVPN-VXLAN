# 2026-07-02 — Splunk Assurance Dashboard Screenshots in Operator's Guide

## What changed

Added a rendered screenshot of each of the five role-segmented Splunk dashboards to the
**Operator's Guide** section of the Splunk Assurance sub-project README
([`Campus BGP EVPN Splunk Assurance/README.md`](../Campus%20BGP%20EVPN%20Splunk%20Assurance/README.md)).

Each screenshot is embedded directly beneath its **Purpose** paragraph and above the panel-by-panel
metric table, so a reader sees the live dashboard before reading how to interpret each panel.

| README subsection | Screenshot | Splunk view |
|---|---|---|
| View 1 — Executive Overview | `images/splunk_executive.png` | `executive_overview` |
| View 2 — Leafs | `images/splunk_leafs.png` | `leafs` |
| View 3 — Spines | `images/splunk_spines.png` | `spines` |
| View 4 — Borders | `images/splunk_borders.png` | `borders` |
| View 5 — Alerts | `images/splunk_alerts.png` | `alerts` |

## Motivation

The Operator's Guide describes every panel in prose but previously had no visual reference. The
screenshots give the on-shift engineer an at-a-glance picture of each dashboard's layout — the
scorecard row, trend charts, Sankeys, reachability matrices, and alert tables — before drilling into
the interpretation tables.

## Capture details

- **Source instance**: Splunk Enterprise 10.4.0, app `campus_evpn_assurance`, Search Head
  `http://18.224.25.161:8000`.
- **Scope**: site `Building P0`; scorecards read the latest snapshot, trends over the picker window.
- **Format**: full-dashboard PNG per view.

## GitHub image normalization

All five PNGs were normalized to the repo's GitHub constraints (longest side ≤ 4000 px, file ≤ 1.2 MB):

```bash
cd "Campus BGP EVPN Splunk Assurance/images"
/usr/bin/sips -Z 4000 splunk_<view>.png --out splunk_<view>.png   # cap longest side
/usr/bin/sips -g pixelWidth -g pixelHeight splunk_<view>.png       # verify ≤ 4000 px
stat -f%z splunk_<view>.png                                        # verify ≤ 1258291 bytes
```

Final sizes: executive 1915×4000 (1.12 MB), leafs 1307×3300 (1.15 MB), spines 3300×2834 (1.14 MB),
borders 1400×4000 (0.91 MB), alerts 2870×2490 (0.35 MB).

## Refreshing the screenshots

When a dashboard's layout or panels change, recapture the affected view against a logged-in Splunk
instance (site `Building P0`, a populated time window), save it over the matching
`images/splunk_<view>.png`, and re-run the normalization commands above before committing.

## Operational impact

Documentation only. No dashboard XML, telemetry pipeline, template, or provisioning behavior changed.
