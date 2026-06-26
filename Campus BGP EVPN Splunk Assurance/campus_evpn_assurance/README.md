# Campus EVPN Assurance — Splunk App

Operational health and assurance dashboards for a **Cisco Catalyst Campus BGP
EVPN VXLAN** fabric, fed by Model-Driven Telemetry (MDT) over an OpenTelemetry
Collector pipeline into a Splunk **metrics** index.

> **Installing this app?** Follow the step-by-step
> [`SETUP_GUIDE.md`](../SETUP_GUIDE.md) shipped alongside the package. It covers
> the Splunk prerequisites, the telemetry collector install, and the per-device
> configuration required for these dashboards to populate.

## What it does

| Capability | Detail |
|---|---|
| Executive overview | Fabric-wide health roll-up: device reachability, BGP/EVPN, NVE peers, VNI throughput |
| Role dashboards | Dedicated views for **Spines**, **Leafs**, and **Borders** |
| Alerts view | Surfaced operational anomalies across the fabric |
| Native Sankey | NVE peer / VNI relationships rendered with `splunk.sankey` (Dashboard Studio v2) |
| Device enrichment | `cisco.node_id` telemetry key joined to a site/role/IP inventory lookup |

## Requirements

| Requirement | Value |
|---|---|
| Splunk Enterprise / Cloud | **8.0+** (Dashboard Studio v2) |
| Metrics index | `evpn_assurance` (type **metric**) — created by the admin, see SETUP_GUIDE |
| Data source | OpenTelemetry Collector `otelcol-yangfix` → Splunk HEC → `index=evpn_assurance` |
| JavaScript in dashboards | enabled (`ui-prefs.conf`) |

## App layout

```
campus_evpn_assurance/
├── app.manifest                     # Splunk packaging manifest (modern AppInspect)
├── README.md                        # this file
├── default/
│   ├── app.conf                     # app metadata, version 1.5.0
│   ├── macros.conf                  # evpn_index / evpn_lb / evpn_lookup macros
│   ├── transforms.conf              # evpn_device_inventory lookup definition
│   ├── ui-prefs.conf                # enable_javascript = true
│   └── data/ui/
│       ├── nav/default.xml          # app navigation
│       └── views/                   # Dashboard Studio v2 dashboards
│           ├── executive_overview.xml
│           ├── spines.xml
│           ├── leafs.xml
│           ├── borders.xml
│           └── alerts.xml
├── lookups/
│   └── evpn_device_inventory.csv    # device inventory — REPLACE with your fabric
├── metadata/
│   └── default.meta                 # permissions (read:*, write:admin,power)
└── static/
    ├── appIcon.png                  # 36×36 launcher icon
    ├── appIcon_2x.png               # 72×72 (retina)
    ├── appIconAlt.png               # 36×36 light variant
    └── appIconAlt_2x.png            # 72×72 light variant
```

## The device inventory lookup (you must customise this)

`lookups/evpn_device_inventory.csv` maps each telemetry device key to its
metadata. The dashboards enrich metrics with it via the `evpn_lookup` macro.

| Column | Meaning |
|---|---|
| `source` | Device FQDN as known to Catalyst Center |
| `hostname` | **Must equal the `cisco.node_id` dimension** emitted by the collector (e.g. `Spine-01`) |
| `ip_address` | Management IP |
| `loopback` | Underlay loopback (RID) |
| `site` | Site name shown in dashboards |
| `role` | `spine` \| `leaf` \| `border` |
| `description` | Free-text label |

> Replace every row with your own fabric devices. The shipped rows are the lab
> reference fabric and will not match your environment. A blank template is
> provided as `evpn_device_inventory.template.csv` in the handoff bundle.

## Macros

| Macro | Purpose |
|---|---|
| `evpn_index` | `index=evpn_assurance` — change here if you use a different index name |
| `evpn_lb` | default panel lookback (`earliest=-15m latest=now`) |
| `evpn_lookup` | renames `cisco.node_id` → `hostname` and joins the inventory lookup |

## Verifying data after install

```spl
| mstats latest("cisco.cp-vnis.") AS vnis WHERE `evpn_index` BY "cisco.node_id"
| `evpn_lookup`
```

A populated table confirms telemetry is flowing and the lookup is matching.

## Version

`1.5.0` (build 56). See [`../SETUP_GUIDE.md`](../SETUP_GUIDE.md) for the full
install, upgrade, and telemetry-pipeline procedures.
