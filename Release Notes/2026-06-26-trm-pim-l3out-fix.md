# Release Note — 2026-06-26

## Tenant Routable Multicast (TRM) Restored: PIM on Spine L3OUT + Leaf Register-Source

### Summary

End-to-end tenant (VRF `red`) IP multicast across the VXLAN EVPN fabric was failing:
a source on Leaf-01 was seen by the fabric, but the receiver on Leaf-02 never received
traffic. Systematic diagnosis traced this to two missing pieces of PIM configuration in
the templates. Both fixes were validated live and are now permanently encoded in the
source-of-truth Jinja2 templates so the CI/CD pipeline cannot regress them.

The tenant anycast RP (`198.19.1.254`) is hosted **externally** on the NX-OS cores and is
reached from the fabric over the per-VRF L3OUT. This is a separate plane from the
spine-hosted underlay BUM anycast RP (`198.19.1.100`).

### Root Cause

| # | Fault | Effect |
|---|-------|--------|
| 1 | FHR (leaf) PIM-registered the source from the anycast Vlan101 SVI (`198.18.101.1`), shared by every leaf | The NX-OS cores cannot return-route to a specific leaf, so the PIM Register/Encap tunnel never came up and **no BGP MVPN Type-5 Source-Active** was originated. FHR `(S,G)` stuck in `flags: PFT`, OIL `Null`. |
| 2 | The spine→core VRF-`red` L3OUT dot1Q sub-interfaces (`Gi1/0/5.2`, `Gi1/0/6.2`) had `ip address` but no `ip pim sparse-mode` | Spines had **zero PIM neighbors** to the cores, so the shared-tree join (MVPN Type-6 → PIM `(*,G)`) could never reach the external tenant RP. |

### What Changed

| Area | Before | After |
|------|--------|-------|
| Leaf PIM Register source | implicit (anycast Vlan101 SVI, non-routable) | `ip pim vrf red register-source Loopback901` (routable per-VRF overlay loopback) |
| Spine→core L3OUT sub-ifs | `ip address` only | `ip address` + `ip pim sparse-mode` |

### Files Modified

- `Catalyst Center Templates/Site BGP EVPN Templates/FABRIC-MCAST.j2`
  - Added `ip pim vrf {{vrf.name}} register-source Loopback{{vrf.id}}` next to the
    per-VRF `rp-address`, so the FHR registers from the routable overlay loopback
    (`Loopback901` = `198.18.100.x`) instead of the anycast SVI.
- `Catalyst Center Templates/Site BGP EVPN Templates/FABRIC-L3OUT.j2`
  - Added `ip pim sparse-mode` to the VRF L3OUT dot1Q sub-interface block, so spines
    form PIM neighbors toward the external cores and can reach the tenant RP.
- `test-cases/README-MCAST-TCASE.md`
  - Added a BGP MVPN control-plane tutorial (route types 1–7, NLRI decoding, RD→device
    legend, mroute flag decoder, signalling sequence diagram).
  - Added a root-cause analysis and resolution section and new MVPN/PIM troubleshooting
    rows; added a Contents/TOC and renumbered sections.
- `test-cases/images/mcast-tcase-topology.drawio` / `.png`
  - Corrected RP labeling: tenant RP `198.19.1.254` is external on the NX-OS cores
    (not the spines); `198.19.1.100` is the separate underlay BUM anycast RP on spines.
  - Moved the NX-OS Cores node north, outside a dashed fabric boundary, with the
    spine→core L3OUT PIM links shown.

### Impact

- Tenant multicast in VRF `red` now converges end-to-end across the fabric.
- `register-source` is emitted on every node that has the VRF mapped (within the existing
  per-VRF loop); it is only operative on the PIM-Register path, so it is a no-op on nodes
  that never act as an FHR.
- `ip pim sparse-mode` is added to every rendered L3OUT VRF sub-interface (the spine→core
  handoff); no other interfaces are affected.

### Validation

- FHR (Leaf-01) `(S,G)` advances `PFT` → `FTGqx` with OIL
  `Vlan901 VXLAN v4 Encap (50901, 239.190.0.1) Forward`.
- Spine forms PIM neighbors to both cores and learns MVPN Type-5/6/7 routes for the group.
- Receiver leaf (Leaf-02) `(S,G)` forwards to `Vlan101`; host (red02) delivery confirmed.
- No Jinja syntax errors and ASCII-only rendered output in `FABRIC-MCAST.j2` /
  `FABRIC-L3OUT.j2`.

### Operator Notes

- The tenant RP (`198.19.1.254`) and the `0.0.0.0/0` return path live on the external
  NX-OS cores and are not rendered by this repository.
- Live PIM-SM convergence requires a **sustained** multicast stream; a short burst
  (e.g. 20 packets over 4 s) will not converge the SPT and can look like a failure.
