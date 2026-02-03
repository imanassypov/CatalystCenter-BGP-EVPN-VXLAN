# Copilot Instructions for Cisco Catalyst Center BGP EVPN VXLAN Templates

## Project Overview
Jinja2 templates for Cisco Catalyst Center provisioning Campus BGP EVPN VXLAN fabrics on IOS-XE Catalyst 9000 switches. Renders role-aware configurations for spine-leaf topologies with multi-tenancy, optional IPSEC transport, and Tenant Routable Multicast (TRM).

## Architecture: Data/Logic Separation

### Two Template Categories
| Category | Purpose | Files |
|----------|---------|-------|
| `DEFN-*.j2` | Data definitions (dicts/lists) | `DEFN-VRF`, `DEFN-ROLES`, `DEFN-LOOPBACKS`, `DEFN-OVERLAY`, `DEFN-IPSEC` |
| `FABRIC-*.j2` | CLI generators (macros) | `FABRIC-VRF`, `FABRIC-EVPN`, `FABRIC-NVE`, `FABRIC-OVERLAY` |
| `FUNC-*.j2` | Reusable helper macros | `FUNC-OBJECT-MACROS` (contains `vrf_definition()`) |

### Build Orchestration (BGP-EVPN-BUILD.j2)
Master template includes all files and calls macros in dependency order:
```
VRF → Loopbacks → IPSEC tunnels → NVE/VNI → Multicast → EVPN BGP → Overlay SVIs → NAC
```

## Catalyst Center Runtime Context
Catalyst Center injects `__device` object. Dereference once and pass to all macros:
```jinja
{% set DEVICE_HOSTNAME = __device.hostname | default('', true) %}
```
**Critical:** Hostnames must match FQDNs exactly across all dictionaries (e.g., `leaf01.dcloud.cisco.com`).

## Key Data Structures

### Node Roles (`DEFN-ROLES.j2`)
```jinja
{% set DEFN_NODE_ROLES = {
  'SPINE':  ['spine01.dcloud.cisco.com', 'spine02.dcloud.cisco.com'],
  'RR':     ['spine01.dcloud.cisco.com', 'spine02.dcloud.cisco.com'],  {# Route Reflectors #}
  'CLIENT': ['leaf01.dcloud.cisco.com', 'border01.dcloud.cisco.com'],  {# RR clients #}
  'BORDER': []  {# Leave empty to disable IPSEC/Multi-Cluster features #}
} %}
```
Use `{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['RR'] %}` for role-specific config.

### VRF-to-Node Mapping (`DEFN-VRF.j2`)
Not all VRFs exist on all nodes. Control instantiation here:
```jinja
{% set DEFN_VRF_TO_NODE = {
  'spine01.dcloud.cisco.com':  ['901'],           {# Spines: corporate only #}
  'leaf01.dcloud.cisco.com':   ['901','902','903'], {# Leafs: all VRFs #}
  'border01.dcloud.cisco.com': ['902','903']      {# Borders: IOT only #}
} %}
```

### VRF Resolution Pattern
Every FABRIC macro resolves device-specific VRFs before generating CLI:
```jinja
{% set vrf_objs = [] %}
{{ vrf_definition(DEFN_VRF, DEFN_VRF_TO_NODE, DEVICE_HOSTNAME) }}
{% for vrf in vrf_objs %}
  {# Access: vrf.id, vrf.name, vrf.mdt_default, vrf.mdt_data #}
{% endfor %}
```

## VNI Offset Conventions (`DEFN-VNIOFFSETS.j2`)
```jinja
{% set L2VNIOFFSET = 10000 %}  {# L2VNI = 10000 + vlan_id → VLAN 101 = VNI 10101 #}
{% set L3VNIOFFSET = 50 %}     {# L3VNI = 50000 + vrf.id → VRF 901 = VNI 50901 #}
```

