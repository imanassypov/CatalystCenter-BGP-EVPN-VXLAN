# 2026-07-02 — EVPN Fabric Layered Data-Model Diagram (draw.io)

## What changed

Rebuilt the **§10.1 "CLI Dependency Hierarchy"** data-model diagram in the root
[`README.md`](../README.md) from scratch in draw.io for a CCIE-level audience, replacing the
stale hand-drawn `cisco_evpn_CLI_hierarchy.png`.

- New source: [`DIAGRAMS/cisco_evpn_data_model.drawio`](../DIAGRAMS/cisco_evpn_data_model.drawio)
- New rendering: `DIAGRAMS/cisco_evpn_data_model.png` (2645×1770, ~850 KB — GitHub-safe)
- Replaced the §10.1 image reference and added a `.drawio` source link
- Deleted the orphaned stale `DIAGRAMS/cisco_evpn_CLI_hierarchy.png`

## Motivation

The diagram visualizes how the three fabric planes (underlay reachability, EVPN/MVPN control-plane
signaling, and VXLAN overlay encapsulation) map to the concrete IOS-XE CLI a leaf renders. The
previous hand-drawn version contained multiple stale values predating current template state. All
values were re-verified against the live templates.

## Corrected values (vs. the earlier hand-drawn diagram)

| Object | Stale value | Corrected value | Source |
|---|---|---|---|
| red L2VNI (VLAN 101) | `member vni 10101 mcast 239.190.100.11` | `member vni 50101 mcast-group 239.190.100.101` | `DEFN-OVERLAY.j2`, `DEFN-VNIOFFSETS.j2` (L2VNIOFFSET=50000) |
| red L2VNI (VLAN 102) | `10102` | `member vni 50102 mcast-group 239.190.100.102` | `DEFN-OVERLAY.j2` |
| blue L2 service | VLAN 401 / VNI 10401 | **VLAN 201** / `member vni 50201 mcast-group 239.190.100.201` | `DEFN-OVERLAY.j2` |
| green L2 service | VLAN 501 / VNI 10501 | **VLAN 221** / `member vni 50221 mcast-group 239.190.100.221` | `DEFN-OVERLAY.j2` |
| L3VNI (red/blue/green) | — | `50901` / `50902` / `50903` (L3VNIOFFSET `50` + VRF-ID) | `FABRIC-NVE.j2` |
| RD | `172.16.255.x:901` | `198.19.1.3:901` (Leaf-01 Lo0 : VRF-ID) | `FABRIC-VRF.j2`, `DEFN-LOOPBACKS.j2` |
| green VRF card label | mislabeled `vrf definition blue` | `vrf definition green` | `DEFN-VRF.j2` |
| red SVI DHCP relay source | `Loopback902` on Vlan102 | `Loopback901` (VRF-ID loopback) on both red SVIs | `FABRIC-OVERLAY.j2` |

## Authoritative data (verified from templates)

- **VNI math**: L2VNI = `50000 + VLAN-ID`; L3VNI = `50 + VRF-ID` (string concat)
- **RD** = `<node Lo0>:<VRF-ID>` (per-device); **RT** = `65001:<VRF-ID>` (fabric-wide, incl. `stitching`)
- **VRFs**: red=901 (mdt default 239.190.0.1 / data 239.190.1.0), blue=902 (239.190.0.2 / 239.190.2.0),
  green=903 (239.190.0.3 / 239.190.3.0)
- **MAC / SVI**: 101→`0000.0901.0101`, 102→`0000.0901.0102`, 201→`0000.0902.0201`, 221→`0000.0903.0221`
- **Role scope**: leaves render L3VNI + L2VNI; spines/borders render **L3VNI only** (VRF route-leak),
  no L2VPN EVPN instances / VLAN configs / anycast SVIs

## Regenerating the diagram

```bash
cd DIAGRAMS
/opt/homebrew/bin/drawio -x -f png --scale 1.6 -o cisco_evpn_data_model.png cisco_evpn_data_model.drawio
/usr/bin/sips -g pixelWidth -g pixelHeight cisco_evpn_data_model.png   # verify ≤ 4000 px
ls -lh cisco_evpn_data_model.png                                       # verify ≤ 1.2 MB
```

> Do **not** run `sips -Z 4000` on this file — the canvas renders below 4000 px at scale 1.6, so
> `-Z` would upscale and inflate the PNG past the 1.2 MB GitHub limit.

## Operational impact

Documentation only. No template, config, or provisioning behavior changed.

## Known stale artifacts (out of scope — flagged, not fixed here)

- `DEFN-VNIOFFSETS.j2` inline comments still reference the legacy `10XXX` L2VNI scheme while the
  `{% set %}` value is authoritatively `50000`.
- `.github/copilot-instructions.md` still states `L2VNI: 10000 + vlan_id`.
- `Node Configs/fabric-site1/` rendered configs predate the 50000 offset and the VLAN 202→221 change.
