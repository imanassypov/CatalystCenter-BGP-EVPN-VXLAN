# dmz2 Second DMZ Gateway — Underlay Addressing + Reference Config

**Date:** 2026-07-03

## Summary

Added a second DMZ gateway, `dmz2` (ASN 65004), in a geographically separate DMZ location
(Location B). `dmz2` mirrors `dmz1`'s EVPN role — extending `vrf blue` and `vrf green` from
the campus fabric — but uses **fully non-overlapping** underlay link addressing and
**location-unique** tenant-facing shared-services subnets so the two DMZs can coexist while
peering the same Borders and the same enterprise core/DHCP nodes.

## Deployment Status (2026-07-03)

**Stage 1 — physical interface addressing: DEPLOYED & VERIFIED** on the live lab devices
(pushed via netmiko over the mgmt network, saved to startup):

| Device | Interfaces applied | Verification |
|--------|--------------------|--------------|
| `core1` (`.108`) | `Eth1/6` `198.19.2.85/30` → dmz2 | `core1→198.19.2.86` 100% |
| `core2` (`.109`) | `Eth1/6` `198.19.2.89/30` → dmz2 | `core2→198.19.2.90` 100% |
| `dhcp` (`.110`) | `Gi3` (no shut), `Gi3.101` green `198.18.145.100/24`, `Gi3.111` blue `198.18.146.100/24` | all `up/up` |
| `dmz2` (`.114`) | `ip routing`; `Lo0 198.19.2.200/32`; `Gi1/0/1 198.19.2.86/30` (core1); `Gi1/0/2 198.19.2.90/30` (core2); `Gi1/0/3 198.19.2.93/30` (vrf shared, FW); `Gi1/0/5` dhcp trunk vlan 101,111 | `dmz2→198.19.2.85` & `→198.19.2.89` 100% (5/5) |

> A minimal `vrf definition shared` was created on `dmz2` as a prerequisite for the FW-facing
> `Gi1/0/3` interface (RD/RT/EVPN come in the VRF stage). The FW-side link (`198.19.2.94`) is not
> yet reachable — the `fw-shared-services` device's dmz2-facing interface is a later stage.
> Remaining stages (VRFs/RD-RT, SVIs + L2VNI, NVE, BGP overlay + core/DMZ loopback peering) are
> pending.

**Stage 2 — VRF definitions (RD / RT / MDT): DEPLOYED & VERIFIED** on `dmz2`:

| VRF | RD | Route-Targets | MDT (TRM) |
|-----|-----|---------------|-----------|
| `blue` | `172.18.200.2:902` | exp/imp `65004:902` (+ stitching), imp `65004:1000` | default `239.190.0.2`, data `239.190.2.0/24` |
| `green` | `172.18.200.2:903` | exp/imp `65004:903` (+ stitching), imp `65004:1000` | default `239.190.0.3`, data `239.190.3.0/24` |
| `shared` | `172.18.200.2:1000` | exp `65004:1000`, imp `65004:902` + `65004:903`; route-replicate from blue/green | — |

> MDT groups are per-VRF fabric-wide (identical to `dmz1`); only the RD base (`172.18.200.2`) and
> RT ASN (`65004`) differ from `dmz1`. `Gi1/0/3` retained its `198.19.2.93` address in `vrf shared`
> after the `rd` was added (verified). Remaining stages (SVIs + L2VNI, NVE, BGP overlay + core/DMZ
> loopback peering) are pending.

**Stage 3 — SVIs + L2VNI (EVPN L3VNI plumbing): DEPLOYED & VERIFIED** on `dmz2`:

| Object | Value | Status |
|--------|-------|--------|
| `l2vpn evpn` (global) | `replication-type static`, `router-id Loopback0` | applied |
| `l2vpn evpn instance 902/903 vlan-based` | `encapsulation vxlan`, `replication-type static` | applied |
| `vlan configuration 902` | `member evpn-instance 902 vni 50902` | applied |
| `vlan configuration 903` | `member evpn-instance 903 vni 50903` | applied |
| VLAN `101` (`green-dhcp-server`), `111` (`blue-dhcp-server`), `902`, `903` | L2 database | active |
| `interface Vlan101` (green tenant) | `198.18.145.1/24`, `no autostate` | up/up |
| `interface Vlan111` (blue tenant) | `198.18.146.1/24`, `no autostate` | up/up |
| `interface Vlan902` (blue L3VNI) | `ip unnumbered Loopback0`, pim, `no autostate` | up/up |
| `interface Vlan903` (green L3VNI) | `ip unnumbered Loopback0`, pim, `no autostate` | up/up |

