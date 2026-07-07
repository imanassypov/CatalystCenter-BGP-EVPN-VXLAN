# Campus EVPN Assurance — Splunk App

Operational health and assurance dashboards for a **Cisco Catalyst Campus BGP
EVPN VXLAN** fabric, fed by Model-Driven Telemetry (MDT) over an OpenTelemetry
Collector pipeline into a Splunk **metrics** index.

> **Installing this app?** Follow the step-by-step
> [`SETUP_GUIDE.md`](../SETUP_GUIDE.md) shipped alongside the package. It covers
> Splunk prerequisites, the telemetry collector install, and the per-device
> configuration required for these dashboards to populate.
>
> **New to MDT / OpenTelemetry?** Start with the parent
> [`README.md`](../README.md) — especially [§4 Telemetry and Data Model](../README.md#4-telemetry-and-data-model).

---

## What it does

| Capability | Detail |
|---|---|
| **Summary** view | Fabric-wide health roll-up: BGP/EVPN, NVE peers, VNI throughput, tunnel interfaces |
| **Details** view | Role-scoped deep dive — select **Leafs**, **Spines**, or **Borders** from one dashboard |
| **Alerts** view | Surfaced operational anomalies across the fabric |
| Native Sankey | NVE peer / VNI relationships rendered with `splunk.sankey` (Dashboard Studio v2) |
| Device enrichment | `cisco.node_id` telemetry key joined to a site/role/IP inventory lookup |

---

## Requirements

| Requirement | Value |
|---|---|
| Splunk Enterprise / Cloud | **8.0+** (Dashboard Studio v2) |
| Metrics index | `evpn_assurance` (type **metric**) — created by the admin; see [`SETUP_GUIDE.md`](../SETUP_GUIDE.md) |
| Data source | OpenTelemetry Collector `otelcol-yangfix` → Splunk HEC → `index=evpn_assurance` |
| Search permissions | Splunk user must have search access to the **metrics** index (not all lab accounts do) |
| JavaScript in dashboards | enabled (`ui-prefs.conf`) |

---

## App layout

```
campus_evpn_assurance/
├── app.manifest                     # Splunk packaging manifest (modern AppInspect)
├── README.md                        # this file
├── default/
│   ├── app.conf                     # app metadata, version 1.5.0 (build 85)
│   ├── macros.conf                  # evpn_index / evpn_lb / evpn_lookup macros
│   ├── transforms.conf              # evpn_device_inventory lookup definition
│   ├── ui-prefs.conf                # enable_javascript = true
│   └── data/ui/
│       ├── nav/default.xml          # Summary · Details · Alerts
│       └── views/                   # Dashboard Studio v2 dashboards
│           ├── executive_overview.xml   # Summary
│           ├── node_details.xml         # Details (role filter)
│           └── alerts.xml
├── lookups/
│   └── evpn_device_inventory.csv    # device inventory — REPLACE with your fabric
├── metadata/
│   └── default.meta                 # permissions (read:*, write:admin,power)
└── appserver/static/
    └── dashboard.css                # shared Dashboard Studio stylesheet
```

---

## Dashboard views

| Nav tab | View file | Role filter | Focus |
|---|---|---|---|
| **Summary** | `executive_overview.xml` | All roles | Fabric-wide posture — start every shift here |
| **Details** | `node_details.xml` | **Dropdown:** leaf / spine / border | Deep dive on one fabric tier |
| **Alerts** | `alerts.xml` | All roles | Consolidated anomalies and triage table |

Operator interpretation guide:
[`README.md` § Operator's Guide](../README.md#6-operators-guide).

---

## The device inventory lookup (you must customise this)

`lookups/evpn_device_inventory.csv` maps each telemetry device key to its
metadata. The dashboards enrich metrics with it via the `evpn_lookup` macro.

| Column | Meaning |
|---|---|
| `source` | Device FQDN as known to Catalyst Center |
| `hostname` | **Must equal the `cisco.node_id` dimension** emitted by the collector (e.g. `Spine-01`) |
| `ip_address` | Management IP |
| `loopback` | Underlay loopback (RID) — also used to resolve external eBGP peer IPs in matrices |
| `site` | Site name shown in dashboards |
| `role` | `spine` \| `leaf` \| `border` (and optional `core`, `dmz` for external peers) |
| `description` | Free-text label |

> Replace every row with your own fabric devices. The shipped rows are the lab
> reference fabric and will not match your environment. A blank template is
> provided as `evpn_device_inventory.template.csv` in the handoff bundle.

---

## Macros

| Macro | Purpose |
|---|---|
| `` `evpn_index` `` | `index=evpn_assurance` — change here if you use a different index name |
| `` `evpn_lb` `` | default panel lookback (`earliest=-15m latest=now`) |
| `` `evpn_lookup` `` | renames `cisco.node_id` → `hostname` and joins the inventory lookup |

Every dashboard panel uses these macros. If you rename the metrics index, update
`default/macros.conf` and rebuild/reinstall the app package.

---

## How telemetry appears in Splunk

This app reads a **metrics** index. Use **`mstats`** and **`mcatalog`**, not
regular `search index=evpn_assurance` on `_raw` events.

### Key dimensions

| Dimension | Source | Used for |
|---|---|---|
| `cisco.node_id` | Device hostname from MDT | **Primary device key** — join via `` `evpn_lookup` `` |
| `cisco.encoding_path` | YANG model path in the collector | Filter to a specific model/list (BGP, NVE, interfaces, …) |
| `name` | YANG list key | Interface name, VRF, neighbor-id context, etc. |
| `value` | Enum/string companion dimension | Human-readable state when the leaf is an IOS-XE enumeration |
| `vni`, `vni-id`, `evni` | Numeric YANG list keys (patched receiver) | Per-VNI panels, throughput (Sub 40115) |
| `subscription` | Subscription ID (when tagged) | Tie-back to `show telemetry ietf subscription <id>` on device |

> **Do not use Splunk `source` as the device identity.** HEC metrics arrive with
> a generic source (e.g. `http:Cisco MDT`). Always filter and group on
> `cisco.node_id`.

### Device XPath vs Splunk `cisco.encoding_path`

On IOS-XE, the telemetry subscription filter uses the **YANG prefix form**:

```text
/interfaces-ios-xe-oper:interfaces/interface
```

In Splunk, the collector stores a **different** path in `cisco.encoding_path`:

```text
Cisco-IOS-XE-interfaces-oper:interfaces/interface
```

Always copy the encoding path from Splunk (`mcatalog`) — do not paste the device
XPath verbatim into `mstats` filters.

### Enum leaves (`*_info` metrics)

Splunk metrics indexes store **numeric** measurements. IOS-XE enumeration leaves
(oper-status, admin-status, session-state, …) are emitted as:

- metric name: `cisco.oper-status_info`, `cisco.vni-oper-state_info`, …
- string enum in the **`value`** dimension (`if-oper-state-ready`, `nve-vni-state-down`, …)

Query pattern:

```spl
| mstats latest("cisco.oper-status_info") AS _m
  WHERE `evpn_index` earliest=-7d latest=now
  "cisco.encoding_path"="Cisco-IOS-XE-interfaces-oper:interfaces/interface"
  BY "cisco.node_id", name, value
```

BGP up/down in the dashboards uses a numeric workaround (`hold-time > 0`) for the
same reason — see the parent [`README.md`](../README.md#44-metrics-index-and-query-patterns).

---

## Querying the metrics index

### Anatomy of an `mstats` search

```spl
| mstats <agg>("<metric_name>") AS alias
  WHERE `evpn_index` earliest=-7d latest=now
  "cisco.encoding_path"="<yang path in Splunk>"
  "cisco.node_id"="<hostname>"
  BY "<dim1>", "<dim2>"
| `evpn_lookup`
| where ...
```

- **`WHERE`** — index, time range, dimension filters
- **`BY`** — splits series (device, interface, VNI, …)
- **`latest()`** — state / on-change metrics
- **`count()`** — volume / “is anything flowing?” checks

### Discovery (run these first on a new install)

```spl
| mcatalog values(metric_name) WHERE `evpn_index` earliest=-24h latest=now
| head 30
```

```spl
| mcatalog values("cisco.encoding_path") WHERE `evpn_index` earliest=-24h latest=now
```

```spl
| mcatalog values("cisco.node_id") WHERE `evpn_index` earliest=-24h latest=now
```

```spl
| mcatalog values(_dims) AS d
  WHERE `evpn_index` earliest=-24h latest=now
  "cisco.encoding_path"="Cisco-IOS-XE-interfaces-oper:interfaces/interface"
| nomv d
```

### Smoke test (NVE — should return rows on a live fabric)

```spl
| mstats latest("cisco.cp-vnis.") AS vnis
  WHERE `evpn_index` earliest=-15m latest=now
  BY "cisco.node_id"
| `evpn_lookup`
```

### Interface oper-status (subs 40120 / 40121)

Subscriptions **40120** (on-change) and **40121** (periodic 5 min) stream
`Cisco-IOS-XE-interfaces-oper` from all fabric nodes. Verify on device:

```text
show telemetry ietf subscription 40120 detail
show telemetry ietf subscription 40121 detail
```

Splunk queries:

```spl
| mstats latest("cisco.oper-status_info") AS oper
  WHERE `evpn_index` earliest=-7d latest=now
  "cisco.encoding_path"="Cisco-IOS-XE-interfaces-oper:interfaces/interface"
  "cisco.node_id"="Leaf-01"
  BY name, value
| where name IN ("nve1","Nve1") OR like(name, "Tunnel%") OR like(name, "Loopback%")
| table name, value, oper
```

```spl
| mstats count("cisco.oper-status_info") AS points
  WHERE `evpn_index` earliest=-7d latest=now
  "cisco.encoding_path"="Cisco-IOS-XE-interfaces-oper:interfaces/interface"
  BY "cisco.node_id"
| `evpn_lookup`
| sort - points
```

> **40120 is on-change.** If nothing changed recently, widen the time picker to
> `-7d` or `-24h`, or rely on **40121** (periodic) for a baseline snapshot.

### Common `cisco.encoding_path` values (lab fabric)

| Model | `cisco.encoding_path` | Dashboard use |
|---|---|---|
| BGP neighbors | `Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors/neighbor` | Session matrices, hold-time |
| NVE oper | `Cisco-IOS-XE-nve-oper:nve-oper-data/nve-oper` | VTEP peer counts, VNI summary |
| NVE VNI | `Cisco-IOS-XE-nve-oper:nve-oper-data/nve-oper/nve-vni-oper` | Per-VNI state, throughput |
| NVE peers | `Cisco-IOS-XE-nve-oper:nve-oper-data/nve-oper/nve-peer-oper` | Peer adjacency, cp-vnis |
| EVPN inst | `Cisco-IOS-XE-evpn-oper:evpn-oper-data/evpn-inst` | EVI / VLAN binding |
| EVPN stats | `Cisco-IOS-XE-evpn-oper:evpn-oper-data/evpn-stats/evpn-vni-rt-cnt` | Route churn (Sub 40113) |
| **Interfaces** | `Cisco-IOS-XE-interfaces-oper:interfaces/interface` | **40120/40121** oper-status |

Full subscription IDs and device XPaths:
[`model-config-snippets/telemetry-subscriptions.ios-xe.cfg`](../model-config-snippets/telemetry-subscriptions.ios-xe.cfg).

---

## Verifying data after install

Run in **Search & Reporting** (metrics-capable account):

```spl
| rest /services/data/indexes/evpn_assurance
| table title, datatype, currentDBSizeMB, totalEventCount
```

Expect `datatype=metric` and a non-zero event count.

Then confirm live telemetry:

```spl
| mstats latest("cisco.cp-vnis.") AS vnis
  WHERE `evpn_index` earliest=-15m latest=now
  BY "cisco.node_id"
| `evpn_lookup`
```

A populated table confirms metrics are flowing and the lookup is matching.

Collector-side checks (on the OTel host): see
[`otel-collector/README.md`](../otel-collector/README.md).

---

## Troubleshooting empty panels

| Symptom | Likely cause | Fix |
|---|---|---|
| All panels empty | No data in `evpn_assurance` | Check OTel `:57444` sessions, HEC token, device subscriptions |
| `Unauthorized` in Search | User lacks index ACL | Use an admin / metrics-authorized account |
| `mstats` returns nothing | Wrong `cisco.encoding_path` | Run `mcatalog values("cisco.encoding_path")` and copy exact string |
| Interface query empty | Used device XPath instead of encoding path | Use `Cisco-IOS-XE-interfaces-oper:interfaces/interface` |
| Interface query empty (40120 only) | On-change sub, quiet window | Widen to `-7d` or flap an interface; check 40121 |
| `` `evpn_lookup` `` drops rows | `hostname` ≠ `cisco.node_id` | Fix `evpn_device_inventory.csv` |
| Bare `mstats count WHERE index=…` = 0 | Known metrics-index quirk | Filter on a real metric name, e.g. `cisco.cp-vnis.` |
| Details panels empty for a role | Wrong **Fabric Node Role** dropdown | Confirm `role` column in inventory matches `leaf`/`spine`/`border` |

---

## Version

`1.5.0` (build 85). See [`../SETUP_GUIDE.md`](../SETUP_GUIDE.md) for install,
upgrade, and telemetry-pipeline procedures.

---

## Related documentation

| Document | Contents |
|---|---|
| [`../README.md`](../README.md) | Full pipeline architecture, CCIE-oriented telemetry primer, operator guide |
| [`../SETUP_GUIDE.md`](../SETUP_GUIDE.md) | Install app + OTel collector, HEC, subscriptions |
| [`../otel-collector/README.md`](../otel-collector/README.md) | `otelcol-yangfix`, numeric YANG keys, collector troubleshooting |
| [`../model-config-snippets/telemetry-subscriptions.ios-xe.cfg`](../model-config-snippets/telemetry-subscriptions.ios-xe.cfg) | IOS-XE subscription IDs 40101–40121 |
| [`../Model Maps/README.md`](../Model Maps/README.md) | CLI ⇄ Cisco YANG xpath reference (when available locally) |
| [`../images/README.md`](../images/README.md) | Pipeline diagram assets |
