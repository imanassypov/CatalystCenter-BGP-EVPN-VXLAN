# Release Note — 2026-07-02

## Telemetry Subscriptions Not Rendered on CLIENT-Only Leaves (Variable-Key Jinja Lookup)

### Summary

During a live audit of the MDT telemetry deployment, the Splunk/OpenTelemetry
subscriptions (`telemetry ietf subscription 40101`–`40119`) were found on the
Spine and Border nodes but **completely absent from the CLIENT-only leaves**
(`Leaf-01`, `Leaf-02`). The composite template had provisioned successfully on the
leaves — their full fabric configuration (NVE, `l2vpn evpn`, `member vni`, BGP EVPN
address-family) was present — yet the entire telemetry section rendered empty.

Root-cause analysis traced this to a **variable-key dictionary lookup into an
included-scope dict** in `FABRIC-TELEMETRY-SPLUNK.j2`. Catalyst Center's Jinja2
engine silently returns empty for `DEFN_NODE_ROLES[role]` when `role` is a loop
variable, so the computed target-device union list never received the leaf
hostnames and the `{% if DEVICE_HOSTNAME in TELEMETRY_TARGET_DEVICES %}` guard
evaluated false on every CLIENT-only node.

---

### Root Cause

| Symptom | Cause |
|---|---|
| `40101`–`40119` present on Spine-01/02 and Border-01/02 | Those subscriptions were pre-existing from an earlier manual/OTel push (configured 06/30); not from this render |
| `40101`–`40119` absent on Leaf-01 and Leaf-02 | Telemetry section rendered empty — guard was false |
| Leaf-01 has NVE/EVPN/VNI/BGP EVPN config | Composite ran on the leaves; only the telemetry block was skipped |
| Target list built via `for role in DEFN_TELEMETRY_SPLUNK_ROLES` → `DEFN_NODE_ROLES[role]` | Variable-key bracket lookup into an included-scope dict returns empty in CatC's Jinja engine — the documented limitation in `.github/copilot-instructions.md` |

This is the same class of engine limitation already recorded in the project's
Catalyst Center Jinja2 caveats: **any dict defined in an included `DEFN-*.j2` file
must be accessed with a literal key, never a variable key, for iteration or lookup.**

---

### Changes Made

#### `FABRIC-TELEMETRY-SPLUNK.j2` — replace variable-key target list with literal-key guard

**Before** (silently empty on leaves):

```jinja
{% set TELEMETRY_TARGET_DEVICES = [] %}
{% set TELEMETRY_TARGET_SEEN = {} %}
{% for role in DEFN_TELEMETRY_SPLUNK_ROLES %}
{% for node in DEFN_NODE_ROLES[role] %}
{% if TELEMETRY_TARGET_SEEN[node] is not defined %}
{% set _ = TELEMETRY_TARGET_DEVICES.append(node) %}
{% set _ = TELEMETRY_TARGET_SEEN.update({node: true}) %}
{% endif %}
{% endfor %}
{% endfor %}
{% if DEVICE_HOSTNAME in TELEMETRY_TARGET_DEVICES %}
```

**After** (literal-key membership — the only reliable pattern):

```jinja
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['SPINE'] or DEVICE_HOSTNAME in DEFN_NODE_ROLES['BORDER'] or DEVICE_HOSTNAME in DEFN_NODE_ROLES['CLIENT'] %}
```

`DEFN_TELEMETRY_SPLUNK_ROLES` remains in `DEFN-TELEMETRY-SPLUNK.j2` as documentation
of the intended role set; the roles are now enumerated explicitly in the guard so no
variable-key lookup is performed.

---

### Affected Files

| File | Change |
|---|---|
| `Catalyst Center Templates/Site BGP EVPN Templates/FABRIC-TELEMETRY-SPLUNK.j2` | Replaced variable-key target-list construction with a literal-key `or` membership guard |

---

### Validation

- Local Jinja2 render (`trim_blocks=True`) of the corrected guard against the live
  `DEFN_NODE_ROLES` data:

  | Host | Result |
  |---|---|
  | Leaf-01 (CLIENT) | renders telemetry |
  | Leaf-02 (CLIENT) | renders telemetry |
  | Spine-01 (SPINE) | renders telemetry |
  | Border-01 (BORDER+CLIENT) | renders telemetry |
  | dmz1 (MCLUSTER) | correctly skipped |

- Live device audit prior to fix confirmed the leaves carried full fabric config but
  no `40xxx` subscriptions, isolating the defect to this template's device-selection
  logic rather than device provisioning or reachability.

---

### Operational Impact

- After re-syncing the template from GitHub and re-running the composite (or a
  targeted device provision), the leaves will receive the `40101`–`40119`
  telemetry subscriptions, enabling their NVE/EVPN/BGP operational state to stream to
  the OpenTelemetry collector and Splunk.
- No change to Spine/Border behavior — those nodes already matched the previous guard
  (indirectly via pre-existing subscriptions) and match the new literal-key guard.

---

### Related Note — Invalid XPath Filters (separate issue, not fixed here)

During the same audit, subscriptions `40103`, `40105`, `40107`–`40113` reported
`Invalid XPath filter` / `Invalid value ... for parameter 'filter'` on IOS-XE
17.18.02 (e.g. `/nve-oper-data/nve-oper/nve-vni-oper`, `/evpn-oper-data/evpn-inst`,
`/evpn-oper-data/evpn-stats`). These XPaths are pushed correctly but rejected by the
device YANG models — a data-model compatibility issue distinct from this rendering
fix. Tracked separately.