> **Reference fix:** `dmz02.cfg` originally omitted `no autostate` on the tenant SVIs `Vlan101`/
> `Vlan111`; live `dmz1` has it on `Vlan100`/`Vlan110`. Added `no autostate` to both the live device
> **and** the `dmz02.cfg` reference so the shared-services SVIs stay up regardless of trunk-port
> state. L2VNI VLAN names (`green-dhcp-server`/`blue-dhcp-server`) mirror `dmz1`'s role convention.
> Remaining stages (NVE, BGP overlay + core/DMZ loopback peering) are pending.

**Stage 4 — NVE (VXLAN tunnel endpoint): DEPLOYED & VERIFIED** on `dmz2`:

| Object | Value | Status |
|--------|-------|--------|
| `interface nve1` | `source-interface Loopback0` (`198.19.2.200`), `host-reachability protocol bgp` | Admin Up / Oper Up |
| `member vni 50902 vrf blue` | L3VNI blue | VNI state `Up` (mcast `239.190.0.2`) |
| `member vni 50903 vrf green` | L3VNI green | VNI state `Up` (mcast `239.190.0.3`) |

> `nve1` mirrors `dmz1` exactly (only the `source-interface` primary IP differs — `198.19.2.200`
> vs `198.19.1.200`). No L2 members (dmz2 carries only L3VNIs, same as dmz1). Remaining stage:
> BGP overlay (EVPN border peers + direct/loopback core peers) — after which the VXLAN tunnels and
> Type-5 routes will come up.

**Stage 5 — GRE overlay + BGP overlay: DEPLOYED & VERIFIED (dmz2 side + cores)** on `dmz2`,
`core1`, `core2`. The `dmz02.cfg` reference originally peered EVPN directly to the border
Loopback0s (`198.19.1.5`/`198.19.1.6`); this was **incorrect** — live `dmz1` peers the borders
over a GRE/OSPF-100 overlay to their `Loopback2` identities (`10.101.1.2`/`10.101.2.2`), per
[`2026-06-25-border-dmz-evpn-gre-overlay.md`](2026-06-25-border-dmz-evpn-gre-overlay.md). dmz2 was
built to mirror the live `dmz1` GRE model:

| Object | Value | Status |
|--------|-------|--------|
| `interface Loopback1` | `10.100.4.1/32` (GRE tunnel source) | Up / Up |
| `interface Tunnel10` → Border-01 | `10.100.102.1/30`, src `Loopback1`, dest `10.100.2.5`, OSPF 100 area 0, PIM | Up / Up |
| `interface Tunnel11` → Border-02 | `10.100.103.1/30`, src `Loopback1`, dest `10.100.2.6`, OSPF 100 area 0, PIM | Up / Up |
| `router ospf 100` | `router-id 198.19.2.200`, `redistribute connected route-map LOOPBACK0-INTO-OSPF100` | Interfaces P2P |
| `route-map TO-BGP` | `permit 10` match `Loopback0`; `permit 30` match `Loopback1` (no `Vlan120` — dmz2 has no red VRF) | — |
| `router bgp 65004` EVPN peers | `10.101.1.2` / `10.101.2.2` (border Loopback2, `ebgp-multihop 255`, `update-source Loopback0`, EVPN-only) | Idle (pending borders) |
| `router bgp 65004` direct core peers | `198.19.2.85` / `198.19.2.89` (`remote-as 65002`, `soft-reconfiguration inbound`) | **Established** (21 pfx each) |
| Per-VRF AFs | `blue` / `green` / `shared` — `advertise l2vpn evpn`, `redistribute connected/static`, `default-information originate` | Configured |

