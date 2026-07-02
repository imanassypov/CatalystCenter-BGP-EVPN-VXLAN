# Cisco Catalyst Center BGP EVPN VXLAN Campus Fabric — Automation and Assurance

**Copyright © 2024-2026 Cisco Systems, Inc. All rights reserved.**

| Name | Role | Contact |
|------|------|---------|
| Igor Manassypov | Systems Engineer | imanassy@cisco.com |

---

## 1. Introduction

This repository implements a controller-managed BGP EVPN VXLAN campus fabric on Cisco IOS-XE Catalyst 9000 platforms via Cisco Catalyst Center CLI templates. The solution covers the full operational lifecycle: declarative intent definition, GitOps-driven template synchronization, role-aware device provisioning, and streaming telemetry assurance through Splunk.

### 1.1 Reference Topology

The lab validates a **three-tenant, multi-cluster spine-leaf fabric** with the following topology:

| Node | Platform | Role | ASN | Loopback0 | Additional Identities |
|------|----------|------|-----|-----------|----------------------|
| Spine-01 | C9000v | Route Reflector | 65001 | 198.19.1.1/32 | Lo2 = 198.19.1.100/32 (Anycast RP) |
| Spine-02 | C9000v | Route Reflector | 65001 | 198.19.1.2/32 | Lo2 = 198.19.1.100/32 (Anycast RP) |
| Leaf-01 | C9000v | BGP Client | 65001 | 198.19.1.3/32 | — |
| Leaf-02 | C9000v | BGP Client | 65001 | 198.19.1.4/32 | — |
| Border-01 | C9000v | Border Client | 65001 | 198.19.1.5/32 | Lo1 = 10.100.2.5 (GRE src), Lo2 = 10.101.1.2 (EVPN overlay) |
| Border-02 | C9000v | Border Client | 65001 | 198.19.1.6/32 | Lo1 = 10.100.2.6 (GRE src), Lo2 = 10.101.2.2 (EVPN overlay) |
| dmz1 | C9000v | DMZ Gateway | 65003 | 198.19.1.200/32 | Lo1 = 10.100.2.1 (GRE hub src) |
| Core-01 | NX-OSv | Core Router | 65002 | — | Enterprise IP Core |
| Core-02 | NX-OSv | Core Router | 65002 | — | Enterprise IP Core |

**Three ASN domains** define the BGP control plane:

- **ASN 65001** — Campus fabric: Spines as iBGP route reflectors, Leaves/Borders as clients
- **ASN 65002** — Enterprise IP Core: eBGP peering from Spines via L3OUT sub-interfaces
- **ASN 65003** — DMZ fabric: eBGP EVPN peering from Borders over GRE overlay (`ebgp-multihop 255`)

**Three tenants** provide traffic segmentation:

| VRF | ID | L3VNI | Transit VLAN | Segment VLANs | Deployment Scope |
|-----|----|-------|-------------|---------------|-----------------|
| red | 901 | 50901 | 901 | 101, 102 | Spine + Leaf |
| blue | 902 | 50902 | 902 | 201 | Leaf + Border + DMZ |
| green | 903 | 50903 | 903 | 221 | Leaf + Border + DMZ |

### 1.2 Topology Diagrams

![Logical EVPN Topology](DIAGRAMS/cisco_evpn_topology.png)

Logical spine-leaf architecture with border connections and three tenant VRFs.

![CML Lab Topology](DIAGRAMS/cisco_evpn_cml.png)

Cisco Modeling Labs emulation using virtual Catalyst 9000 instances.

![BGP ASN Relationships](DIAGRAMS/cisco_evpn_ASN.png)

BGP control plane: three ASN domains (campus, core, DMZ) and their peering relationships.

### 1.3 Border-to-DMZ EVPN Peering (GRE Overlay)

Borders peer with the DMZ gateway over a **GRE underlay** to decouple EVPN session stability from physical path topology:

