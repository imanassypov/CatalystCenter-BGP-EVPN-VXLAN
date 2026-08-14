# 2026-08-13 — MCLUSTER-LOOPBACKS Prefix-List Rebuilt On Every Push (Compliance Deviation Fix)

## Summary

After provisioning, Catalyst Center reported a persistent **CLI compliance violation** on
`FABRIC-EVPN.j2` for both spines. The intended line

```
ip prefix-list MCLUSTER-LOOPBACKS seq 15 permit 10.100.2.1/32
```

was never present in the device running-config, while the neighbouring
`seq 25 permit 10.100.4.1/32` matched cleanly.

## Root Cause

Two conditions combined:

1. **Stale day-0 entry squatting on `seq 15`.** The CML startup configuration for
   `Spine-01` / `Spine-02` ships with the pre-2026-07-01 design line:

   ```
   ip prefix-list MCLUSTER-LOOPBACKS seq 15 permit 198.19.1.200/32
   ```

   That entry (DMZ `Loopback0`) was removed manually in
   [2026-07-01-border-gre-src-reip-and-dmz-evpn-repoint.md](2026-07-01-border-gre-src-reip-and-dmz-evpn-repoint.md),
   but every CML lab reset restores the older snapshot and re-introduces it.

2. **Catalyst Center CLI templates are purely additive** — they never emit `no` commands.
   IOS-XE will not silently overwrite an occupied prefix-list sequence number, so the
   template's `seq 15 permit 10.100.2.1/32` was rejected on push. `seq 25` was a free
   sequence number, so it applied normally.

Result: an unfixable compliance deviation that re-appeared after every re-provision.

## Functional Impact (beyond the compliance flag)

- Borders had **no specific OSPF 1 route** to the `dmz1` GRE hub `10.100.2.1`, falling back
  to default-route ECMP for GRE tunnel destination reachability.
- `198.19.1.200/32` (DMZ `Loopback0`) **was** being injected into OSPF 1 — precisely the
  condition the design forbids, because it decouples EVPN peer reachability from GRE tunnel
  state and prevents BGP `fall-over` from triggering on tunnel failure.

## Fix 1 — Live Remediation (spine1, spine2)

```
configure terminal
no ip prefix-list MCLUSTER-LOOPBACKS seq 15 permit 198.19.1.200/32
ip prefix-list MCLUSTER-LOOPBACKS seq 15 permit 10.100.2.1/32
end
write memory
```

Post-change state (identical on both spines):

```
ip prefix-list MCLUSTER-LOOPBACKS seq 15 permit 10.100.2.1/32
ip prefix-list MCLUSTER-LOOPBACKS seq 25 permit 10.100.4.1/32
```

## Fix 2 — Template Hardening (`FABRIC-EVPN.j2`)

The prefix-list is now torn down and rebuilt on every push, so the template is
self-healing against any pre-existing entry regardless of sequence number.

```jinja
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['RR'] and DEFN_TUNNELS is defined and DEFN_TUNNELS | length > 0 %}
! @start-ignore-compliance
no ip prefix-list MCLUSTER-LOOPBACKS
! @end-ignore-compliance
{% for remote in DEFN_NODE_ROLES['MCLUSTER'] %}
ip prefix-list MCLUSTER-LOOPBACKS seq {{loop.index * 10 + 5}} permit {{DEFN_LOOP_MCLUSTER[remote]['gre_src']}}/32
{% endfor %}
!
{% endif %}
```

The `no` line is wrapped in `! @start-ignore-compliance` / `! @end-ignore-compliance` because
a negation command never appears in the running-config and would itself be scored as a
deviation by the Catalyst Center compliance engine.

Rendered on a spine with both DMZs defined:

```
no ip prefix-list MCLUSTER-LOOPBACKS
ip prefix-list MCLUSTER-LOOPBACKS seq 15 permit 10.100.2.1/32
ip prefix-list MCLUSTER-LOOPBACKS seq 25 permit 10.100.4.1/32
!
```

> **Note**: the rebuild causes a sub-second window where `route-map BGP-TO-OSPF permit 30`
> matches an empty prefix-list. Since `match` against a non-existent/empty prefix-list denies,
> the DMZ GRE hub /32s are momentarily withdrawn from OSPF 1 during a push. Established GRE
> tunnels and EVPN sessions are not torn down at this timescale.

## Affected Files

| File | Change |
|---|---|
| `Catalyst Center Templates/Site BGP EVPN Templates/FABRIC-EVPN.j2` | Added compliance-ignored `no ip prefix-list MCLUSTER-LOOPBACKS` before the generation loop; expanded the block comment with the rationale |
| `README.md` | Spine `MCLUSTER-LOOPBACKS` bullet documents the rebuild behaviour |
| Live: `Spine-01`, `Spine-02` | Stale `seq 15 permit 198.19.1.200/32` replaced with `10.100.2.1/32`, saved to startup-config |

## Known Related Drift (not remediated)

The same CML day-0 config also leaves a legacy aggregate on the spines:

```
ip prefix-list FABRIC-LOOPBACKS seq 10 permit 198.19.1.0/24 ge 32
```

`FABRIC-EVPN.j2` generates `FABRIC-LOOPBACKS` at `seq 1..8` only, so `seq 10` is pure extra
config. It broadens `route-map OSPF-TO-BGP` to redistribute every `198.19.1.0/24` /32 —
including the DMZ Lo0 `198.19.1.200/32` — into BGP. It was removed live on 2026-07-01 and
has since been restored by a lab reset. Consider applying the same rebuild pattern to the
`FABRIC-LOOPBACKS` block, or removing `seq 10` from the CML startup configs.

## Validation

```
spine1# show running-config | include MCLUSTER-LOOPBACKS
ip prefix-list MCLUSTER-LOOPBACKS seq 15 permit 10.100.2.1/32
ip prefix-list MCLUSTER-LOOPBACKS seq 25 permit 10.100.4.1/32
 match ip address prefix-list MCLUSTER-LOOPBACKS
```

Re-run the compliance check in Catalyst Center (Device 360 -> Compliance -> CLI Template);
the `FABRIC-EVPN.j2` open violation should clear.