**Core-side dmz2 peering — DEPLOYED & VERIFIED** on `core1`/`core2` (NX-OS, `router bgp 65002`):

| Core | Neighbor | Config | Status |
|------|----------|--------|--------|
| `core1` | `198.19.2.86` | `remote-as 65004`, `soft-reconfiguration inbound always` | **Established** |
| `core2` | `198.19.2.90` | `remote-as 65004`, `soft-reconfiguration inbound always` | **Established** |

> Only the **direct `/30`** core peers were deployed — mirroring live `dmz1` (whose working overlay
> uses direct core peers + GRE EVPN only). The `198.19.x.200` loopback core peers present in the
> reference `core01/02.cfg` were intentionally **not** deployed (live `dmz1` does not use them
> either). Once the core sessions came up, dmz2 learned the border `Loopback1`s (`10.100.2.5/.6`)
> via BGP and both GRE tunnels came `Up/Up`. OSPF 100 shows the tunnel interfaces in `P2P` with
> `0` neighbors and the EVPN peers `Idle` — both **expected**, pending the border-side config.

**Border-side rendering (pending CatC push):** The GRE tunnel + EVPN neighbor for dmz2 on both
borders is driven entirely by the CatC J2 templates (no manual border edits). The following
`DEFN-*` files were updated so a future render adds the dmz2 side automatically:

| Template | Change |
|----------|--------|
| [`DEFN-ROLES.j2`](../Catalyst%20Center%20Templates/Site%20BGP%20EVPN%20Templates/DEFN-ROLES.j2) | Added `dmz2.dcloud.cisco.com` to the `MCLUSTER` role list |
| [`DEFN-LOOPBACKS.j2`](../Catalyst%20Center%20Templates/Site%20BGP%20EVPN%20Templates/DEFN-LOOPBACKS.j2) | Added `DEFN_LOOP_MCLUSTER['dmz2…'] = {'ip':'198.19.2.200','asn':'65004','gre_src':'10.100.4.1'}` |
| [`DEFN-BORDER-DMZ-TUNNELS.j2`](../Catalyst%20Center%20Templates/Site%20BGP%20EVPN%20Templates/DEFN-BORDER-DMZ-TUNNELS.j2) | Appended two `Tunnel20` entries: Border-01→dmz2 `10.100.102.2/30` and Border-02→dmz2 `10.100.103.2/30`, both `dest 10.100.4.1` |

> `FABRIC-BORDER-DMZ-TUNNELS.j2` and `FABRIC-EVPN.j2` iterate these dicts, so no FABRIC template
> changes were needed. On the next CatC render/push the borders will get `Tunnel20` to dmz2 (OSPF
> 100), the spines will redistribute dmz2's `gre_src` (`10.100.4.1/32`) into OSPF 1 via
> `MCLUSTER-LOOPBACKS`, and each border will add `neighbor 198.19.2.200 remote-as 65004` under the
> `OVERLAY-DMZ-EVPN-PEER-*` templates — bringing the dmz2 EVPN sessions up.

**GRE overlay tunnel addressing (dmz1 vs dmz2):**

| Link | dmz1 | dmz2 |
|------|------|------|
| DMZ `Loopback1` (GRE src) | `10.100.2.1/32` | `10.100.4.1/32` |
| DMZ ↔ Border-01 tunnel `/30` | `10.100.100.0/30` | `10.100.102.0/30` |
| DMZ ↔ Border-02 tunnel `/30` | `10.100.101.0/30` | `10.100.103.0/30` |
| Border tunnel iface to this DMZ | `Tunnel10` | `Tunnel20` |
| EVPN peers (border `Loopback2`) | `10.101.1.2` / `10.101.2.2` | `10.101.1.2` / `10.101.2.2` (shared) |

## Motivation

- `dmz1` and `dmz2` sit in two separate physical DMZ locations and both extend the **same**
  `vrf blue` / `vrf green` over EVPN. If they reused `dmz1`'s shared-services `/24`s, the two
  subnets would collide inside the tenant VRFs.
- Both DMZs form multi-cluster BGP EVPN peering to the same `border01`/`border02`, so their
  underlay `/30`s must not overlap any existing fabric/core allocation in `198.19.2.0/24`.