- **GRE source addressing**: All GRE tunnel sources are allocated from `10.100.2.0/29`, intentionally outside the `198.19.1.0/24` fabric loopback space to avoid conflicts with core router Loopback0 addresses. See `DEFN_LOOP_GRE_SRC` and `DEFN_LOOP_GRE_PEER` in `DEFN-LOOPBACKS.j2`.
- **Tunnel underlay (OSPF 100)**: `FABRIC-BORDER-DMZ-TUNNELS.j2` renders per-border GRE tunnels and OSPF 100 adjacencies. The DMZ OSPF 100 router-id is `198.19.1.200` (Lo0), redistributed into OSPF 100 locally by the DMZ — never injected into OSPF 1 from the spine side.
- **Spine MCLUSTER-LOOPBACKS**: Only the DMZ `Loopback1` (`10.100.2.1/32`) is redistributed into OSPF 1 via `ip prefix-list MCLUSTER-LOOPBACKS` on spines. This ensures borders have a specific route to the GRE hub. Injecting `198.19.1.200` into OSPF 1 would decouple `fall-over` detection from tunnel state.
- **EVPN session sourcing**: Borders source from `Loopback2` (DEFN_LOOP_NAME `DMZ_OVERLAY`) with `ebgp-multihop 255`. DMZ peers to border Lo2 addresses (`10.101.1.2` / `10.101.2.2`).
- **EVPN-only peer**: The DMZ neighbor is activated only under `address-family l2vpn evpn` with `rewrite-evpn-rt-asn`; it is not activated in IPv4 unicast.

> **Operator note**: The DMZ gateway is not provisioned by this template set. On the DMZ side: configure Lo0 = 198.19.1.200/32 (OSPF 100 RID, EVPN update-source), Lo1 = 10.100.2.1/32 (GRE hub source), tunnel destinations = 10.100.2.5 / 10.100.2.6, and EVPN neighbors = 10.101.1.2 / 10.101.2.2.

### 1.4 Platform and Software Requirements

| Component | Version |
|-----------|---------|
| IOS-XE | 17.15.3 recommended; 17.12.x minimum (Multi-Cluster BGP requires 17.15+) |
| Catalyst Center | 2.3.7.9 or later |
| Cisco Modeling Labs | 2.9+ (lab emulation) |
| Ansible | 2.15+ with `cisco.dnac` collection |

**Supported hardware**: Catalyst 9500, 9400, 9300, and 9000v (virtual).

> Validation baseline: `Node Configs/Config-Backup-032626` (March 26, 2026).

---

## 2. Repository Structure

```
Catalyst Center Templates/
└── Site BGP EVPN Templates/       # Jinja2 template source (DEFN/FABRIC/FUNC)
    ├── BGP-EVPN-BUILD.yml         # Composite member list and execution order
    ├── DEFN-*.j2                  # Data dictionaries ({% set %} only, no CLI)
    ├── FABRIC-*.j2                # CLI generators (include DEFN + FUNC)
    └── FUNC-*.j2                  # Reusable Jinja macros

Node Configs/                      # Reference device configs (lab output)
├── Config-Backup-032626/          # Current validation baseline
├── fabric-site1/                  # Per-template rendered configs
├── fabric-dmz/                    # DMZ rendered configs
└── cores/                         # Core router configs

CICD Pipeline/                     # Ordered Catalyst Center provisioning stages
├── 1.0-Cisco-Catalyst-Center-Site-Hierarchy/
├── 2.0-Cisco-Catalyst-Center-Settings/
├── 3.0-Cisco-Catalyst-Center-Credentials/
├── 4.0-Cisco-Catalyst-Center-Device-Discovery/
├── 5.0-Cisco-Catalyst-Center-Assign-To-Site/
├── 6.0-Cisco-Catalyst-Center-SWIM/                        # Software Image Management (upgrade)
├── 7.0-Cisco-Catalyst-Center-Templates-Github-integration/  # GitOps sync: Git → Catalyst Center
├── 8.0-Cisco-Catalyst-Center-Network-Profile/
├── 9.0-Cisco-Catalyst-Center-Provision-Devices/
├── 10.0-Cisco-Catalyst-Center-Provision-Composite/
└── 11.0-Backup-My-Configs/

Campus BGP EVPN Splunk Assurance/  # Streaming telemetry assurance
├── campus_evpn_assurance/         # Packaged Splunk app
├── otel-collector/                # OpenTelemetry collector config
├── packaging/                     # Build scripts (.spl + handoff bundle)
├── mcp-ssh-server/                # MCP stdio server for CLI verification
├── Model Maps/                    # YANG → Splunk metric mappings
└── SETUP_GUIDE.md                 # Install procedure

DIAGRAMS/                          # Architecture diagrams (.mmd + .png)
Release Notes/                     # Dated feature and behavior change notes
test-cases/                        # Fabric validation scenarios
```

