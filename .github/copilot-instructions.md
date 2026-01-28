# Copilot Instructions for Cisco Catalyst Center BGP EVPN VXLAN Templates

## Project Overview
Jinja2 template collection for Cisco Catalyst Center (DNAC) to provision Campus BGP EVPN VXLAN fabrics on IOS-XE Catalyst 9000 switches. Templates render role-aware configurations for spine-leaf topologies with multi-tenancy, IPSEC transport, and Tenant Routable Multicast (TRM).

## Catalyst Center Magic Variables
Catalyst Center injects runtime context into templates. The primary magic variable is:
```jinja
{% set DEVICE_HOSTNAME = __device.hostname | default('', true) %}
```
- `__device.hostname` - FQDN of the target device (e.g., `leaf01.dcloud.cisco.com`)
- Always dereference once at template start and pass to macros as `DEVICE_HOSTNAME`
- Must match hostnames in `DEFN_NODE_ROLES` and `DEFN_LOOP_UNDERLAY` exactly
- Other available: `__device.managementIpAddress`, `__device.platformId`, `__device.serialNumber`

## Architecture

### Template Structure (Two Categories)
1. **DEFN-*.j2 (Definition Templates)** - Declare fabric intent as JSON-like data structures:
   - `DEFN-ROLES.j2` - Node role assignments (SPINE, RR, CLIENT, BORDER)
   - `DEFN-LOOPBACKS.j2` - Per-device underlay/overlay IP mappings
   - `DEFN-VRF.j2` - VRF definitions with RD/RT assignments
   - `DEFN-OVERLAY.j2` - VLAN/VNI/SVI/DHCP definitions per VRF

2. **FABRIC-*.j2 (Provisioning Templates)** - Generate CLI using role-based logic:
   - Numbered 1-7 indicating deployment order
   - Reference definitions via `{% include %}` directives
   - Use macros from `FUNC-OBJECT-MACROS.j2` for VRF resolution

### Build Orchestration
[BGP-EVPN-BUILD.j2](BGP EVPN/BGP-EVPN-BUILD.j2) is the master template that:
- Includes all DEFN-*.j2 and FUNC-*.j2 files
- Calls build macros in sequence: VRF → Loopbacks → IPSEC → NVE → Multicast → EVPN → Overlay → NAC

### Node Role Conventions
Roles are defined in `DEFN_NODE_ROLES` dict and drive conditional logic throughout:
```jinja
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['RR'] %}      {# Spine/Route Reflector logic #}
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['CLIENT'] %}  {# Leaf/Border client logic #}
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['BORDER'] %}  {# Border-specific (IPSEC, L3OUT) #}
{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['SPINE'] %}   {# Spine-only (Anycast RP, MSDP) #}
```

## Tenant Semantics (VRF Classification)

### Corporate Tenant: `red` (VRF ID 901)
- **Purpose**: Enterprise user subnets with full routing to IP Core
- **Services**: Centralized DHCP/DNS via IP Core (helper: `198.18.5.253`)
- **Multicast**: Tenant Routable Multicast (TRM) enabled with Anycast-RP at `172.17.254.100`
- **VLANs**: 101, 102, 201 (corporate workstation segments)
- **Routing**: Advertised to Core via L3OUT on Spine nodes

### IOT Tenants: `blue` (902), `green` (903)
- **Purpose**: Isolated IOT device segments requiring DMZ handoff
- **Services**: Segregated DHCP/DNS in DMZ only (helpers: `198.18.7.253`, `198.18.8.253`)
- **Transport**: VXLAN-over-IPSEC tunnels from Border nodes to DMZ fabric
- **VLANs**: 401 (blue), 501 (green)
- **Routing**: No direct Core access; traffic hairpins through DMZ firewalls

### VRF-to-Node Assignment
Not all VRFs deploy to all nodes. `DEFN_VRF_TO_NODE` maps which VRF IDs apply per device:
```jinja
{% set DEFN_VRF_TO_NODE = {
  'leaf01.dcloud.cisco.com': [901, 902, 903],
  'border01.dcloud.cisco.com': [902, 903],  {# IOT only on borders #}
  ...
} %}
```

## Key Patterns

### VRF Object Resolution
Every FABRIC template resolves VRF objects before generating config:
```jinja
{% set vrf_objs = [] %}
{{ vrf_definition(DEFN_VRF, DEFN_VRF_TO_NODE, DEVICE_HOSTNAME) }}
{% for vrf in vrf_objs %}
  {# Generate VRF-specific config #}
{% endfor %}
```

### VNI Offset Calculations
L2VNI and L3VNI values are computed from VLAN IDs using offsets:
- **L3VNI**: `L3VNIOFFSET + vrf.id` (e.g., 50000 + 901 = 50901)
- **L2VNI**: `L2VNIOFFSET + vlan_id` (e.g., 10000 + 101 = 10101)

### Loopback IP Derivation
Device-specific addressing uses underlay loopback as anchor:
- `DEFN_LOOP_UNDERLAY[DEVICE_HOSTNAME]` for Loopback0 IP
- Overlay loopback IPs derived by adding last octet to VRF base

## Editing Guidelines

### When Modifying DEFN-* Templates
- Hostnames must match device FQDN exactly (e.g., `leaf01.dcloud.cisco.com`)
- VRF IDs must be unique and consistent across all DEFN files
- L3OUT interface/neighbor params must match physical topology

### When Modifying FABRIC-* Templates
- Wrap role-specific config in `{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['...'] %}`
- Use `{{FABRIC_BGP_ASN}}` not hardcoded ASN values
- Maintain the build sequence dependencies (VRF before NVE before EVPN)

### Template Macro Signatures
All FABRIC templates export a single macro that accepts consistent parameters:
```jinja
{% macro vrfDefinitionBuild(DEFN_VRF, DEFN_VRF_TO_NODE, DEVICE_HOSTNAME, DEFN_LOOP_UNDERLAY, FABRIC_BGP_ASN) %}
{% macro interfaceLoopbackBuild(DEFN_VRF, DEFN_VRF_TO_NODE, DEVICE_HOSTNAME, DEFN_LOOP_NAME, ...) %}
{% macro evpnBuild(DEFN_VRF, DEFN_VRF_TO_NODE, DEVICE_HOSTNAME, DEFN_NODE_ROLES, ...) %}
```

## Reference Files
- [README.md](README.md) - Complete architecture docs with IP tables and CLI examples
- [Node Configs/](Node%20Configs/) - Expected output configurations for validation
- [BGP EVPN/](BGP%20EVPN/) - Production templates

## Validation Checklist
When making changes, verify:
1. Template renders valid IOS-XE CLI syntax
2. Role conditions prevent config from applying to wrong node types
3. VRF/VLAN/VNI mappings remain consistent across templates
4. BGP neighbor relationships use correct loopback IPs from DEFN-LOOPBACKS