- `dmz1` and `dmz2` do **not** carry corporate `red` — only `blue` and `green`. The red
  underlay-DHCP VLAN (`Vlan120` on `dmz1`) is intentionally omitted from `dmz2`.

## Addressing Design

### Underlay P2P links (`198.19.2.0/24`)

`dmz1` occupies `198.19.2.64/28`. The next free contiguous block starts at `198.19.2.84`
(`.80/30` is the core1↔core2 interconnect). `dmz2` takes three routed links:

| Link | `/30` subnet | dmz2 side | Peer side |
|------|--------------|-----------|-----------|
| dmz2 ↔ core1 | `198.19.2.84/30` | `198.19.2.86` | core1 `198.19.2.85` |
| dmz2 ↔ core2 | `198.19.2.88/30` | `198.19.2.90` | core2 `198.19.2.89` |
| dmz2 ↔ FW (vrf shared) | `198.19.2.92/30` | `198.19.2.93` | FW `198.19.2.94` |

`dmz2` reaches the `dhcp-server` over an L2 trunk (green + blue VLANs only), like `dmz1`.

### Tenant-facing shared-services SVIs (location-unique)

| SVI | VRF | dmz1 | dmz2 |
|-----|-----|------|------|
| green | 903 | `Vlan100` `198.18.143.1/24` | `Vlan101` `198.18.145.1/24` |
| blue  | 902 | `Vlan110` `198.18.144.1/24` | `Vlan111` `198.18.146.1/24` |

VLAN IDs are also unique (`101`/`111` vs `100`/`110`) because both DMZs trunk to the same
`dhcp-server` node — reusing IDs would merge the two locations' L2 domains.

### Identity summary

| Attribute | dmz1 | dmz2 |
|-----------|------|------|
| Hostname / ASN | `dmz1` / 65003 | `dmz2` / 65004 |
| Loopback0 | `198.19.1.200/32` | `198.19.2.200/32` |
| Mgmt (Gi0/0) | `198.18.128.107` | `198.18.128.114` |
| RD base | `172.18.200.1` | `172.18.200.2` |
| Route-Target ASN | `65003:xxx` | `65004:xxx` |
| EVPN peers | `198.19.1.5` / `198.19.1.6` (borders, `ebgp-multihop 255`) | same |
| PIM RP | `198.19.1.254` | same |

## What Changed

| File | Change |
|------|--------|
| `Node Configs/fabric-dmz/dmz02.cfg` | **New** reference IOS-XE config for `dmz2`; includes core `Loopback0` eBGP peers |
| `Node Configs/fabric-dmz/dmz01.cfg` | Synced to live `dmz1` (`soft-reconfiguration inbound` on direct core neighbors); added core `Loopback0` eBGP peers |
| `Node Configs/cores/core01.cfg` | Refreshed to current `198.19.2.x` / NX-OS 10.5(3) scheme; added `E1/6` dmz2 `/30` link + dmz2 BGP peerings + symmetric dmz1 loopback peer (`update-source loopback0`); advertises own `Loopback0` `network 198.19.1.8/32` |
| `Node Configs/cores/core02.cfg` | Refreshed to current `198.19.2.x` / NX-OS 10.5(3) scheme; added `E1/6` dmz2 `/30` link + dmz2 BGP peerings (`update-source loopback0` on loopback peers); advertises own `Loopback0` `network 198.19.1.9/32` |
| `Node Configs/fabric-dmz/dhcp.cfg` | Added `Gi3.101` (green `198.18.145.100/24`) + `Gi3.111` (blue `198.18.146.100/24`) dmz2 trunk sub-interfaces |
| `DIAGRAMS/cisco_evpn_cml.drawio` | Split shared-services labels per DMZ; added dmz2 DHCP scopes; annotated underlay `/30`s |
| `DIAGRAMS/cisco_evpn_cml.png` | Re-rendered from updated source |
| `README.md` §1.1 | Added ASN 65004 (`dmz2`, Location B) to the ASN-domain list |
| `README.md` §1.2 | Updated CML prose: per-DMZ shared-services subnets + DHCP scopes; removed stale IOT VXLAN reference |