---

## 3. Template Architecture

### 3.1 Three Template Categories

| Category | Purpose | Output |
|----------|---------|--------|
| `DEFN-*.j2` | Data dictionaries — roles, loopbacks, VRFs, VLANs, L3OUT, NAC, telemetry | No CLI (only `{% set %}` blocks) |
| `FABRIC-*.j2` | CLI generators — include DEFN/FUNC, emit IOS-XE configuration | Role-aware IOS-XE CLI |
| `FUNC-*.j2` | Reusable Jinja macros for shared lookup/rendering logic | Macro definitions |

Every `.j2` file must begin with the device targeting header:
```jinja
{## CATC: productFamily=Switches and Hubs, softwareType=IOS-XE, productSeries=Cisco Catalyst 9000 Series Virtual Switches ##}
```

### 3.2 Composite Build Order (BGP-EVPN-BUILD.yml)

Only FABRIC templates appear in the composite; DEFN/FUNC files are resolved internally via `{% include %}`:

| Step | Template | Function | Depends On |
|------|----------|----------|-----------|
| 1 | `FABRIC-VRF.j2` | VRF definitions with RD/RT | — |
| 2 | `FABRIC-LOOPBACKS.j2` | Underlay + overlay loopbacks | VRF |
| 3 | `FABRIC-BORDER-DMZ-TUNNELS.j2` | GRE tunnels + OSPF 100 (borders only) | Loopbacks |
| 4 | `FABRIC-L3OUT.j2` | Spine-to-Core sub-interfaces | Loopbacks |
| 5 | `FABRIC-NVE.j2` | NVE + L3VNI/L2VNI membership | VRF, Loopbacks |
| 6 | `FABRIC-MCAST.j2` | PIM RP, MSDP, VRF MDT | NVE |
| 7 | `FABRIC-EVPN.j2` | BGP EVPN control plane + L3OUT BGP | All above |
| 8 | `FABRIC-OVERLAY.j2` | L2VNI overlay VLANs/EVPN instances | NVE, EVPN |
| 9 | `FABRIC-CLIENT-PORTS.j2` | Client-facing port provisioning | Overlay |
| 10 | `FABRIC-NAC.j2` | 802.1X/MAB access control | Client Ports |
| 11 | `FABRIC-TELEMETRY-SPLUNK.j2` | MDT telemetry subscriptions | NVE |

### 3.3 Per-Role Render Behavior

The same composite renders differently per device role based on `DEFN_NODE_ROLES` membership:

| Template | Spine/RR | Leaf | Border |
|----------|----------|------|--------|
| FABRIC-VRF | ✓ | ✓ | ✓ |
| FABRIC-LOOPBACKS | ✓ | ✓ | ✓ |
| FABRIC-BORDER-DMZ-TUNNELS | — | — | ✓ |
| FABRIC-L3OUT | ✓ (if in `DEFN_L3OUT_NODES`) | — | — |
| FABRIC-NVE | ✓ (L3VNI only, for route leaking) | ✓ | ✓ |
| FABRIC-MCAST | ✓ | ✓ | ✓ |
| FABRIC-EVPN | ✓ (RR config) | ✓ (client) | ✓ (client + DMZ eBGP) |
| FABRIC-OVERLAY | — | ✓ | ✓ |
| FABRIC-CLIENT-PORTS | — | ✓ | ✓ |
| FABRIC-NAC | — | ✓ | — |
| FABRIC-TELEMETRY-SPLUNK | ✓ | ✓ | ✓ |

> **Spine NVE/L3VNI is intentional**: Spines terminate L3VNI for VRF route leaking to the upstream IP Core via L3OUT sub-interfaces. Do not treat Spine NVE config as a bug.

### 3.4 Optional Components

| Feature | Enabled By | Disabled By |
|---------|------------|-------------|
| Border Leaf / Multi-Cluster | Add FQDNs to `DEFN_NODE_ROLES['BORDER']` | Leave `BORDER = []` |
| L3OUT to IP Core | Add nodes to `DEFN_L3OUT_NODES` | Set `DEFN_L3OUT_NODES = []` |
| GRE/DMZ Tunnels | Define entries in `DEFN_TUNNELS` | Omit `DEFN_TUNNELS` |
| Telemetry | Populate `DEFN_TELEMETRY_SPLUNK_ROLES` | Leave role list empty |

