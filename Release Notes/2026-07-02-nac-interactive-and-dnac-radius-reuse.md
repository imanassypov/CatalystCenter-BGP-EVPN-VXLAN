# NAC template: remove bogus INTERACTIVE wrapper and reuse DNAC-managed RADIUS server

**Date:** 2026-07-02
**Templates affected:** `Catalyst Center Templates/Site BGP EVPN Templates/FABRIC-NAC.j2`, `Catalyst Center Templates/Site BGP EVPN Templates/DEFN-NAC.j2`

## Summary

Two defects in the NAC/802.1X template caused the composite provision (`BGP-EVPN-BUILD.j2`)
to leave Leaf devices mis-configured and blocked the subsequent
`FABRIC-TELEMETRY-SPLUNK.j2` push. Both are fixed.

## Defect 1 — `terminal width 0` / leaked `#END_INTERACTIVE`

### Symptom

When NAC config was pushed to Leaf roles the device reported `terminal width 0` and the
literal marker `#END_INTERACTIVE` was sent onto the CLI:

```
Leaf-01(config)#class-map type control subscriber match-all AAA_SVR_DOWN_AUTHD_HOST
Leaf-01(config-filter-control-classmap)##END_INTERACTIVE
```

The session was left stuck in `config-filter-control-classmap` sub-mode, so every
following line (including the telemetry template that runs next in the composite) was
applied in the wrong context and failed.

### Root cause

`FABRIC-NAC.j2` wrapped the first class-map in a Catalyst Center interactive-command block:

```jinja
#INTERACTIVE
class-map type control subscriber match-all AAA_SVR_DOWN_AUTHD_HOST<IQ>Do you wish to continue?<R>yes
#END_INTERACTIVE
```

The `class-map type control subscriber` command never prompts `Do you wish to continue?`.
The fabricated `<IQ>/<R>` interactive handler misfired, and Catalyst Center emitted the
`#END_INTERACTIVE` marker as a literal CLI line. The reference config
([`Node Configs/fabric-site1/leaf01.cfg`](../Node%20Configs/fabric-site1/leaf01.cfg)) shows
the class-map as plain, non-interactive config.

### Fix

Removed the `#INTERACTIVE … <IQ> … <R> … #END_INTERACTIVE` wrapper. The class-map is now
emitted as plain config, matching the reference:

```
class-map type control subscriber match-all AAA_SVR_DOWN_AUTHD_HOST
 match result-type aaa-timeout
 match authorization-status authorized
```

## Defect 2 — duplicate RADIUS server (`%Server already exists with same address port combination`)

### Symptom

```
Leaf-01(config)#radius server NAC_902_198.18.133.27
Leaf-01(config-radius-server)#address ipv4 198.18.133.27 auth-port 1812 acct-port 1813
%Server already exists with same address port combination.
```

Catalyst Center had already provisioned the AAA server from network settings as
`dnac-radius_198.18.133.27`. The template then tried to create a second server
`NAC_902_198.18.133.27` bound to the same IP/port, which IOS-XE rejects.

### Root cause

DNAC-managed-server detection relied solely on the `__aaaendpointserver` system binding
variable. In this deployment that variable renders empty (`dnac_server_ips == []`), so the
template fell through to the `NAC_<vrfid>_<ip>` branch and created a duplicate. The reference
config did not hit this because there the NAC IP (`198.18.7.254`) differed from the DNAC IP
(`10.0.10.34`); in the current fabric both are `198.18.133.27`.

### Fix

1. `DEFN-NAC.j2` — added an explicit, deterministic `dnac_managed` flag to the NAC entry:

   ```jinja
   {% set DEFN_NAC_IOT = [
     {'vrf':'blue', 'nac_ip':'198.18.133.27', 'nac_key':'C1sco12345', 'dnac_managed': true}
     ]
   %}
   ```

2. `FABRIC-NAC.j2` — compute `nac_dnac_managed` from the explicit flag **or** the
   `__aaaendpointserver` auto-detection, then:
   - reuse the existing `dnac-radius_<ip>` server (do **not** emit a `radius server` block)
     when managed by Catalyst Center, and
   - **always** emit the VRF-scoped `aaa group server radius NAC_IOT_<vrfid>` referencing the
     resolved server name, with `ip vrf forwarding` + `ip radius source-interface`.

   Previously the AAA group was created only in the non-DNAC branch and, when DNAC-managed,
   the template referenced the global `dnac-client-radius-group` (losing VRF scoping). The
   group is now always VRF-scoped, matching the reference config
   (`aaa group server radius NAC_IOT_902` → `server name dnac-radius_…`).

### Rendered result (DNAC-managed IP)

```
aaa group server radius NAC_IOT_902
server name dnac-radius_198.18.133.27
ip vrf forwarding blue
ip radius source-interface Loopback902
retransmit 2
timeout 10
```

No `radius server` line is emitted, so the duplicate-address error no longer occurs.

## Behavior matrix

| NAC IP vs DNAC AAA IP | `dnac_managed` | `radius server` emitted? | AAA group | Server referenced |
|---|---|---|---|---|
| Same (this fabric) | `true` | No (reuses existing) | `NAC_IOT_<vrfid>` (VRF-scoped) | `dnac-radius_<ip>` |
| Different (reference) | `false` | Yes (`NAC_<vrfid>_<ip>`) | `NAC_IOT_<vrfid>` (VRF-scoped) | `NAC_<vrfid>_<ip>` |

## Operational impact

- Leaf NAC push no longer corrupts the CLI mode; `FABRIC-TELEMETRY-SPLUNK.j2` now applies.
- No duplicate RADIUS server is attempted when the AAA server is Catalyst Center-managed.
- Re-run stage `7.0` (template sync) then stage `10.0` (composite provision) to apply.

## Validation

- Compared rendered class-map and RADIUS/AAA structure against
  [`Node Configs/fabric-site1/leaf01.cfg`](../Node%20Configs/fabric-site1/leaf01.cfg)
  (`aaa group server radius NAC_IOT_902`, `class-map type control subscriber …` plain).
- Confirmed no remaining `#INTERACTIVE`, `<IQ>`, `<R>`, or `dnac-client-radius-group`
  references in `FABRIC-NAC.j2`.
