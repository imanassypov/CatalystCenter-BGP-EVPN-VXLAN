# 2026-09-01 — dmz2 Bidirectional EVPN: Border Shared-RT Import + Tenant Defaults

## Summary

Multi-cluster EVPN sessions to `dmz2` (ASN 65004) were Established, and campus Type-5
reached both DMZ sites, but **dmz2 prefixes were not installed on campus**
(`State/PfxRcd = 0` toward `198.19.2.200`). Two independent gaps combined:

1. **Campus import.** After `rewrite-evpn-rt-asn`, dmz2's only advertised Type-5
   (`RD 172.18.200.2:1000`, RT `65004:1000`) becomes `65001:1000`. Campus tenant
   VRFs imported only `:902` / `:903`.
2. **dmz2 origin.** CML day-0 for `dmz2` had `default-information originate` in
   blue/green but no matching static defaults, so it never originated tenant Type-5
   the way `dmz1` does.

This is **not** a campus inbound `EVPN-TYPE5-ONLY` filter. That route-map lives on
the DMZ devices and only permits EVPN route-type 5. Campus
`OVERLAY-DMZ-EVPN-PEER-POLICY` has no inbound map.

## Changes

### 1. Campus templates — border-only extra RT import

| File | Change |
|------|--------|
| `DEFN-VRF.j2` | `DEFN_VRF_BORDER_IMPORT_RTS = ['1000']` |
| `FABRIC-VRF.j2` | Include `DEFN-ROLES` + `DEFN-BORDER-DMZ-TUNNELS`; on BORDER when `DEFN_TUNNELS` is set, emit `route-target import 65001:1000` and the stitching variant into each tenant VRF |

Shared stays at the DMZ/firewall. No campus `shared` VRF or L3VNI. Leaves and
spines do not import `:1000`.

### 2. dmz2 day-0 origin (CML v10)

Aligned with `Node Configs/fabric-dmz/dmz02.cfg`:

```
ip route vrf blue 0.0.0.0 0.0.0.0 198.19.2.94
ip route vrf green 0.0.0.0 0.0.0.0 198.19.2.94
ip route vrf shared 0.0.0.0 0.0.0.0 198.19.2.94
```

`DMZ-policy-out` (`as-path _$`) is unchanged so DMZ sites do not re-advertise
campus prefixes back into the fabric.

## Validation

- Border `show bgp l2vpn evpn summary`: `198.19.2.200` **PfxRcd > 0**
- `show vrf detail blue | include 1000` on borders: import `65001:1000` (stitching)
- `show ip route vrf blue 198.19.2.92` (and green) on borders and Leaf-01
- After dmz2 defaults: `advertised-routes` toward `10.101.1.2` include Type-5 902/903