---

## 4. Architecture Diagrams

### 4.1 Conceptual Data Model

![BGP EVPN Presentation Data Model](DIAGRAMS/bgp-evpn-data-model-presentation.png)

> Source: `DIAGRAMS/bgp-evpn-data-model-presentation.mmd`

- DEFN templates are the **intent layer** (roles, addressing, tenants, policy, numbering)
- FUNC templates are the **transformation layer** (intent → device-local objects)
- FABRIC templates are the **rendering layer** (emit IOS-XE CLI in dependency order)
- The composite binds the render pipeline to Catalyst Center provisioning at the site level

### 4.2 Detailed Data Model

![BGP EVPN Data Model Relationships](DIAGRAMS/bgp-evpn-data-model.png)

> Source: `DIAGRAMS/bgp-evpn-data-model.mmd`

Key relationships:
- `DEFN-VRF.j2` + `FUNC-VRF-LOOKUP.j2` form the core binding between intent and per-device rendering
- `DEFN-OVERLAY.j2`, `DEFN-VNIOFFSETS.j2`, and `DEFN-LOOPBACKS.j2` provide numeric/addressing context consumed by multiple FABRIC templates
- Optional behaviors (L3OUT, multicast RP, client ports, NAC, telemetry) are each activated by dedicated DEFN structures

### 4.3 Template Dependency Flow

![BGP EVPN Template Relationships](DIAGRAMS/bgp-evpn-template-relationships.png)

> Source: `DIAGRAMS/bgp-evpn-template-relationships.mmd`

### 4.4 Per-Role Render Behavior

![BGP EVPN Per-Role Render Behavior](DIAGRAMS/bgp-evpn-role-behavior.png)

> Source: `DIAGRAMS/bgp-evpn-role-behavior.mmd`

### 4.5 Catalyst Center Operational Lifecycle

![BGP EVPN Catalyst Center Lifecycle](DIAGRAMS/bgp-evpn-catalyst-center-lifecycle.png)

> Source: `DIAGRAMS/bgp-evpn-catalyst-center-lifecycle.mmd`

Lifecycle phases:
1. **Template Preparation**: Populate DEFN intent → Git → Ansible sync to CatC Template Editor
2. **Template Binding**: Attach composite to CLI Network Profile → assign to building site
3. **Provisioning**: CatC renders per-device CLI using `__device.hostname` → pushes to fabric nodes
4. **Assurance**: Fabric nodes stream YANG telemetry (gRPC/MDT) → OTel collector → Splunk dashboards
5. **Day-2 Change**: Update DEFN data → resync → re-provision

---

## 5. Data Model Reference

### 5.1 Key Data Structures

| Variable | Source | Structure |
|----------|--------|-----------|
| `DEFN_NODE_ROLES` | DEFN-ROLES.j2 | `{'SPINE':[], 'RR':[], 'CLIENT':[], 'BORDER':[], 'MCLUSTER':[]}` |
| `DEFN_VRF` | DEFN-VRF.j2 | List of `{'id':'901','name':'red','mdt_default':'...','mdt_data':'...'}` |
| `DEFN_VRF_TO_NODE` | DEFN-VRF.j2 | `{'hostname.fqdn': ['901','902']}` |
| `DEFN_LOOP_UNDERLAY` | DEFN-LOOPBACKS.j2 | `{'hostname.fqdn': '198.19.1.x'}` |
| `DEFN_LOOP_GRE_SRC` | DEFN-LOOPBACKS.j2 | `{'hostname.fqdn': '10.100.2.x'}` |
| `DEFN_LOOP_GRE_PEER` | DEFN-LOOPBACKS.j2 | `{'hostname.fqdn': '10.101.x.2'}` |
| `DEFN_LOOP_MCLUSTER` | DEFN-LOOPBACKS.j2 | `{'hostname.fqdn': {'ip':'...','asn':'...','gre_src':'...'}}` |
| `DEFN_OVERLAY` | DEFN-OVERLAY.j2 | VLANs per VRF with SVI params |
| `FABRIC_BGP_ASN` | DEFN-OVERLAY.j2 | Fabric ASN string (e.g., `'65001'`) |

### 5.2 VNI Numbering Convention

