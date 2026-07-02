# Splunk Assurance — Device × Peer Matrices: Map External (Core / DMZ) eBGP Peers

## Summary

The **BGP Session Health Matrix — Device × Peer** (executive overview) and the
**Per-VNI Peer Reachability Matrix per Spine** (spines view) were rendering several
peer columns as raw `198.19.x.x` IP addresses instead of friendly device names.
The affected columns were the fabric's **external eBGP peers** — the DMZ gateway and
the two upstream enterprise core routers — which were absent from the Splunk device
inventory lookup.

## Root Cause

Both matrices resolve a peer's IP to a hostname with an inline reverse lookup:

```spl
| lookup evpn_device_inventory loopback AS "peer-addr" OUTPUT hostname AS peer_name
| eval peer_name=coalesce(peer_name, 'peer-addr')
```

Any peer IP that is **not** present in the lookup's `loopback` column falls through the
`coalesce()` and is displayed as the raw neighbour IP. The packaged
`evpn_device_inventory.csv` only contained the six streaming fabric switches
(`198.19.1.1`–`198.19.1.6`), so these external neighbours never resolved:

| Peer IP | Belongs to | Seen from |
|---|---|---|
| `198.19.1.200` | dmz1 (DMZ gateway, overlay identity Lo0) | Border-01, Border-02 |
| `198.19.2.49` | Core-01 (Spine-01 uplink1) | Spine-01 |
| `198.19.2.57` | Core-01 (Spine-02 uplink1) | Spine-02 |
| `198.19.2.53` | Core-02 (Spine-01 uplink2) | Spine-01 |
| `198.19.2.61` | Core-02 (Spine-02 uplink2) | Spine-02 |

- The DMZ neighbour IP `198.19.1.200` is `DEFN_LOOP_MCLUSTER['dmz1...']['ip']`, configured
  by `FABRIC-EVPN.j2` as `neighbor 198.19.1.200 remote-as 65003` on both Borders.
- The core neighbour IPs are the L3OUT `/30` P2P addresses from `DEFN-L3OUT.j2`; the
  Core-01/Core-02 ownership was confirmed against the reference core configs
  (`Node Configs/Config-Backup-20260508-131703/Core-01.cfg` / `Core-02.cfg`).

## Fix

Added five external-peer rows to
`Campus BGP EVPN Splunk Assurance/campus_evpn_assurance/lookups/evpn_device_inventory.csv`,
one per peer link IP, using distinct roles (`dmz`, `core`) so they never collide with the
`spine`/`leaf`/`border` role filters used by the per-role panels:

```csv
dmz1.dcloud.cisco.com,dmz1,198.19.1.200,198.19.1.200,Building P0,dmz,DMZ Gateway (external eBGP EVPN peer)
Core-01,Core-01,198.19.2.49,198.19.2.49,Building P0,core,Enterprise Core 01 (Spine-01 uplink1)
Core-01,Core-01,198.19.2.57,198.19.2.57,Building P0,core,Enterprise Core 01 (Spine-02 uplink1)
Core-02,Core-02,198.19.2.53,198.19.2.53,Building P0,core,Enterprise Core 02 (Spine-01 uplink2)
Core-02,Core-02,198.19.2.61,198.19.2.61,Building P0,core,Enterprise Core 02 (Spine-02 uplink2)
```

Core-01 and Core-02 each get two rows (one per uplink IP) that share the same `hostname`,
so the matrix collapses each core's two peer links into a single named column.

## Why This Is Safe

- The peer-resolution lookup keys only on `loopback` → outputs `hostname`; each new row has a
  unique `loopback`, so there is no ambiguity.
- The `evpn_lookup` macro (used by the per-role panels) keys on `hostname` against streaming
  `cisco.node_id` telemetry. The external peers do **not** stream telemetry, so they never match
  there and cannot appear as phantom fabric devices in role-scoped panels.
- No panel enumerates the lookup as an "expected devices" list; the only `inputlookup` usage is
  the Site dropdown (`stats count by site`), which is unaffected (`site = Building P0` for all rows).
- Result: rows are unchanged; only previously-raw peer **columns** now resolve to `dmz1`,
  `Core-01`, and `Core-02`.

## Affected Files

| File | Change |
|---|---|
| `Campus BGP EVPN Splunk Assurance/campus_evpn_assurance/lookups/evpn_device_inventory.csv` | Added 5 external-peer rows (dmz1, Core-01 ×2, Core-02 ×2) |
| `Campus BGP EVPN Splunk Assurance/SETUP_GUIDE.md` | Documented how/why to map external core/DMZ eBGP peers in the lookup |

## Operational Impact

- After the lookup is re-uploaded (Settings → Lookups → Lookup table files, or reinstall the
  app package), the **Device × Peer** matrices show `dmz1`, `Core-01`, and `Core-02` instead of
  raw `198.19.x.x` IPs. No switch/template configuration change is required.
- When the fabric's external topology changes (new core link, new DMZ), add/adjust the
  corresponding row(s) in the lookup — no dashboard edits are needed.

## Validation

- Confirmed the DMZ neighbour IP in `FABRIC-EVPN.j2` (`neighbor {{DEFN_LOOP_MCLUSTER[remote]['ip']}}`
  → `198.19.1.200`) and `DEFN-LOOPBACKS.j2` (`DEFN_LOOP_MCLUSTER['dmz1.dcloud.cisco.com'].ip`).
- Confirmed core neighbour IPs and Core-01/Core-02 ownership in `DEFN-L3OUT.j2` and the reference
  `Core-01.cfg` / `Core-02.cfg` (`198.19.2.49`+`.57` = Core-01; `198.19.2.53`+`.61` = Core-02).
- Verified the resolution SPL in `executive_overview.xml` (`ds` for "BGP Session Health Matrix")
  and `spines.xml` (`ds_spines_16`).
