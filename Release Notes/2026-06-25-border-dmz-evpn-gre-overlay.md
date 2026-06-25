# Release Note — 2026-06-25

## Border-to-DMZ EVPN Peering Realigned to GRE Overlay (Loopback2 / ebgp-multihop 255)

### Summary

With the introduction of GRE underlay tunnels between the border switches and the DMZ
gateway, the border-to-DMZ BGP EVPN session was realigned from the legacy multicluster
model to a dedicated overlay-sourced model. The EVPN session now sources from the border
overlay loopback (`Loopback2`) with `ebgp-multihop 255`, riding the GRE/OSPF 100 underlay,
instead of sourcing from the physical underlay loopback (`Loopback0`) with `ebgp-multihop 4`.
The DMZ peer is now EVPN-only.

### What Changed

| Area | Before | After |
|------|--------|-------|
| Peer templates | `OVERLAY-MCLUSTER-EVPN-PEER-SESSION-POLICY` / `OVERLAY-MCLUSTER-EVPN-PEER-POLICY` | `OVERLAY-DMZ-EVPN-PEER-SESSION-POLICY` / `OVERLAY-DMZ-EVPN-PEER-POLICY` |
| EVPN session source | `update-source Loopback0` | `update-source Loopback2` (`DEFN_LOOP_NAME['DMZ_OVERLAY']`) |
| Multihop | `ebgp-multihop 4` | `ebgp-multihop 255` |
| IPv4 unicast AF | DMZ peer activated + IPv4 peer-policy | DMZ peer EVPN-only (not activated; block removed — `no bgp default ipv4-unicast` keeps it inactive on greenfield) |
| L2VPN EVPN AF | inherit `OVERLAY-MCLUSTER-EVPN-PEER-POLICY` | inherit `OVERLAY-DMZ-EVPN-PEER-POLICY` (still with `rewrite-evpn-rt-asn`) |

### Files Modified

- `BGP EVPN/DEFN-LOOPBACKS.j2`
  - Added `'DMZ_OVERLAY': 'Loopback2'` to `DEFN_LOOP_NAME`.
  - Clarified the `DEFN_LOOP_MCLUSTER` comment: the peer IP is the remote overlay EVPN
    identity reached via GRE/OSPF 100, not a directly-connected Loopback0.
- `BGP EVPN/FABRIC-EVPN.j2` (all changes are `DEFN_NODE_ROLES['BORDER']`-guarded)
  - Replaced the MCLUSTER peer-session/peer-policy with the DMZ peer templates
    (`ebgp-multihop 255`, `update-source Loopback2`, `fall-over route-map NODE-LOOPBACKS`).
  - DMZ neighbor now inherits `OVERLAY-DMZ-EVPN-PEER-SESSION-POLICY`.
  - Removed the BORDER-only `address-family ipv4` activation block (DMZ peer is EVPN-only).
  - `address-family l2vpn evpn` now inherits `OVERLAY-DMZ-EVPN-PEER-POLICY`.
- `README.md`
  - Documented the GRE tunnel templates (`DEFN-BORDER-DMZ-TUNNELS.j2`,
    `FABRIC-BORDER-DMZ-TUNNELS.j2`) in the directory tree and build sequence.
  - Added a "Border-to-DMZ EVPN Peering Model (GRE Overlay)" subsection.
  - Updated the node loopback table (border GRE Lo1/Lo2) and the ASN control-plane note.

### Impact

- Border switches: border-DMZ EVPN sessions now source from `Loopback2` over the GRE
  overlay with `ebgp-multihop 255` and are EVPN-only.
- Spine and Leaf rendering is unaffected — all changes are BORDER-guarded.
- No data structures were removed; the `MCLUSTER` role list is reused as the DMZ peer source.

### Operator Action Required (DMZ side, manual)

The DMZ gateway (`dmz1`) is not rendered by this repository. On the DMZ device:

- Repoint EVPN neighbors to the border `Loopback2` addresses `10.101.1.2` / `10.101.2.2`
  (instead of border `Loopback0` `198.19.1.5` / `198.19.1.6`).
- Set OSPF 100 `router-id` to the overlay identity `198.19.1.200` (not the tunnel endpoint).
- Keep DMZ peers EVPN-only: not activated in IPv4 unicast; activated under `l2vpn evpn`.

### Validation

- No Jinja syntax errors in `FABRIC-EVPN.j2` or `DEFN-LOOPBACKS.j2`.
- No remaining `OVERLAY-MCLUSTER` references in the template set.
- Rendered border path shows `OVERLAY-DMZ-EVPN-PEER-SESSION-POLICY` with
  `update-source Loopback2` and `ebgp-multihop 255`; DMZ peer activated only under
  `address-family l2vpn evpn`.