| Component | Formula | Example (VRF red, VLAN 101) |
|-----------|---------|----------------------------|
| L3VNI | `50 + VRF_ID` | 50 + 901 = **50901** |
| L2VNI | `50000 + VLAN_ID` | 50000 + 101 = **50101** |
| RD | `{loopback_ip}:{vrf_id}` | `198.19.1.3:901` |
| RT | `{fabric_asn}:{vrf_id}` | `65001:901` |

Offsets defined in `DEFN-VNIOFFSETS.j2`:
```jinja
{% set L2VNIOFFSET = 50000 %}
{% set L3VNIOFFSET = 50 %}
```

### 5.3 VLAN-to-VNI Mapping

| VLAN | Name | L2VNI | VRF | BUM Multicast |
|------|------|-------|-----|---------------|
| 101 | corp-101 | 50101 | red | 239.190.100.101 |
| 102 | corp-102 | 50102 | red | 239.190.100.102 |
| 201 | iot-blue-201 | 50201 | blue | 239.190.100.201 |
| 221 | iot-green-221 | 50221 | green | 239.190.100.221 |
| 901 | L3-VRF-CORE-901 | 50901 | red | — (transit) |
| 902 | L3-VRF-CORE-902 | 50902 | blue | — (transit) |
| 903 | L3-VRF-CORE-903 | 50903 | green | — (transit) |

### 5.4 VRF Overlay Loopback Addressing

| VRF | Loopback | Leaf-01 | Leaf-02 | Border-01 | Border-02 |
|-----|----------|---------|---------|-----------|-----------|
| red | Lo901 | 10.1.100.3/32 | 10.1.100.4/32 | — | — |
| blue | Lo902 | 10.1.200.3/32 | 10.1.200.4/32 | 10.1.200.5/32 | 10.1.200.6/32 |
| green | Lo903 | 10.1.220.3/32 | 10.1.220.4/32 | 10.1.220.5/32 | 10.1.220.6/32 |

Spines do **not** receive overlay loopbacks — they function as control-plane RRs and L3OUT termination points, not edge forwarding nodes.

---

## 6. BGP EVPN Control Plane

### 6.1 Address Families

| Address Family | Purpose | Spine Behavior | Leaf/Border Behavior |
|----------------|---------|----------------|---------------------|
| `l2vpn evpn` | MAC/IP distribution (RT-2, RT-3) | `additional-paths send receive` | `additional-paths receive` |
| `ipv4 mvpn` | Multicast VPN signaling (TRM) | Reflect to clients | Signal RP reachability |
| `ipv4 vrf <name>` | Per-tenant L3 unicast | L3OUT eBGP to Core (if enabled) | `redistribute connected` |

### 6.2 Convergence Optimization

| Knob | Scope | Effect |
|------|-------|--------|
| `bgp additional-paths send receive` | Spine RRs | Advertise multiple paths for fabric-wide diversity |
| `bgp additional-paths receive` | Leaf/Border | Store alternate paths for sub-second failover |
| `bgp nexthop trigger delay 0` | All nodes | Immediate next-hop reachability processing |
| `fall-over route-map NODE-LOOPBACKS` | EVPN peers | Tear down session when peer loopback unreachable |

### 6.3 L3OUT BGP (Spine-to-Core)

Spine nodes configured in `DEFN_L3OUT_NODES` render per-VRF eBGP sessions to the IP Core over dot1Q sub-interfaces:

```
address-family ipv4 vrf red
 advertise l2vpn evpn
 neighbor <CORE-IP> remote-as 65002
```

East-west protection via Null0 routes prevents cross-tenant leakage through the L3OUT path.

![Spine-to-Core Connectivity](DIAGRAMS/cisco_evpn_core_interface.png)

---

## 7. Underlay Services

### 7.1 OSPF IGP (Unicast Reachability)

OSPF area 0 provides loopback reachability across all fabric nodes. Loopback0 serves as BGP router-ID, NVE source, and OSPF router-ID:

```
interface Loopback0
 ip address 198.19.1.X 255.255.255.255
 ip pim sparse-mode
 ip ospf 1 area 0
!
router ospf 1
 router-id 198.19.1.X
```

### 7.2 PIM + MSDP (Multicast for BUM Replication)

| Component | Value | Function |
|-----------|-------|----------|
| Fabric Anycast RP | 198.19.1.100 | Shared on Lo2 of both Spines |
| MSDP peering | Spine-01 ↔ Spine-02 via Lo0 | RP redundancy and source sync |
| PIM mode | Sparse | All fabric interfaces |

