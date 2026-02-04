# Copilot Instructions for Cisco Catalyst Center BGP EVPN VXLAN Templates

## Project Overview
Jinja2 templates for Cisco Catalyst Center provisioning Campus BGP EVPN VXLAN fabrics on IOS-XE Catalyst 9000 switches. Outputs role-aware IOS-XE CLI for spine-leaf topologies with multi-tenancy, optional IPSEC transport, and Tenant Routable Multicast (TRM).

## Template Architecture

### Three Template Categories
| Prefix | Purpose | Output |
|--------|---------|--------|
| `DEFN-*.j2` | Data dictionaries (variables only) | None—`{% set %}` blocks only |
| `FABRIC-*.j2` | CLI generators (include DEFN files) | IOS-XE configuration |
| `FUNC-*.j2` | Reusable Jinja macros | Called by FABRIC templates |

### Execution Order (BGP-EVPN-BUILD.yml)
```
VRF → Loopbacks → IPSEC → NVE → Multicast → EVPN → L3OUT → Overlay → NAC
```
**Only `FABRIC-*.j2` in BGP-EVPN-BUILD.yml**—DEFN/FUNC are included via `{% include %}`.

### Required Line 1 Header
Every `.j2` file must start with this targeting hint:
```jinja
{## CATC: productFamily=Switches and Hubs, softwareType=IOS-XE, productSeries=Cisco Catalyst 9000 Series Virtual Switches ##}
```

### Template Include Pattern
FABRIC templates include DEFN/FUNC files using:
```jinja
{% include "{{ TEMPLATE_PROJECT_NAME }}/DEFN-VRF.j2" %}
```
**`TEMPLATE_PROJECT_NAME`** is injected by the companion [Ansible automation](https://github.com/imanassypov/Cisco-Catalyst-Center-Templates-Github-integration) during Git-to-Catalyst Center sync. It resolves to the Catalyst Center Template Project name. Do not hardcode project names in templates.

## Critical Patterns

### Catalyst Center Jinja2 Limitations
Catalyst Center uses a restricted Jinja2 engine. **Avoid:**
| Unsupported | Use Instead |
|-------------|-------------|
| `not in` operator | `{% if dict[key] is not defined %}` |
| `.keys()` method | Iterate dict directly |
| Complex nested expressions | Restructure into simpler steps |

### Device Context Pattern (every FABRIC template)
```jinja
{% set DEVICE_HOSTNAME = __device.hostname | default('', true) %}
```
**Hostnames = FQDNs matching Catalyst Center inventory exactly** (e.g., `leaf01.dcloud.cisco.com`).

### VRF Resolution Pattern (FUNC-OBJECT-MACROS.j2)
```jinja
{% set vrf_objs = [] %}
{{ vrf_definition(DEFN_VRF, DEFN_VRF_TO_NODE, DEVICE_HOSTNAME) }}
{% for vrf in vrf_objs %}
  {# vrf.id='901', vrf.name='red', vrf.mdt_default='239.190.0.1', vrf.mdt_data='239.190.1.0' #}
{% endfor %}
```

### Role-Based Conditionals (DEFN-ROLES.j2)
```jinja
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['RR'] %}     {# Spines as Route Reflectors #}
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['BORDER'] %} {# Border switches for IPSEC #}
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['CLIENT'] %} {# Leaf/Border as BGP clients #}
```
**Empty `BORDER` list = IPSEC disabled** (intentional for non-border deployments).

## Key Data Structures

| Variable | File | Purpose |
|----------|------|---------|
| `DEFN_NODE_ROLES` | DEFN-ROLES.j2 | `{'SPINE':[], 'RR':[], 'CLIENT':[], 'BORDER':[]}` |
| `DEFN_VRF_TO_NODE` | DEFN-VRF.j2 | Maps hostname → list of VRF IDs |
| `DEFN_LOOP_UNDERLAY` | DEFN-LOOPBACKS.j2 | Maps hostname → Loopback0 IP |
| `DEFN_OVERLAY` | DEFN-OVERLAY.j2 | VLANs per VRF with SVI params |
| `FABRIC_BGP_ASN` | DEFN-OVERLAY.j2 | Fabric ASN (e.g., `'65001'`) |

### VNI Calculations (DEFN-VNIOFFSETS.j2)
- **L2VNI**: `10000 + vlan_id` → VLAN 101 = VNI 10101
- **L3VNI**: `50` + `vrf.id` → VRF 901 = VNI 50901

### RD/RT Formats (see Node Configs/ for expected output)
- **RD**: `{DEFN_LOOP_UNDERLAY[hostname]}:{vrf.id}` → `172.16.255.3:901`
- **RT**: `{FABRIC_BGP_ASN}:{vrf.id}` → `65001:901`

## Editing Checklists

### Adding a New Device
1. **DEFN-ROLES.j2**: Add FQDN to SPINE/RR/CLIENT/BORDER lists
2. **DEFN-LOOPBACKS.j2**: Add to `DEFN_LOOP_UNDERLAY` (+ `DEFN_LOOP_IPSEC`/`DEFN_LOOP_MCLUSTER` if Border)
3. **DEFN-VRF.j2**: Add VRF ID list to `DEFN_VRF_TO_NODE`

### Adding a New VRF
1. **DEFN-VRF.j2**: Add to `DEFN_VRF` list: `{'id':'904','name':'yellow','mdt_default':'239.190.0.4','mdt_data':'239.190.4.0'}`
2. **DEFN-VRF.j2**: Add VRF ID to nodes in `DEFN_VRF_TO_NODE`
3. **DEFN-OVERLAY.j2**: Add VLANs under new VRF key

### Adding a New VLAN
Add to `DEFN_OVERLAY` under the correct VRF:
```jinja
'102': {'name':'corp-102', 'ipaddr':'10.1.12.1 255.255.255.0', 'mac':'0000.0901.0102', 'dhcp_helper':'198.18.5.253', 'bum_addr':'239.190.100.102'}
```

### Adding L3 External Connectivity (Spine-to-Core)
Edit **DEFN-L3OUT.j2**: Add per-VRF eBGP peering with interface/neighbor details.

## Validation
Compare rendered output against `Node Configs/*.cfg` (LEAF1.cfg, SPINE1.cfg, BORDER1.cfg).

**Check for:**
- Valid IOS-XE CLI—no Jinja artifacts (`{{`, `{%`, `}}`)
- Correct RD/RT formats per device role
- Role conditionals applied correctly (no RR config on leafs, no IPSEC on non-borders)

## Common Mistakes
| Mistake | Impact | Fix |
|---------|--------|-----|
| Hostname mismatch | No config rendered for device | FQDNs must match Catalyst Center inventory exactly |
| Missing VRF mapping | Empty VRF config | Add device to `DEFN_VRF_TO_NODE` |
| DEFN in BGP-EVPN-BUILD.yml | Template errors | Only FABRIC-*.j2 in composite; DEFN/FUNC included internally |
| Using `not in` | Catalyst Center parse failure | Use `is not defined` pattern |
