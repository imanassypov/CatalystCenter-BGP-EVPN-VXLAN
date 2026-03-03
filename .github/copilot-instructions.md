# Copilot Instructions for Cisco Catalyst Center BGP EVPN VXLAN Templates

## Project Overview
Jinja2 templates for Cisco Catalyst Center provisioning Campus BGP EVPN VXLAN fabrics on IOS-XE Catalyst 9000 switches. Generates role-aware IOS-XE CLI for spine-leaf topologies with multi-tenancy, optional IPSEC transport, and Tenant Routable Multicast (TRM).

## Template Architecture

### Three Template Prefixes
| Prefix | Purpose | Output |
|--------|---------|--------|
| `DEFN-*.j2` | Data dictionaries (`{% set %}` blocks only) | No CLI output |
| `FABRIC-*.j2` | CLI generators (include DEFN/FUNC files) | IOS-XE configuration |
| `FUNC-*.j2` | Reusable Jinja macros | Called by FABRIC templates |

### Execution Order (BGP-EVPN-BUILD.yml)
Only FABRIC templates appear in `BGP-EVPN-BUILD.yml`:
```
VRF → Loopbacks → L3OUT → IPSEC → NVE → Multicast → EVPN → Overlay → NAC
```

### Required Line 1 Header
Every `.j2` file **must** start with:
```jinja
{## CATC: productFamily=Switches and Hubs, softwareType=IOS-XE, productSeries=Cisco Catalyst 9000 Series Virtual Switches ##}
```

### Template Include Pattern
```jinja
{% include "{{ TEMPLATE_PROJECT_NAME }}/DEFN-VRF.j2" %}
```
`TEMPLATE_PROJECT_NAME` is injected by [Ansible automation](https://github.com/imanassypov/Cisco-Catalyst-Center-Templates-Github-integration). Never hardcode project names.

## Catalyst Center Jinja2 Limitations (Critical)
| Unsupported | Use Instead |
|-------------|-------------|
| `not in` operator | `{% if dict[key] is not defined %}` |
| `.keys()` method | Iterate dict directly |
| Two-variable `for` loop: `{% for k, v in dict.items() %}` | Single-variable: `{% for k in dict %}` then access `dict[k]` |
| Complex nested expressions | Restructure into simpler steps |

## Core Patterns

### Device Context (every FABRIC template)
```jinja
{% set DEVICE_HOSTNAME = __device.hostname | default('', true) %}
```
Hostnames = **FQDNs matching Catalyst Center inventory exactly** (e.g., `leaf01.dcloud.cisco.com`).

### VRF Resolution Pattern
```jinja
{% set vrf_objs = [] %}
{{ vrf_definition(DEFN_VRF, DEFN_VRF_TO_NODE, DEVICE_HOSTNAME) }}
{% for vrf in vrf_objs %}
  {# vrf.id='901', vrf.name='red' #}
{% endfor %}
```

### Role-Based Conditionals
```jinja
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['RR'] %}     {# Spines as Route Reflectors #}
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['BORDER'] %} {# Border switches for IPSEC #}
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['CLIENT'] %} {# Leaf/Border as BGP clients #}
```
**Empty `BORDER` list = IPSEC disabled** (intentional for non-border deployments).

## Key Data Structures

| Variable | Source File | Structure |
|----------|-------------|-----------|
| `DEFN_NODE_ROLES` | DEFN-ROLES.j2 | `{'SPINE':[], 'RR':[], 'CLIENT':[], 'BORDER':[]}` |
| `DEFN_VRF` | DEFN-VRF.j2 | List of `{'id':'901','name':'red','mdt_default':'...','mdt_data':'...'}` |
| `DEFN_VRF_TO_NODE` | DEFN-VRF.j2 | `{'hostname.fqdn': ['901','902']}` |
| `DEFN_LOOP_UNDERLAY` | DEFN-LOOPBACKS.j2 | `{'hostname.fqdn': '172.16.255.3'}` |
| `DEFN_OVERLAY` | DEFN-OVERLAY.j2 | VLANs per VRF with SVI params |
| `FABRIC_BGP_ASN` | DEFN-OVERLAY.j2 | Fabric ASN string (e.g., `'65001'`) |

### VNI/RD/RT Calculations
- **L2VNI**: `10000 + vlan_id` → VLAN 101 = VNI 10101
- **L3VNI**: `50` + `vrf.id` → VRF 901 = VNI 50901
- **RD**: `{loopback_ip}:{vrf.id}` → `172.16.255.3:901`
- **RT**: `{FABRIC_BGP_ASN}:{vrf.id}` → `65001:901`

## Editing Checklists

### Adding a New Device
1. [DEFN-ROLES.j2](BGP%20EVPN/DEFN-ROLES.j2): Add FQDN to SPINE/RR/CLIENT/BORDER lists
2. [DEFN-LOOPBACKS.j2](BGP%20EVPN/DEFN-LOOPBACKS.j2): Add to `DEFN_LOOP_UNDERLAY` (+IPSEC/MCLUSTER if Border)
3. [DEFN-VRF.j2](BGP%20EVPN/DEFN-VRF.j2): Add VRF ID list to `DEFN_VRF_TO_NODE`

### Adding a New VRF
1. [DEFN-VRF.j2](BGP%20EVPN/DEFN-VRF.j2): Add to `DEFN_VRF` list and `DEFN_VRF_TO_NODE` mappings
2. [DEFN-OVERLAY.j2](BGP%20EVPN/DEFN-OVERLAY.j2): Add VLAN definitions under new VRF

### Adding a New VLAN
Add to `DEFN_OVERLAY` under the correct VRF:
```jinja
'102': {'name':'corp-102', 'ipaddr':'10.1.12.1 255.255.255.0', 'mac':'0000.0901.0102', 'dhcp_helper':'198.18.5.253', 'bum_addr':'239.190.100.102', 'network':'10.1.12.0 255.255.255.0'}
```

## Validation
Compare rendered output against [Node Configs/](Node%20Configs/) reference files (LEAF1.cfg, SPINE1.cfg, BORDER1.cfg).

**Check for:**
- Valid IOS-XE CLI—no Jinja artifacts (`{{`, `{%`, `}}`)
- Correct RD/RT formats per device role
- Role conditionals applied correctly

## Common Mistakes
| Mistake | Fix |
|---------|-----|
| Hostname mismatch | FQDNs must match Catalyst Center inventory exactly |
| Missing VRF mapping | Add device to `DEFN_VRF_TO_NODE` in DEFN-VRF.j2 |
| DEFN in BGP-EVPN-BUILD.yml | Only FABRIC-*.j2 in composite; DEFN/FUNC included internally |
| Using `not in` operator | Use `is not defined` pattern instead |
