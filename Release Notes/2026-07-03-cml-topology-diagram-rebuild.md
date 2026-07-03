# CML Lab Topology Diagram — Rebuilt as drawio Source (§1.2)

**Date:** 2026-07-03

## Summary

Rebuilt the §1.2 **CML Lab Topology** figure (`DIAGRAMS/cisco_evpn_cml.png`) from a raw
Cisco Modeling Labs screenshot into a clean, versioned draw.io source
(`DIAGRAMS/cisco_evpn_cml.drawio`), aligned to the current lab build and to README §1.1.

## Motivation

- The previous `cisco_evpn_cml.png` was a dark-theme CML screenshot with no editable source,
  and it still showed the removed `leaf03` and a single `dmz01`.
- The updated lab adds a second DMZ gateway (`dmz2`, ASN 65004) in a separate physical
  location, an Enterprise Core Anycast RP, a shared-services firewall, and per-tenant
  client/DHCP hosts — none of which were captured in the old image.
- Every other architecture figure in `DIAGRAMS/` ships a `.drawio`/`.mmd` source; the CML
  diagram was the outlier.

## What Changed

| File | Change |
|------|--------|
| `DIAGRAMS/cisco_evpn_cml.drawio` | **New** draw.io source for the CML lab topology |
| `DIAGRAMS/cisco_evpn_cml.png` | Re-rendered from the new source (2645×2505, ~0.7 MB) |
| `README.md` §1.1 | Core-01/Core-02 rows now list `Lo2 = 198.19.1.254/32 (Enterprise Anycast RP)` |
| `README.md` §1.2 | Added `Diagram source` link + prose describing the surrounding services/addressing |

## Topology Captured

- **Shared services**: `FW-SHARED-SERVICES` fronting `vrf-blue` and `vrf-green` with
  location-unique subnets per DMZ (`dmz1`: green `198.18.143.x` / blue `198.18.144.x`;
  `dmz2`: green `198.18.145.x` / blue `198.18.146.x`)
- **DMZ**: `dmz1` (65003, `Lo0 198.19.1.200`, Location A) and `dmz2` (65004,
  `Lo0 198.19.2.200`, Location B), each extending the same `vrf blue` + `vrf green` over
  EVPN; border↔DMZ EVPN over GRE overlay
- **Enterprise Core** (ASN 65002): `core1`/`core2`, Enterprise Anycast RP `Lo2 198.19.1.254`
- **DHCP**: `dhcp-server` per-DMZ scopes — `dmz1` green `198.18.143.100` / blue
  `198.18.144.100`; `dmz2` green `198.18.145.100` / blue `198.18.146.100`; plus underlay
  `198.19.2.78`
- **cp-border / spines** (ASN 65001): `spine1`/`spine2` route reflectors, Fabric Anycast RP
  `Lo2 198.19.1.100`
- **Campus Fabric** (ASN 65001): `leaf1`/`leaf2` edge nodes, `border1`/`border2` (IPSEC)
- **Tenants**: red (`red01`–`red04`, VLAN 101/102, `198.18.101/102.x`), blue (`blue01`–`blue03`,
  VLAN 201, `198.18.201.x`), green (`green01`–`green03`, VLAN 221, `198.18.221.x`)

## Regenerating

```bash
cd DIAGRAMS
drawio -x -f png --scale 2 -o cisco_evpn_cml.png cisco_evpn_cml.drawio
sips -Z 4000 cisco_evpn_cml.png --out cisco_evpn_cml.png   # enforce ≤4000 px / ≤1.2 MB
```

## Operational Impact

Documentation only — no template, playbook, or device-config changes.