```
ip pim spt-threshold 0
ip pim rp-address 198.19.1.100
ip msdp peer 198.19.1.X connect-source Loopback0 remote-as 65001
```

---

## 8. Deployment Operations

### 8.1 GitOps Workflow (Ansible)

The vendored pipeline at [`CICD Pipeline/7.0-Cisco-Catalyst-Center-Templates-Github-integration/`](CICD%20Pipeline/7.0-Cisco-Catalyst-Center-Templates-Github-integration/) performs:

1. Fetch `.j2` templates from Git repository
2. Enrich each template with Git commit metadata (version description + diff header)
3. Read `BGP-EVPN-BUILD.yml` to determine composite ordering
4. Sync to Catalyst Center Template Project via `cisco.dnac.template_workflow_manager`
5. Create/update `BGP-EVPN-BUILD` composite and bind to CLI Network Profile

The playbook supports **multiple subfolders** (`git_repo_subfolders` in `inventory.yml`), each synced to its own CatC project. See the [pipeline README](CICD%20Pipeline/7.0-Cisco-Catalyst-Center-Templates-Github-integration/README.md) for configuration details.

### 8.2 Provisioning Workflow

| Step | Action | Where |
|------|--------|-------|
| 1 | Verify site hierarchy exists | CatC: Design > Network Hierarchy |
| 2 | Verify devices discovered + assigned to site | CatC: Provision > Inventory |
| 3 | Verify underlay OSPF operational | Device CLI: `show ip ospf neighbor` |
| 4 | Import/sync templates | Ansible `ansible-git-catc.yml` |
| 5 | Attach composite to CLI Network Profile | CatC: Design > Network Profiles |
| 6 | Assign profile to building site | CatC: Design > Network Profiles |
| 7 | Provision devices | CatC: Provision > Inventory (or Ansible playbook) |

### 8.3 Deployment Phases

**Phase 1 — Foundation** (Steps 1-2): VRF isolation + loopback addressing
**Phase 2 — Transport** (Steps 3-5): GRE tunnels, L3OUT, NVE, Multicast
**Phase 3 — Control Plane** (Steps 6-7): BGP EVPN peering, L2VNI overlay
**Phase 4 — Services** (Steps 8-11): Client ports, NAC, telemetry

---

## 9. Splunk Assurance Integration

### 9.1 Telemetry Pipeline

`FABRIC-TELEMETRY-SPLUNK.j2` provisions IOS-XE Model-Driven Telemetry (MDT) subscriptions on each fabric node:

```
Fabric nodes (MDT/YANG, gRPC dial-out) → OpenTelemetry collector → splunk_hec → index=evpn_assurance → campus_evpn_assurance dashboards
```

### 9.2 Components

| Component | Purpose |
|-----------|---------|
| `campus_evpn_assurance/` | Packaged Splunk app (executive, Spine, Leaf, Border, Alerts dashboards) |
| `otel-collector/` | OpenTelemetry config: YANG gRPC → `splunk_hec` |
| `packaging/` | Build scripts for `.spl` package and customer handoff bundle |
| `SETUP_GUIDE.md` | Install workflow for Splunk app + patched `otelcol-yangfix` |
| `Model Maps/` | YANG → Splunk metric model mappings |
| `mcp-ssh-server/` | MCP stdio server for live device CLI verification during triage |

The assurance suite shares the same fabric model (roles, tenants, VNIs, loopbacks) as the provisioning templates, so dashboard logic maps directly onto what was provisioned.

See [`Campus BGP EVPN Splunk Assurance/README.md`](Campus%20BGP%20EVPN%20Splunk%20Assurance/README.md) and [`SETUP_GUIDE.md`](Campus%20BGP%20EVPN%20Splunk%20Assurance/SETUP_GUIDE.md) for details.

---

## 10. IOS-XE Configuration Architecture

### 10.1 CLI Dependency Hierarchy

![IOS-XE BGP EVPN CLI Hierarchy](DIAGRAMS/cisco_evpn_CLI_hierarchy.png)

Configuration must be applied in strict dependency order:

