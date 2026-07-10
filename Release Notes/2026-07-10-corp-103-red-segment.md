# Corporate user segment corp-103 (VLAN 103) in red VRF

**Date:** 2026-07-10  
**Branch:** `feature-new-tenant-segments`  
**Templates affected:** `DEFN-OVERLAY.j2`, `DEFN-L3OUT.j2`, `DEFN-CLIENT-PORTS.j2`  
**Lab config affected:** `Node Configs/fabric-dmz/dhcp.cfg`

## Summary

Added a third corporate user overlay segment — **corp-103** — to the existing **red** VRF (901).
The segment follows the established red-tenant addressing convention (VLAN ID = third octet):
**VLAN 103** on **`198.18.103.0/24`**. No new VRF, loopback prefix, or FABRIC template edits
were required; `FABRIC-OVERLAY.j2`, `FABRIC-NVE.j2`, `FABRIC-EVPN.j2`, and related templates
pick up the new VLAN by iterating `DEFN_OVERLAY`.

## Segment definition

| Field | Value |
|-------|-------|
| VLAN | 103 |
| Name | `corp-103` |
| VRF | red (901) |
| Subnet | `198.18.103.0/24` |
| Anycast GW (SVI) | `198.18.103.1/24` |
| Anycast MAC | `0000.0901.0103` |
| L2VNI | 50103 (`50000 + 103`) |
| BUM multicast | `239.190.100.103` |
| DHCP helper (leaf relay) | `198.19.2.78` |

`198.18.100.0/24` remains the per-node **Loopback901** overlay prefix (`DEFN_LOOP_OVERLAY['red']`)
and is not used as a user segment.

## Files changed

| File | Change |
|------|--------|
| [`DEFN-OVERLAY.j2`](../Catalyst%20Center%20Templates/Site%20BGP%20EVPN%20Templates/DEFN-OVERLAY.j2) | Added `'103'` to red `vlan_ids` and `vlans['103']` overlay entry |
| [`DEFN-L3OUT.j2`](../Catalyst%20Center%20Templates/Site%20BGP%20EVPN%20Templates/DEFN-L3OUT.j2) | Added `198.18.103.0/24` to `DEFN_L3OUT_AGGREGATES` for external summary leak to core (ASN 65002) |
| [`DEFN-CLIENT-PORTS.j2`](../Catalyst%20Center%20Templates/Site%20BGP%20EVPN%20Templates/DEFN-CLIENT-PORTS.j2) | Leaf-02 `GigabitEthernet1/0/8` → VLAN 103 (`client-red-05`); Leaf-01 unchanged |
| [`dhcp.cfg`](../Node%20Configs/fabric-dmz/dhcp.cfg) | `red-103` pool + excluded range `.1`–`.200` in vrf red |

Inline comments in each file document the additions and rationale.

## Client port mapping

| Leaf | Port | VLAN | Description |
|------|------|------|-------------|
| Leaf-02 | `GigabitEthernet1/0/8` | 103 | `client-red-05` |

Leaf-02 ports `Gi1/0/3`–`Gi1/0/7` were already assigned. The segment is overlay-wide on both
leaves via EVPN; only Leaf-02 has a lab access port for corp-103.

## DHCP

The dhcp-server (`198.18.128.110`) gains:

```
ip dhcp excluded-address vrf red 198.18.103.1 198.18.103.200
ip dhcp pool red-103
 vrf red
 network 198.18.103.0 255.255.255.0
 default-router 198.18.103.1
 dns-server 8.8.8.8
```

Leaves relay into vrf red toward `198.19.2.78` (existing `Gi2.120` on dhcp-server). No new
interface or static route on the dhcp-server is required.

## Deployment

1. Merge or sync `feature-new-tenant-segments` and run Ansible stage `07_template_sync.yml`.
2. Re-provision fabric devices from Catalyst Center (`BGP-EVPN-BUILD` composite).
3. Apply updated `dhcp.cfg` to the lab dhcp-server (or rebuild CML if using topology YAML).

## Verification

| Check | Command / location |
|-------|-------------------|
| VLAN / SVI | `show vlan id 103`, `show ip int vrf red Vlan103` on Leaf-01/02 |
| EVPN | `show l2vpn evpn mac vni 50103` |
| L3OUT | `show ip bgp vpnv4 vrf red` — aggregate `198.18.103.0/24` on Spine |
| DHCP | Client on Leaf-02 `Gi1/0/8` receives `.201+` from `red-103` pool |

## Optional follow-on (not in this change)

- Add `198.18.103.0/24` to `TENANT_SEGMENTS` on `core01`/`core02` if external routing tests are needed.
- Add `red05` Alpine client on Leaf-02 `Gi1/0/8` in `BGP_EVPN_Campus_v10.yaml` and update embedded dhcp-server bootstrap in CML.
- Update README §5.3 VLAN-to-VNI table and lab topology diagram when corp-103 is deployed live.
