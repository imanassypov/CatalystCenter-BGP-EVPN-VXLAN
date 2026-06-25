# yanggrpcreceiver — numeric YANG list keys are dropped (not emitted as dimensions or metrics)

> **✅ RESOLVED** — Fixed in receiver build `receiver_yang_26_05_27` (tracked in
> [`receiver_yang_26_05_27.tar.gz`](receiver_yang_26_05_27.tar.gz)), built into the
> custom collector `otelcol-yangfix` and **deployed live on 2026-06-23**. Numeric
> list keys (`vni`, `vni-id`, `evni`, `unit-number`, `evpn-inst-id`, `vlan-id`,
> `evpn-stats-id`) are now promoted to dimensions. The fix corresponds to
> **Option A** below (`extractKeysOnly` stringifies every leaf under the `keys`
> branch via `formatValueToString`, regardless of value type). See
> [Resolution](#resolution) at the end of this document for the deployed mechanism,
> the resulting dimension-model change, and the dashboard impact. The body below is
> retained as the original problem analysis (pre-fix, v0.154.0).

**Component:** `receiver/yanggrpcreceiver`
**Collector:** opentelemetry-collector-contrib `otelcol` **v0.154.2** (receiver pkg **v0.154.0**)
**Date observed:** 2026-06-22
**Date resolved:** 2026-06-23 (build `receiver_yang_26_05_27`)
**Severity:** functional limitation — telemetry rows are silently collapsed/lost
**Reporter context:** Cisco IOS-XE EVPN/VXLAN fabric → gRPC dial-out (KV-GPB) → `yang_grpc` → `splunk_hec`

---

## Summary

When a Cisco YANG list is keyed by a **numeric** leaf (e.g. `uint32`), the
receiver does **not** emit that key as a metric dimension, and also does not emit
it as a metric value. As a result every distinct list entry that differs *only*
by its numeric key collapses into a single series, and the key value is lost
entirely. Loading YANG models via the `yang:` block (`enable_rfc_parser: true`,
`module_paths: [...]`) does **not** change this — the metric-conversion path
never consults the parsed schema.

The concrete data loss in our deployment: `show nve peers` on one leaf has 10
VNI×peer rows; the receiver emits only the peer-level distinctions and drops the
VNI number, so the per-VNI rows are indistinguishable downstream.

---

## Environment

| Item | Value |
|---|---|
| Binary | `/usr/bin/otelcol` v0.154.2 (statically linked, contrib distro) |
| Receiver package | `yanggrpcreceiver` v0.154.0 |
| Source device | Cisco CAT9KV, IOS-XE 26.x, gRPC dial-out (`grpc-tcp`), KV-GPB encoding |
| Receiver config | `yang_grpc` on `0.0.0.0:57444`, `enable_rfc_parser: true`, `cache_modules: true`, `module_paths: ["/etc/otel/yang/cisco"]` |
| Models loaded | `Cisco-IOS-XE-nve-oper.yang` + closure (`ietf-inet-types`, `ietf-yang-types`, `cisco-semver`) from YangModels/yang `vendor/cisco/xe/2611` |
| Startup log | `Loaded 4 builtin YANG modules` / `Loading YANG modules from path {"path":"/etc/otel/yang/cisco"}` — parsing succeeds |

---

## The data model

`Cisco-IOS-XE-nve-oper.yang` (revision 2025-07-01, module-version 1.1.0):

```yang
grouping peer-vni-group-key {
  leaf vni  { type uint32; description "Virtual Network Interface"; }
  leaf evni { type uint32; description "Egress Virtual Network Interface"; }
}
grouping peer-vni-group-data {
  leaf rmac { type yang:mac-address; description "Router MAC address"; }
}
grouping nve-peer-oper {
  leaf peer-addr { type inet:ip-address; }
  ...
  list peer-vni-group {
    key "vni evni";                 // ← list keyed by TWO numeric (uint32) leaves
    uses peer-vni-group-key;
    uses peer-vni-group-data;
  }
}
```

So for one peer there are N `peer-vni-group` entries, each uniquely identified by
`(vni, evni)`, each carrying a string `rmac`.

---

## Expected behaviour

Each `peer-vni-group` list entry should produce a series carrying its list keys
as attributes, e.g.:

```
metric: cisco.rmac_info  value=1
attrs:  cisco.node_id=Leaf-01  peer-addr=198.19.1.4  vni=50901  evni=50901  value=<rmac>
```

i.e. `vni` and `evni` present as dimensions, so the N entries per peer are
distinguishable.

## Observed behaviour

The only attributes emitted on this path are:

```
cisco.encoding_path  cisco.node_id  node_id  peer-addr  rmac  value
```

`vni` and `evni` are **absent**. The metric is `cisco.rmac_info` (=1) with the
RMAC string carried in both `rmac` and `value`. The N per-peer entries are only
distinguishable by their RMAC, never by the VNI numbers that key the list.
Enabling/disabling the YANG `module_paths` makes no difference to the output.

---

## Root cause (from v0.154.0 source)

The conversion in `grpc_service.go` is a two-pass, schema-independent heuristic.

### 1. Dimension extraction is gated on the protobuf value being a *string*

```go
// extractKeys recursively scans for string values that serve as identifiers.
func (s *grpcService) extractKeys(field *pb.TelemetryField, ctxBag map[string]string) {
    val := formatValueToString(field)
    if val != "" {
        // If it's a string value, it's likely a dimension/tag.
        if _, ok := field.ValueByType.(*pb.TelemetryField_StringValue); ok {
            ctxBag[field.Name] = val
            lowName := strings.ToLower(field.Name)
            if lowName == "name" || lowName == "interface-name" {
                ctxBag["interface"] = val
            }
        }
    }
    for _, child := range field.Fields {
        s.extractKeys(child, ctxBag)
    }
}
```

`vni`/`evni` arrive as `TelemetryField_Uint32Value`, so the
`*pb.TelemetryField_StringValue` type assertion is false and they are never
added to `ctxBag`. Only **string-typed** leaves become dimensions. (Note
`formatValueToString` *can* stringify uint32, but the subsequent type assertion
restricts dimensioning to strings only.)

### 2. As list keys, they are also excluded from metric emission

```go
func (s *grpcService) emitMetrics(...) {
    ...
    // Only emit metrics for leaf nodes (values) that are NOT in the 'keys' branch.
    if field.ValueByType != nil && len(field.Fields) == 0 &&
       !strings.HasPrefix(currentPath, "keys") {
        ...
    }
}
```

In Cisco KV-GPB the list-key leaves are delivered under the `keys` sub-branch
(payload values under `content`). The `!strings.HasPrefix(currentPath, "keys")`
guard means key leaves are intentionally skipped as metric values too.

→ Numeric list keys fall through **both** paths: not a string → not a dimension;
under `keys` → not a value. They are dropped completely.

### 3. The parsed YANG schema is not consulted on the hot path

```go
// emitMetrics → numeric branch:
createNumericMetric(m, cleanName, getNumericValue(field), timestamp, nil, ctxBag)
//                                                                    ^^^ yType = nil
```

The only consumer of YANG type info, `createNumericMetric`'s `yType
*internal.YANGDataType` (used for `IsCounterType()` sum-vs-gauge selection), is
passed `nil`. So even with `module_paths` loaded, the schema has **no effect** on
emitted metrics — confirming this is not a missing-models problem but a
conversion-logic limitation.

---

## Minimal reproduction

1. Stream any Cisco IOS-XE list keyed by a numeric leaf via gRPC dial-out, e.g.
   `Cisco-IOS-XE-nve-oper:nve-oper-data/nve-oper/nve-peer-oper/peer-vni-group`
   (`key "vni evni"`), with multiple entries per parent that differ only by `vni`.
2. Configure `yang_grpc` with the models loaded:
   ```yaml
   yang_grpc:
     endpoint: "0.0.0.0:57444"
     yang:
       enable_rfc_parser: true
       module_paths: ["/etc/otel/yang/cisco"]
   ```
3. Inspect the emitted attributes (e.g. in Splunk:
   `| mcatalog values(_dims) WHERE "cisco.encoding_path"="...peer-vni-group"`).

**Observed:** `vni`/`evni` absent from attributes; entries collapse.
**Expected:** `vni`/`evni` present as attributes; one series per list entry.

---

## Suggested fix

Capture list-key leaves as dimensions regardless of value type. Two minimal options:

**Option A — stringify any key leaf in `extractKeys`** (drop the string-only gate
for fields under the `keys` branch):

```go
func (s *grpcService) extractKeys(field *pb.TelemetryField, ctxBag map[string]string, underKeys bool) {
    val := formatValueToString(field)   // already handles uint32/uint64/sint32/sint64
    if val != "" {
        _, isStr := field.ValueByType.(*pb.TelemetryField_StringValue)
        if isStr || underKeys {         // ← keys become dimensions even when numeric
            ctxBag[field.Name] = val
        }
        ...
    }
    for _, child := range field.Fields {
        s.extractKeys(child, ctxBag, underKeys || field.Name == "keys")
    }
}
```

**Option B — schema-aware:** use the loaded YANG model to identify `list ... key
"..."` leaves and always promote them to dimensions (also lets `yType` flow into
`createNumericMetric` for correct counter/gauge typing, which is currently
`nil`). This additionally fixes the unused-schema issue in §3.

Either way, numeric list keys must survive as attributes so list entries remain
distinguishable downstream.

---

## Impact

- Any IOS-XE path with numeric list keys loses key cardinality. Beyond NVE
  `peer-vni-group`, this affects e.g. VNI-keyed and ID-keyed lists broadly.
- Data is **silently** collapsed (no error/warn), so dashboards under-report
  without any signal that rows were merged.
- The `yang:` model-loading feature appears to work (parse succeeds, log
  confirms) but has no observable effect on output for this class of data,
  which is misleading.

---

## Notes / questions for the team

- Is the `keys`-branch exclusion in `emitMetrics` intended to also suppress keys
  as *dimensions*, or only as *values*? The current code does both.
- Is there a planned path for `yType` to reach `createNumericMetric` (it is `nil`
  today), i.e. is schema-driven counter/gauge typing expected to be wired in?
- Would a PR implementing Option A (with the `keys`-branch awareness) be welcome,
  or is Option B (full schema-driven dimensioning) the preferred direction?

---

## Resolution

**Build:** `receiver_yang_26_05_27` ([`receiver_yang_26_05_27.tar.gz`](receiver_yang_26_05_27.tar.gz))
**Deployed:** 2026-06-23 as custom collector `otelcol-yangfix` (see
[`README.md`](README.md) → *Custom collector build* for the build + rollback procedure).

### What the fix does

The new `grpc_service.go` replaces the single-pass heuristic with a clean
two-pass converter:

1. **`extractKeysOnly(field, ctxBag)`** recursively descends into the GPB `keys`
   sub-branch and stringifies **every** child via `formatValueToString` —
   `Uint32Value` / `Uint64Value` / `Sint32Value` / `Sint64Value` are formatted
   with `strconv.FormatUint` / `FormatInt`. There is no longer a
   `*StringValue`-only type gate, so numeric keys survive (this is **Option A**
   from the suggested fix above). `applyCtxBag` then attaches every key as a
   dimension to every data point under that list entry.
2. **`emitMetricsOnly`** walks the `content` branch only: numeric leaves become
   `cisco.<path>` Gauges; string leaves become `cisco.<path>_info` (value `1`).

### Resulting dimension-model change (IMPORTANT)

The fix also **normalised the whole dimension model**, which changed the
attribute contract for existing dashboards:

| Element | Old receiver (v0.154.0) | New receiver (`26_05_27`) |
|---|---|---|
| **Numeric list keys** | dropped | promoted to named dims: `vni`, `vni-id`, `evni`, `unit-number`, `evpn-inst-id`, `vlan-id`, `evpn-stats-id` |
| **String list keys** | named dim (e.g. `peer-addr`) | unchanged — still a named dim |
| **String content leaves** | named dim matching the leaf (e.g. `vni-type`, `nve-vni-vrf`, `last-update`, `ni-name`) | separate `cisco.<leaf>_info` metric; the string is carried in a **generic `value`** attribute (not a dim named after the leaf) |

**Consequence:** any query that grouped a numeric metric `BY "<string-content-leaf>"`
(e.g. `BY "vni-type", "nve-vni-vrf"`) now returns **empty** — those leaves are no
longer dimensions. Such queries must be rewritten to:

- group `BY "<numeric-key>"` (e.g. `"vni-id"`, `"vni"`) — the new join key, and
- pull each string attribute from its `cisco.<leaf>_info` metric via the generic
  `value` attribute (append / `stats values(...) BY "<key>"` to correlate
  multiple `_info` attributes — two `_info` metrics cannot share one `mstats`
  because they collide on `value`).

### Validation (live, 6-device fabric, 2026-06-23)

- `nve-vni-oper` now emits `vni-id`; `peer-vni-group` emits `vni` + `evni`;
  `nve-vni-oper-counters` emits `vni-id` (per-VNI throughput now possible).
- All 21 000 metric points/interval exported to `splunk_hec` with zero failures.
- Real key values confirmed (e.g. Leaf-02 `vni-id` 50101/50201/50221/50901/50902/50903).

### Dashboard migration

The Splunk app `campus_evpn_assurance` (v1.3.16 / build 48) was fully migrated to
the new model — ~16 panels across all 5 dashboards were rewritten to key on
`vni-id` / `vni` and to join `_info` metrics via the generic `value` attribute. A
new **per-VNI VXLAN throughput** panel (leafs) was added, using
`nve-vni-oper-counters BY "vni-id"` — a breakout that was impossible before the
fix.