```
VRF DEFINITION
 └─ LOOPBACK INTERFACES (Lo0 underlay, Lo901+ overlay)
     └─ VLAN + L3VNI SVI (transit VLANs 901-903)
         └─ NVE INTERFACE (source Lo0, member VNIs)
             └─ BGP EVPN CONTROL PLANE (iBGP to RRs, EVPN/MVPN AFs)
                 └─ L2VPN EVPN INSTANCES (per-VLAN EVPN binding)
                     └─ GLOBAL L2VPN EVPN (replication-type, default-gateway advertise)
```

### 10.2 Template-to-Component Mapping

| Template | CLI Deliverables |
|----------|-----------------|
| `FABRIC-VRF.j2` | `vrf definition`, RD/RT |
| `FABRIC-LOOPBACKS.j2` | `interface Loopback0/901-903`, PIM, OSPF |
| `FABRIC-BORDER-DMZ-TUNNELS.j2` | `interface Tunnel10/11`, `router ospf 100` |
| `FABRIC-L3OUT.j2` | Dot1Q sub-interfaces, Null0 routes |
| `FABRIC-NVE.j2` | `interface nve1`, L3VNI VLANs/SVIs, `vlan configuration` |
| `FABRIC-MCAST.j2` | `ip pim`, `ip msdp`, VRF MDT |
| `FABRIC-EVPN.j2` | `router bgp`, peer templates, all AFs |
| `FABRIC-OVERLAY.j2` | L2VNI VLANs, `l2vpn evpn instance`, anycast GW SVIs |
| `FABRIC-CLIENT-PORTS.j2` | Access port config, trunk/access modes |
| `FABRIC-NAC.j2` | 802.1X/MAB policies |
| `FABRIC-TELEMETRY-SPLUNK.j2` | `telemetry ietf subscription`, `receiver` |

### 10.3 Global L2VPN EVPN (Leaf Only)

```
l2vpn evpn
 replication-type static
 router-id Loopback0
 default-gateway advertise
```

Spines do not configure this block — they do not participate in L2 forwarding.

---

## 11. FABRIC Template Detail

### FABRIC-VRF.j2
Creates VRF containers with per-device RD (`loopback_ip:vrf_id`) and fabric-wide RT (`asn:vrf_id`). Applied to all nodes listed in `DEFN_VRF_TO_NODE`.

### FABRIC-LOOPBACKS.j2
- **Loopback0**: Underlay identity (BGP RID, NVE source, OSPF RID)
- **Loopback901-903**: Per-VRF overlay loopbacks (leaves/borders only)
- **Loopback1/2** (borders): GRE source and EVPN overlay identity
- Overlay formula: `DEFN_LOOP_OVERLAY[vrf] + last_octet(Lo0)`

### FABRIC-BORDER-DMZ-TUNNELS.j2
GRE tunnels sourced from Lo1 with OSPF 100 underlay. Rendered only on `DEFN_NODE_ROLES['BORDER']` nodes when `DEFN_TUNNELS` is defined.

### FABRIC-L3OUT.j2
Dot1Q sub-interfaces on Spines for per-VRF routing to the IP Core. East-west Null0 routes prevent cross-tenant leakage. Auto-skipped when `DEFN_L3OUT_NODES = []`.

### FABRIC-NVE.j2
L3VNI VLANs (transit), L2VNI VLANs (segment), NVE member VNI assignments with multicast groups. Spines receive L3VNI config for route leaking.

### FABRIC-MCAST.j2
Global PIM sparse-mode, Anycast RP on Lo2, MSDP inter-spine peering, per-VRF MDT configuration.

### FABRIC-EVPN.j2
BGP router config with role-based peer templates. RRs: `send receive` + `route-reflector-client`. Clients: `receive` only. Includes L3OUT eBGP (conditional) and DMZ eBGP (conditional on `BORDER` + `MCLUSTER` roles).

### FABRIC-OVERLAY.j2
L2VPN EVPN instances per segment VLAN, anycast gateway SVIs with DHCP relay. Leaves/Borders only.

### FABRIC-NAC.j2
802.1X/MAB policy-maps for device classification and dynamic VLAN assignment. Leaves only.

### FABRIC-TELEMETRY-SPLUNK.j2
IOS-XE MDT subscriptions (gRPC dial-out) for EVPN, NVE, and interface YANG models. Rendered on nodes in `DEFN_TELEMETRY_SPLUNK_ROLES`.

---

## 12. Verification and Troubleshooting

### 12.1 Post-Deployment Checks