## Tenant Model
| Tenant | VRF ID | Type | Routing |
|--------|--------|------|---------|
| `red` | 901 | Corporate | TRM multicast, L3OUT to Core via Spines |
| `blue` | 902 | IOT | IPSEC tunnel to DMZ |
| `green` | 903 | IOT | IPSEC tunnel to DMZ |

## Editing Checklists

### Adding a New Device
1. Add FQDN to `DEFN_NODE_ROLES` under appropriate role(s)
2. Add loopback IP to `DEFN_LOOP_UNDERLAY` in `DEFN-LOOPBACKS.j2`
3. Add VRF assignments to `DEFN_VRF_TO_NODE`
4. If Border: add to `DEFN_LOOP_IPSEC`, `DEFN_LOOP_MCLUSTER`, `DEFN_IPSEC`

### Adding a New VRF
1. Add entry to `DEFN_VRF` list with unique `id`, `name`, `mdt_default`, `mdt_data`
2. Add VRF to nodes in `DEFN_VRF_TO_NODE` (only nodes that need it)
3. Add overlay VLANs to `DEFN_OVERLAY` under matching `vrf` key
4. Ensure VRF ID is consistent across all references

### Adding a New VLAN/Overlay
Add to `DEFN_OVERLAY` under the correct VRF:
```jinja
'102': {'name':'corp-102', 'ipaddr':'10.1.12.1 255.255.255.0', 
        'mac':'0000.0901.0102', 'dhcp_helper':'198.18.5.253', 
        'bum_addr':'239.190.100.102'}
```

### Modifying FABRIC-* Templates
- Always wrap role-specific config: `{% if DEVICE_HOSTNAME in DEFN_NODE_ROLES['...'] %}`
- Pass variables via macro parameters—never hardcode ASN, IPs, or VRF IDs
- Maintain build order (VRF must exist before NVE references it)

## Validation
Compare rendered output against reference configs in `Node Configs/` (e.g., `LEAF1.cfg`, `SPINE1.cfg`).

**Key checks:**
1. No Jinja artifacts in output (valid IOS-XE CLI syntax)
2. Role conditionals prevent misapplied config (no RR config on leafs)
3. RD format: `{loopback_ip}:{vrf_id}` using `DEFN_LOOP_UNDERLAY[DEVICE_HOSTNAME]`
4. RT format: `{ASN}:{vrf_id}` using `FABRIC_BGP_ASN` from `DEFN-OVERLAY.j2`
5. BGP neighbors reference correct peer loopbacks from `DEFN_LOOP_UNDERLAY`

## Ansible Automation (GitOps)
This project integrates with Red Hat Ansible for automated Git-to-Catalyst Center synchronization.

**Companion repo:** [Cisco-Catalyst-Center-Templates-Github-integration](https://github.com/imanassypov/Cisco-Catalyst-Center-Templates-Github-integration)

### Key Files for Automation
- **Line 1 hint:** Each `.j2` file must have CATC targeting hint:
  ```jinja
  {## CATC: productFamily=Switches and Hubs, softwareType=IOS-XE, productSeries=Cisco Catalyst 9000 Series Virtual Switches ##}
  ```
- **`BGP-EVPN-BUILD.yml`:** Defines composite template ordering (only `FABRIC-*.j2` files)

### Template Inclusion Rules
| Include in composite | Template type |
|---------------------|---------------|
| ✅ Yes | `FABRIC-*.j2` (top-level executables) |
| ❌ No | `DEFN-*.j2`, `FUNC-*.j2` (resolved via `{% include %}`) |

## Common Pitfalls
- **Hostname mismatch:** FQDN in templates must exactly match Catalyst Center inventory
- **Missing VRF mapping:** Device generates empty VRF config if not in `DEFN_VRF_TO_NODE`
- **Stale BORDER role:** Empty `DEFN_NODE_ROLES['BORDER']` is intentional—disables IPSEC features
