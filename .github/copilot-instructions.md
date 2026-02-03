# Copilot Instructions for Cisco Catalyst Center BGP EVPN VXLAN Templates

## Project Overview
Jinja2 templates for Cisco Catalyst Center provisioning Campus BGP EVPN VXLAN fabrics on IOS-XE Catalyst 9000 switches. Renders role-aware IOS-XE CLI for spine-leaf topologies with multi-tenancy, optional IPSEC transport, and Tenant Routable Multicast (TRM).

## Template Architecture

### Three Template Categories
| Prefix | Purpose | Examples |
|--------|---------|----------|
| `DEFN-*.j2` | Data dictionaries only (no CLI output) | `DEFN-VRF`, `DEFN-ROLES`, `DEFN-LOOPBACKS` |
| `FABRIC-*.j2` | CLI generators (include DEFN files, output IOS-XE) | `FABRIC-VRF`, `FABRIC-EVPN`, `FABRIC-NVE` |
| `FUNC-*.j2` | Reusable Jinja macros | `FUNC-OBJECT-MACROS` (`vrf_definition()`) |

### Template Execution Order (BGP-EVPN-BUILD.yml)
```yaml
VRF → Loopbacks → IPSEC → NVE → Multicast → EVPN → Overlay → NAC
```
Only `FABRIC-*.j2` files go in `BGP-EVPN-BUILD.yml`—`DEFN-*` and `FUNC-*` are included via `{% include %}`.

### Required Line 1 Hint
Every `.j2` file must start with Catalyst Center targeting:
```jinja
{## CATC: productFamily=Switches and Hubs, softwareType=IOS-XE, productSeries=Cisco Catalyst 9000 Series Virtual Switches ##}
```

## Critical Patterns

### Catalyst Center Jinja2 Limitations
Catalyst Center uses a restricted Jinja2 engine. **Avoid these unsupported constructs:**
- `not in` operator → Use `is not defined` instead: `{% if dict[key] is not defined %}`
- Intermediate variables in conditionals may cause false-positive "undefined variable" detection
- Complex expressions may need restructuring

### Catalyst Center Device Context
Dereference `__device` once per template, pass to macros:
```jinja
{% set DEVICE_HOSTNAME = __device.hostname | default('', true) %}
```
**Hostnames must be FQDNs matching Catalyst Center inventory exactly** (e.g., `leaf01.dcloud.cisco.com`).

### VRF Resolution Pattern (used in all FABRIC templates)
```jinja
{% set vrf_objs = [] %}
{{ vrf_definition(DEFN_VRF, DEFN_VRF_TO_NODE, DEVICE_HOSTNAME) }}
{% for vrf in vrf_objs %}
  {# vrf.id='901', vrf.name='red', vrf.mdt_default, vrf.mdt_data #}
{% endfor %}
```

### Role-Based Conditionals
Wrap role-specific config with role checks:
```jinja
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['RR'] %}     {# Spines as Route Reflectors #}
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['BORDER'] %} {# Border switches for IPSEC #}
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['CLIENT'] %} {# Leaf/Border as RR clients #}
```

## Key Data Structures

### DEFN_NODE_ROLES (DEFN-ROLES.j2)
```jinja
'SPINE': [...], 'RR': [...], 'CLIENT': [...], 'BORDER': []
```
Empty `BORDER` list disables IPSEC features intentionally.

### DEFN_VRF_TO_NODE (DEFN-VRF.j2)
Controls which VRFs instantiate on each device:
```jinja
'spine01.dcloud.cisco.com': ['901'],           {# Corporate only #}
'leaf01.dcloud.cisco.com':  ['901','902','903'] {# All VRFs #}
```

### VNI Calculations (DEFN-VNIOFFSETS.j2)
- L2VNI: `10000 + vlan_id` → VLAN 101 = VNI 10101
- L3VNI: `50000 + vrf.id` → VRF 901 = VNI 50901

### Fabric Globals (DEFN-OVERLAY.j2)
```jinja
{% set FABRIC_BGP_ASN = '65001' %}
{% set FABRIC_UNDERLAY = {'proto':'ospf', 'instance_id':'1', 'area':'0'} %}
```

## Editing Checklists

### Adding a New Device
1. `DEFN-ROLES.j2`: Add FQDN to appropriate role lists
2. `DEFN-LOOPBACKS.j2`: Add to `DEFN_LOOP_UNDERLAY` (and `DEFN_LOOP_IPSEC`/`DEFN_LOOP_MCLUSTER` if Border)
3. `DEFN-VRF.j2`: Add VRF assignments to `DEFN_VRF_TO_NODE`

### Adding a New VRF
1. `DEFN-VRF.j2`: Add to `DEFN_VRF` list with `id`, `name`, `mdt_default`, `mdt_data`
2. `DEFN-VRF.j2`: Add VRF ID to nodes in `DEFN_VRF_TO_NODE`
3. `DEFN-OVERLAY.j2`: Add overlay VLANs under the new `vrf` key

### Adding a New VLAN
Add to `DEFN_OVERLAY` under correct VRF:
```jinja
'102': {'name':'corp-102', 'ipaddr':'10.1.12.1 255.255.255.0', 
        'mac':'0000.0901.0102', 'dhcp_helper':'198.18.5.253', 'bum_addr':'239.190.100.102'}
```

## Validation
Compare rendered output against `Node Configs/*.cfg` (LEAF1.cfg, SPINE1.cfg, etc.).

**Check for:**
- Valid IOS-XE CLI (no Jinja artifacts like `{{` or `{%`)
- RD format: `{loopback_ip}:{vrf_id}` from `DEFN_LOOP_UNDERLAY`
- RT format: `{FABRIC_BGP_ASN}:{vrf_id}`
- Role conditionals applied correctly (no RR config on leafs)

## Common Mistakes
- **Hostname mismatch**: FQDNs in DEFN files must exactly match Catalyst Center inventory
- **Missing VRF mapping**: Device outputs empty VRF config if missing from `DEFN_VRF_TO_NODE`
- **Wrong template in composite**: Only `FABRIC-*.j2` in `BGP-EVPN-BUILD.yml`; `DEFN-*`/`FUNC-*` are included internally