```
show ip ospf neighbor                    ! OSPF adjacencies (FULL)
show bgp l2vpn evpn summary             ! EVPN peers (Established)
show nve interface                       ! NVE tunnel status + VNI list
show l2vpn evpn summary                  ! L2VPN instance state
show vrf                                 ! VRF presence and RD
show ip route vrf red                    ! Per-VRF routing table
show mac address-table dynamic           ! MAC learning across fabric
```

### 12.2 Common Failure Modes

| Symptom | Root Cause | Resolution |
|---------|-----------|-----------|
| BGP EVPN peer stuck in Active | FQDN mismatch between DEFN and CatC inventory | Verify hostnames: `show inventory \| include NAME` |
| NVE tunnel down | Loopback0 unreachable across underlay | Verify OSPF: `ping <peer-Lo0>`, `show ip ospf neighbor` |
| L2VPN instances not activating | L3VNI VLAN/SVI missing | Verify FABRIC-NVE output includes `interface Vlan901` |
| BUM replication failure | RP unreachable or MSDP down | `ping 198.19.1.100`, `show ip msdp peer` |
| Border-DMZ EVPN down | GRE tunnel INIT / OSPF 100 not FULL | Check tunnel state, verify no Lo1 IP conflict with core |
| Template renders empty | Device not in `DEFN_VRF_TO_NODE` | Add FQDN to node mapping in `DEFN-VRF.j2` |

---

## 13. Appendix: Catalyst Center Jinja2 Engine Caveats

### 13.1 Unsupported Constructs

| Unsupported | Workaround |
|-------------|------------|
| `not in` operator | `{% if dict[key] is not defined %}` |
| `.keys()` method | Iterate companion list |
| `{% for k, v in dict.items() %}` | Iterate companion list, then `dict[k]` |
| `.split('.')` | `.split('\\.')` (CatC treats `.` as regex wildcard) |
| Complex nested expressions | Break into simpler steps |

### 13.2 Dict Iteration in Included Scope (Critical)

Any dict defined in an included `DEFN-*.j2` file must have a **companion flat list** for iteration. Dict-key iteration is non-deterministic in CatC's included-scope engine — the loop variable may resolve to the value object instead of the key string.

**Pattern**:
```jinja
{# DEFN file: define both #}
{% set DEFN_ALL_NODES = ['spine01.fqdn', 'leaf01.fqdn'] %}
{% set DEFN_LOOP_UNDERLAY = {'spine01.fqdn': '198.19.1.1', 'leaf01.fqdn': '198.19.1.3'} %}

{# FABRIC file: iterate the list, lookup from the dict #}
{% for node in DEFN_ALL_NODES %}
ip prefix-list LOOPBACKS seq {{loop.index}} permit {{DEFN_LOOP_UNDERLAY[node]}}/32
{% endfor %}
```

**Existing companion lists**:

| List | Dict | Usage |
|------|------|-------|
| `DEFN_ALL_NODES` | `DEFN_LOOP_UNDERLAY` | Fabric node loopback IPs |
| `DEFN_NODE_ROLES['MCLUSTER']` | `DEFN_LOOP_MCLUSTER` | Remote multi-cluster peers |

### 13.3 `.split()` Escaping

```jinja
{% set last_octet = DEFN_LOOP_UNDERLAY[DEVICE_HOSTNAME].split('\\.')[3] %}
```

---

## 14. Adding New Fabric Elements

### New Device
1. `DEFN-ROLES.j2` — Add FQDN to appropriate role lists
2. `DEFN-LOOPBACKS.j2` — Add to `DEFN_LOOP_UNDERLAY` dict + `DEFN_ALL_NODES` list (+ GRE/MCLUSTER if border)
3. `DEFN-VRF.j2` — Add VRF ID list to `DEFN_VRF_TO_NODE`

### New VRF
1. `DEFN-VRF.j2` — Add VRF object to `DEFN_VRF` list + add node mappings to `DEFN_VRF_TO_NODE`
2. `DEFN-OVERLAY.j2` — Add VLAN definitions under the new VRF

### New VLAN
Add entry to `DEFN_OVERLAY` under the correct VRF:
```jinja
'102': {'name':'corp-102', 'ipaddr':'10.1.12.1 255.255.255.0', 'mac':'0000.0901.0102',
        'dhcp_helper':'198.18.5.253', 'bum_addr':'239.190.100.102', 'network':'10.1.12.0 255.255.255.0'}
```

---