## Core Reference-Config Refresh (Important)

The canonical repo references `Node Configs/cores/core01.cfg` and `core02.cfg` were **stale** —
they still held the retired `172.16.x` underlay scheme on NX-OS 9.3(9). The live topology (from
backup `config-backups/20260702-153910/`) runs the `198.19.2.x` scheme on NX-OS 10.5(3). Both
core references were refreshed to the current scheme **and** extended with the dmz2 peer-side
config in the same pass, so the cores are now symmetric.

### Core dmz2 peer-side deltas (applied to both cores)

| Item | core1 | core2 |
|------|-------|-------|
| dmz2 `/30` interface | `E1/6` `198.19.2.85/30` (ospf p2p, pim sparse) | `E1/6` `198.19.2.89/30` (ospf p2p, pim sparse) |
| dmz2 direct eBGP | `neighbor 198.19.2.86 remote-as 65004` | `neighbor 198.19.2.90 remote-as 65004` |
| dmz2 loopback eBGP | `neighbor 198.19.2.200 remote-as 65004 ebgp-multihop 2` | `neighbor 198.19.2.200 remote-as 65004 ebgp-multihop 2` |
| dmz1 loopback eBGP (symmetry) | `neighbor 198.19.1.200 remote-as 65003 ebgp-multihop 2` **(added)** | `neighbor 198.19.1.200 remote-as 65003 ebgp-multihop 2` (already present) |

Both cores' loopback neighbors (`198.19.1.200`, `198.19.2.200`) also carry `update-source loopback0`
so the multihop eBGP sessions source from the core `Loopback0` (`198.19.1.8` / `198.19.1.9`).

### DMZ-side loopback peers (added to `dmz01.cfg` and `dmz02.cfg`)

To match the core-side loopback neighbors, both DMZ gateways now peer the two core `Loopback0`
addresses over multihop eBGP (verified against the live `dmz1` running-config, which was also the
source for syncing the `soft-reconfiguration inbound` lines on the direct core neighbors):

```
 neighbor 198.19.1.8 remote-as 65002
 neighbor 198.19.1.8 ebgp-multihop 2
 neighbor 198.19.1.8 update-source Loopback0
 neighbor 198.19.1.9 remote-as 65002
 neighbor 198.19.1.9 ebgp-multihop 2
 neighbor 198.19.1.9 update-source Loopback0
```
(plus `activate` + `soft-reconfiguration inbound` under `address-family ipv4`).

> **Reachability — loopback next-hops now resolve:** the dmz↔core `/30` links are **not** in OSPF
> (dmz `router ospf 100` runs only on the GRE tunnels to the borders), so the DMZ has no IGP route
> to the core `Loopback0`s. To make the multihop-loopback sessions install routes, **each core now
> advertises its own `Loopback0` `/32`** into BGP — `network 198.19.1.8/32` on core1 and
> `network 198.19.1.9/32` on core2. The DMZ receives each `/32` over the **direct `/30` session**
> (next-hop = the connected core `/30` address), which resolves the multihop next-hop so routes
> learned over the loopback sessions install correctly. The fabric-facing `TO_CAMPUS` outbound
> filter permits only `0.0.0.0/0`, so the `/32`s are **not** leaked toward the campus fabric.



## Operational Impact

Reference/design artifact — `dmz02.cfg` documents the intended `dmz2` build and the core/DHCP
references now include the matching peer-side config. No live template or playbook logic changed.
Remaining peer-side deltas to apply when deploying `dmz2`:

- **FW (vrf shared)**: dmz2-facing inside interface `198.19.2.94/30`
- **dhcp-server**: **done** — green `198.18.145.100/24` (`Gi3.101`) + blue `198.18.146.100/24`
  (`Gi3.111`). dmz2 subnets are directly connected on the dhcp-server, so no extra static route is
  needed; the existing `blue`/`green` VRF default routes (via dmz1) remain unchanged.
- **leaves**: add dmz2 DHCP helpers `198.18.145.100` (green) / `198.18.146.100` (blue)

