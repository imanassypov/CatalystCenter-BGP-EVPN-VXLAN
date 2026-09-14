# 2026-09-14 - AS-path regex `_$` is a permit-any: corrected to `^$`

## Summary

Both EVPN outbound loop-prevention policies in this design were backed by an
AS-path ACL written as `permit _$`. That regex matches **every** AS path, so
neither policy filtered anything. Corrected to `permit ^$` (locally originated
only), which is what the design intent has always called for.

| Device role | Route-map | ACL | Applied |
|---|---|---|---|
| Spine (RR) | `EVPN-PEER-BORDER-OUT` | `ip as-path access-list 100` | `OVERLAY-BORDER-EVPN-PEER-POLICY` peer-policy, `address-family l2vpn evpn` |
| DMZ gateway (`dmz1` 65003 / `dmz2` 65004) | `DMZ-policy-out` | `ip as-path access-list 1` | `neighbor 10.101.1.2 / 10.101.2.2 route-map DMZ-policy-out out` |

## Root cause

In Cisco IOS AS-path regular expressions, `_` matches a comma, a left or right
brace, a left or right parenthesis, a space, **the beginning of the input
string, or the end of the input string**. The last two are zero-width matches.

Therefore `_$` reduces to `$`:

| AS path in the BGP table | `_$` | `^$` |
|---|---|---|
| (empty - locally originated) | match | match |
| `65002` (learned from the IP core) | match | no match |
| `65001 65004` (fabric transit) | match | no match |

`_$` is only meaningful when an AS number follows the underscore - `_65002$`
correctly matches "originated in AS 65002". With nothing after it, the
underscore anchors to the end-of-string boundary and the ACL degenerates to
permit-any.

The correct expression for "originated in the local AS" is `^$`. At outbound
policy evaluation time the local ASN has not yet been prepended, so `^$` is
evaluated against the path as stored in the BGP table.

## Impact of the defect

- **Spines**: `EVPN-PEER-BORDER-OUT` advertised every EVPN path to borders,
  including DMZ-learned Type-5 routes (`65003` / `65004`) reflected back out.
  Borders already hold those routes directly over their eBGP GRE sessions, so
  the intended "reflect fabric-originated routes only" guard was absent.
- **DMZ gateways**: `DMZ-policy-out` advertised core-learned (`65002`) paths to
  the fabric borders instead of only DMZ-originated Type-5 prefixes.

eBGP's own AS-path loop check still prevented a true routing loop, so the
defect was latent rather than service-affecting - but the stated loop-prevention
control did not exist.

## Changes

### `Catalyst Center Templates/Site BGP EVPN Templates/FABRIC-EVPN.j2`

```diff
-{# =========================================== #}
-{# BGP Border Prefix-List to prevent loops     #}
-{# =========================================== #}
 {% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['RR'] %}
-ip as-path access-list 100 permit _$
+! @start-ignore-compliance
+no ip as-path access-list 100
+! @end-ignore-compliance
+ip as-path access-list 100 permit ^$
 !
 route-map EVPN-PEER-BORDER-OUT permit 10
  match as-path 100
 {% endif %}
```

The `no ip as-path access-list 100` guard is required because IOS-XE AS-path
ACLs are **append-only** and Catalyst Center template pushes are **additive**.
Without the explicit removal, a device that already carries `permit _$` would
end up with both entries, and the permit-any `_$` line would continue to match
everything - leaving the fix inert. This mirrors the existing
`no ip prefix-list MCLUSTER-LOOPBACKS` pattern in the same template
(see [2026-08-13-mcluster-prefix-list-rebuild.md](2026-08-13-mcluster-prefix-list-rebuild.md)).

### `Node Configs/CML/BGP_EVPN_Campus_v10.yaml`

Day-0 config for both DMZ gateways (`dmz1`, `dmz2`) updated:

```diff
-ip as-path access-list 1 permit _$
+ip as-path access-list 1 permit ^$
```

### Documentation

- `README.md` section 1.3 operator note - corrected the DMZ guidance and added
  the reason `_$` must not be used.
- `Release Notes/2026-09-01-dmz2-bidirectional-evpn-rt-import.md` - correction
  callout added.

## Affected files

| File | Change |
|---|---|
| `Catalyst Center Templates/Site BGP EVPN Templates/FABRIC-EVPN.j2` | `_$` -> `^$` + additive-push rebuild guard |
| `Node Configs/CML/BGP_EVPN_Campus_v10.yaml` | dmz1 + dmz2 day-0 ACL `_$` -> `^$` |
| `README.md` | Operator note corrected |
| `Release Notes/2026-09-01-dmz2-bidirectional-evpn-rt-import.md` | Correction callout |

`Node Configs/fabric-dmz/dmz01.cfg`, `dmz02.cfg`, `fabric-site1/spine0*.cfg` and
`Config-Backup-20260508-131703/Spine0*.cfg` are **device captures**, not design
sources, and are intentionally left at their as-captured state. They will show
`^$` after the next push and backup cycle.

## Validation

Spines are template-provisioned; the DMZ gateways are not (see README section
1.3) and must be updated by hand:

```
configure terminal
 no ip as-path access-list 1
 ip as-path access-list 1 permit ^$
end
write memory
```

Verify on a spine and on each DMZ gateway:

```
show ip as-path-access-list 100          ! spine  - expect: permit ^$  (single entry)
show ip as-path-access-list 1            ! dmz1/2 - expect: permit ^$  (single entry)
show bgp l2vpn evpn neighbors 10.101.1.2 advertised-routes
```

Expected after the fix: `advertised-routes` from each DMZ toward the border Lo2
peers contains only DMZ-originated Type-5 prefixes (blue 902 / green 903
defaults and `shared` 1000) with an empty AS path - no `65002` core paths.

Regression checks (must be unchanged):

- Border `show bgp l2vpn evpn summary` - `198.19.1.200` / `198.19.2.200`
  `PfxRcd > 0`
- `show ip route vrf blue 0.0.0.0` on borders and Leaf-01 - default still
  present via the DMZ
- Leaf/border tenant reachability through the DMZ firewall unchanged

## Operational impact

Behaviour change on spines and DMZ gateways: outbound EVPN advertisements are
now genuinely restricted to locally originated paths. Deploy during a change
window and confirm the regression checks above before and after. If DMZ-learned
prefixes must transit the fabric in future, add an explicit permit line to the
ACL rather than reverting to `_$`.
