# OTel Collector — Campus BGP EVPN Telemetry Pipeline

This folder holds the source-of-truth mirror of the OpenTelemetry Collector
configuration running on the cloud Splunk/OTel host. The collector ingests Cisco
IOS-XE Model-Driven Telemetry (MDT) over gRPC dial-out and ships it, together
with EC2 host metrics, to the co-located Splunk HEC.

## Contents

| File | Purpose |
|---|---|
| [`agent_config.running.yaml`](agent_config.running.yaml) | Mirror of the live collector config. Edit here, then deploy to the host (see [Installation](#installation)). |
| `README.md` | This document. |

## Overview

```
Cisco fabric switches (6)                 EC2 host 18.224.25.161 (ip-172-31-30-149)
  Spine-01/02, Leaf-01/02,         gRPC   ┌────────────────────────────────────────┐
  Border-01/02                  dial-out  │  splunk-otel-collector.service          │
  (NATed via 64.100.12.5) ───────────────▶│   receiver: yang_grpc  :57444           │
                                          │   receiver: hostmetrics                 │
  device config:                          │   processor: batch                      │
  "receiver ip address                    │   exporter: splunk_hec ──┐              │
   18.224.25.161 57444                     └──────────────────────────┼─────────────┘
   protocol grpc-tcp"                                                 │ https://localhost:8088
                                                                      ▼
                                                        Splunk HEC → index=evpn_assurance (metric)
```

| Item | Value |
|---|---|
| Host | `18.224.25.161` (internal `ip-172-31-30-149.us-east-2.compute.internal`) |
| Active collector binary | `/usr/local/bin/otelcol-yangfix` (custom build with the numeric-key fix — see [Custom collector build & rollback](#custom-collector-build--rollback)) |
| Stock binary (rollback) | `/usr/bin/otelcol` (opentelemetry-collector-contrib, **v0.154.2**, untouched rpm) |
| systemd unit | `splunk-otel-collector.service` (+ drop-in `…/splunk-otel-collector.service.d/override.conf`) |
| Live config path | `/etc/otel/collector/agent_config.yaml` |
| Env file | `/etc/otel/collector/splunk-otel-collector.conf` (`SPLUNK_CONFIG=/etc/otel/collector/agent_config.yaml`) |
| YANG gRPC receiver | `yang_grpc` (patched `yanggrpcreceiver`, build **`26_05_27`**, core v0.150.0) on `0.0.0.0:57444`, transport tcp |
| Exporter | `splunk_hec` → `https://localhost:8088/services/collector` (loopback — EC2 has no hairpin NAT to its own public IP) |
| Target index | `evpn_assurance` (metric) |

## Numeric YANG List Keys — RESOLVED (custom build deployed 2026-06-23)

> **✅ Numeric list keys are now emitted as dimensions.** The earlier limitation
> (numeric YANG list keys silently dropped) is fixed by the patched
> `yanggrpcreceiver` build **`26_05_27`**
> ([`receiver_yang_26_05_27.tar.gz`](receiver_yang_26_05_27.tar.gz)), compiled
> into the custom collector `otelcol-yangfix` now running on the host. Full
> analysis and the resolution mechanism are in
> [`yanggrpcreceiver-numeric-key-issue.md`](yanggrpcreceiver-numeric-key-issue.md).

### The original problem

The `nve-oper-data/nve-oper/nve-peer-oper/peer-vni-group` list is keyed by
`vni` + `evni` (the VNI numbers from `show nve peers`). On Leaf-01 the CLI shows
**10** VNI×peer rows, but with the **stock v0.154.x** receiver these collapsed:
it did not emit `vni`/`evni`, leaving only `peer-addr` + the `rmac`/`_info`
string leaf. Loading the Cisco YANG models via the `yang:` block did **not** fix
it — the conversion path never consulted the parsed schema. Root cause was a
receiver code limitation (numeric leaves were only dimensioned when the protobuf
value was a `StringValue`; keys were also skipped from metric emission).

### How it was fixed

The patched receiver replaces the heuristic with a two-pass converter
(`extractKeysOnly` + `emitMetricsOnly`). `extractKeysOnly` stringifies **every**
leaf under the GPB `keys` branch via `formatValueToString` (handling
`Uint32`/`Uint64`/`Sint32`/`Sint64`), so numeric keys now survive as dimensions.

**Verified live (2026-06-23):** `peer-vni-group` now emits `vni` + `evni` +
`unit-number`; `nve-vni-oper` emits `vni-id`; `nve-vni-oper-counters` emits
`vni-id` (per-VNI throughput now possible). Real values confirmed — Leaf-02
`vni-id` 50101/50201/50221/50901/50902/50903; Leaf-01 `peer-vni-group` `vni`/`evni`
per peer.

### Dimension-model change you must know about

The fix also normalised the dimension model, which changed the attribute contract:

| Element | Stock v0.154.0 | Patched `26_05_27` |
|---|---|---|
| **Numeric list keys** | dropped | promoted to dims: `vni`, `vni-id`, `evni`, `unit-number`, `evpn-inst-id`, `vlan-id`, `evpn-stats-id` |
| **String list keys** (e.g. `peer-addr`) | dim | unchanged — still a dim |
| **String content leaves** (e.g. `vni-type`, `nve-vni-vrf`, `last-update`, `ni-name`) | dim named after the leaf | separate `cisco.<leaf>_info` metric; string carried in a generic **`value`** attribute |

Any query that grouped a numeric metric `BY "<string-content-leaf>"` now returns
**empty** and must be rewritten to group `BY "<numeric-key>"` (e.g. `"vni-id"`)
and pull string attributes from their `cisco.<leaf>_info` metric via the generic
`value` attribute. The Splunk app `campus_evpn_assurance` (v1.3.22 / build 54)
was fully migrated to this model.

### Per-VNI peer mapping — now telemetry-native

The NVE peer Sankey can now be discriminated by the **VNI number** directly:
`peer-vni-group` emits `vni` + `evni` as dimensions, so no `RMAC → VNI` lookup
enrichment is required anymore. (The `rmac` string is still emitted via
`cisco.rmac_info` if you want it.)

## Custom collector build & rollback

The fix ships as a **custom collector binary** (`otelcol-yangfix`) built from the
patched receiver source. The stock Splunk-distro rpm binary at `/usr/bin/otelcol`
is **left untouched**, so rollback is a one-liner.

### How it was built (on the host)

The tarball [`receiver_yang_26_05_27.tar.gz`](receiver_yang_26_05_27.tar.gz) is
receiver **source only** (no binary), and the receiver requires Go 1.25+, so it
was compiled natively on the host (Amazon Linux 2023, x86_64) with the
OpenTelemetry Collector Builder:

- Toolchain: Go 1.26.4 at `/usr/local/go`, `ocb` (collector builder) v0.150.0.
- Build workspace `/tmp/otelbuild`: `builder.yaml` manifest, `src/` (the patched
  receiver), `_build/` output.
- Manifest pins core/contrib to **v0.150.0 / v1.56.0** (matching the receiver's
  `go.mod`) and uses a `replaces:` directive pointing `yanggrpcreceiver` at the
  patched source. Components built in: `hostmetrics`, `yang_grpc`,
  `batchprocessor`, `splunkhecexporter` only.
- Output binary installed at `/usr/local/bin/otelcol-yangfix` (~30 MB, `root:root` 0755).

### How it is wired into systemd (reversible)

The stock unit runs `/usr/bin/otelcol $OTELCOL_OPTIONS` and the Splunk distro
auto-reads `SPLUNK_CONFIG`; a vanilla collector does not, so a **drop-in override**
supplies the config explicitly:

```ini
# /etc/systemd/system/splunk-otel-collector.service.d/override.conf
[Service]
ExecStart=
ExecStart=/usr/local/bin/otelcol-yangfix --config=${SPLUNK_CONFIG}
```

Everything else (User `splunk-otel-collector`, `EnvironmentFile`) is unchanged.
Apply with `sudo systemctl daemon-reload && sudo systemctl restart splunk-otel-collector.service`.

### Backups (on host) — `/opt/otel-backup/2026-06-23/`

| File | What |
|---|---|
| `otelcol.v0.154.2.bak` | original 455 MB rpm Splunk-distro binary (sha256-verified) |
| `agent_config.yaml.bak` | live config at deploy time |
| `splunk-otel-collector.service.bak` | original unit file |
| `splunk-otel-collector.conf.bak` | original env file |

### Rollback to the stock Splunk distro

```bash
sudo rm /etc/systemd/system/splunk-otel-collector.service.d/override.conf
sudo rmdir /etc/systemd/system/splunk-otel-collector.service.d 2>/dev/null
sudo systemctl daemon-reload
sudo systemctl restart splunk-otel-collector.service
# the untouched /usr/bin/otelcol (rpm) runs again — numeric keys revert to dropped.
```

> **Restart gotcha:** the old process does **not** drain its gRPC dial-out
> streams on `SIGTERM`. systemd waits out `TimeoutStopSec` (~90 s), logs
> `Failed with result 'timeout'`, force-kills it, then the new process starts
> cleanly. Expect a **~90 s telemetry gap** on every restart — verify the new
> process logged `Everything is ready` afterwards.

### Verify after any restart

```bash
sudo journalctl -u splunk-otel-collector --since '2 min ago' --no-pager | grep 'Everything is ready'
ss -tnp | grep ':57444' | wc -l    # expect 6 (all fabric devices reconnected)
curl -s localhost:8888/metrics | grep otelcol_exporter_send_failed_metric_points   # expect 0 / absent
```

Confirm numeric keys are present in Splunk (admin account required — the legacy
`cisco` user has no index ACL):

```bash
curl -sk -u '***REMOVED***:<password>' \
  'https://localhost:8089/servicesNS/nobody/campus_evpn_assurance/search/jobs/export' \
  --data-urlencode 'search=| mcatalog values(_dims) AS d WHERE index=evpn_assurance "cisco.encoding_path"="Cisco-IOS-XE-nve-oper:nve-oper-data/nve-oper/nve-peer-oper/peer-vni-group" earliest=-3m latest=now | nomv d' \
  --data-urlencode 'output_mode=csv'
```

Expected dims now **include** `vni` and `evni` (in addition to
`cisco.node_id node_id peer-addr value`), confirming the fix is live.

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| `is-active` stuck `deactivating (stop-sigterm)` after restart | gRPC dial-out streams not draining on SIGTERM | Wait ~90 s for systemd `TimeoutStopSec` to force-kill; the new process then starts. Don't keep restarting. |
| No data in `evpn_assurance` after restart | Devices not yet reconnected, or HEC (`:8088`) was down | Check `ss -tnp | grep 57444` for 6 ESTAB streams; check `ss -tlnp | grep 8088`; check `otelcol_exporter_send_failed_metric_points` at `http://localhost:8888/metrics`. |
| `| mstats count WHERE index=evpn_assurance` returns 0 | Bare `count` with no `metric_name` filter is a known quirk on this metric index | Use a real metric, e.g. `mstats latest("cisco.cp-vnis.") BY "cisco.node_id"`. |
| Panels grouped `BY "vni-type"`/`"nve-vni-vrf"`/`"last-update"`/`"ni-name"` return empty | Those string content leaves are no longer dimensions under the patched receiver — they are now `cisco.<leaf>_info` metrics with the string in the generic `value` attribute | Rewrite to group `BY "<numeric-key>"` (e.g. `"vni-id"`, `"vni"`) and join the `_info` metric on that key. The app v1.3.22/build 54 already does this. |
| `vni`/`evni` missing on `peer-vni-group` | Running the **stock** `/usr/bin/otelcol` (rollback state) — it drops numeric list keys | Confirm `otelcol-yangfix` is active (`systemctl show -p ExecStart splunk-otel-collector`); if rolled back, re-apply the drop-in override (see [Custom collector build & rollback](#custom-collector-build--rollback)). |

## Reference

- Receiver source / config: `opentelemetry-collector-contrib/receiver/yanggrpcreceiver`
  ([config.go](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/receiver/yanggrpcreceiver/config.go),
  [README](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/yanggrpcreceiver))
- Cisco IOS-XE YANG models: [`YangModels/yang` → `vendor/cisco/xe/2611`](https://github.com/YangModels/yang/tree/main/vendor/cisco/xe/2611)
- NVE model: `Cisco-IOS-XE-nve-oper.yang` (revision 2025-07-01, module-version 1.1.0 — the revision that added the `peer-vni-group` container).
