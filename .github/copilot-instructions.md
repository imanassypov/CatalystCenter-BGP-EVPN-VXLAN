# Copilot Instructions for Cisco Catalyst Center BGP EVPN VXLAN Templates

## Project Overview
Jinja2 templates for Cisco Catalyst Center provisioning Campus BGP EVPN VXLAN fabrics on IOS-XE Catalyst 9000 switches. Renders role-aware configurations for spine-leaf topologies with multi-tenancy, optional IPSEC transport, and Tenant Routable Multicast (TRM).

## Catalyst Center Magic Variable
Catalyst Center injects runtime context. Dereference once in master template and pass to all macros:
```jinja
{% set DEVICE_HOSTNAME = __device.hostname | default('', true) %}
```
Hostnames must match FQDNs exactly across all DEFN-* dictionaries (e.g., `leaf01.dcloud.cisco.com`).

## Template Architecture

### Two Template Categories
| Category | Purpose | Example |
|----------|---------|---------|
| `DEFN-*.j2` | Data definitions (dicts/lists) | `DEFN_NODE_ROLES`, `DEFN_VRF`, `DEFN_OVERLAY` |
| `FABRIC-*.j2` | CLI generators (macros) | `vrfDefinitionBuild()`, `evpnBuild()` |

### Build Sequence (BGP-EVPN-BUILD.j2)
Master template orchestrates includes and macro calls in dependency order:
1. VRF definitions → 2. Loopbacks → 3. IPSEC tunnels → 4. NVE/VNI → 5. Multicast → 6. EVPN BGP → 7. Overlay SVIs → 8. NAC

### Node Role Conditionals
All FABRIC templates use role checks from `DEFN_NODE_ROLES`:
```jinja
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['RR'] %}      {# Spine route-reflector #}
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['CLIENT'] %}  {# Leaf/Border as RR client #}
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['BORDER'] %}  {# IPSEC tunnels, Multi-Cluster #}
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['SPINE'] %}   {# Anycast RP, L3OUT to Core #}
```
**Note:** BORDER role is optional—leave `DEFN_NODE_ROLES['BORDER']` empty (`[]`) to skip IPSEC/Multi-Cluster.

## VRF Resolution Pattern
Every FABRIC macro resolves device-specific VRFs before generating CLI:
```jinja
{% set vrf_objs = [] %}
{{ vrf_definition(DEFN_VRF, DEFN_VRF_TO_NODE, DEVICE_HOSTNAME) }}
{% for vrf in vrf_objs %}
  {# vrf.id, vrf.name, vrf.mdt_default, vrf.mdt_data available #}
{% endfor %}
```

## VNI Offset Conventions (DEFN-VNIOFFSETS.j2)
```jinja
{% set L2VNIOFFSET = 10000 %}  {# L2VNI = 10000 + vlan_id (e.g., VLAN 101 → VNI 10101) #}
{% set L3VNIOFFSET = 50 %}     {# L3VNI = 50000 + vrf.id (e.g., VRF 901 → VNI 50901) #}
```

## Tenant Model
| Tenant | VRF ID | Purpose | Routing |
|--------|--------|---------|---------|
| `red` | 901 | Corporate with TRM multicast | L3OUT via Spines to Core |
| `blue` | 902 | IOT (isolated) | IPSEC tunnel to DMZ only |
| `green` | 903 | IOT (isolated) | IPSEC tunnel to DMZ only |

VRFs are assigned per-node in `DEFN_VRF_TO_NODE`—Borders only get IOT VRFs; Spines only get corporate.

## Editing Guidelines

### Modifying DEFN-* (add devices, VRFs, VLANs)
- Add hostnames to ALL relevant dicts: `DEFN_NODE_ROLES`, `DEFN_LOOP_UNDERLAY`, `DEFN_VRF_TO_NODE`
- VRF IDs must be unique integers and consistent across `DEFN_VRF`, `DEFN_OVERLAY`, `DEFN_VRF_TO_NODE`
- VLANs defined in `DEFN_OVERLAY[].vlans{}` with ipaddr, mac, dhcp_helper, bum_addr

### Modifying FABRIC-* (add CLI features)
- Wrap role-specific config in `{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['...'] %}`
- Reference variables via macro parameters, never hardcode ASN/IPs
- Maintain build order—VRF must exist before NVE references it

### Macro Signature Pattern
All FABRIC macros accept common parameters:
```jinja
{% macro someBuild(DEFN_VRF, DEFN_VRF_TO_NODE, DEVICE_HOSTNAME, DEFN_NODE_ROLES, ...) %}
```

## Validation
Compare rendered output against reference configs in `Node Configs/` (e.g., `LEAF1.cfg`, `SPINE1.cfg`).

Key checks:
1. IOS-XE CLI syntax validity (no Jinja artifacts in output)
2. Role conditions prevent misapplied config (e.g., no RR config on leafs)
3. RD/RT use correct loopback IP from `DEFN_LOOP_UNDERLAY[DEVICE_HOSTNAME]`
4. BGP neighbors reference correct peer loopbacks
