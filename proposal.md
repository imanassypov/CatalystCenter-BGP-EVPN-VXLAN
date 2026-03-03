# Cisco Catalyst Center BGP EVPN VXLAN Automation
## Executive Proposal

---

## Slide 1: Executive Summary

### Modernizing Campus Networks with Controller-Driven Automation

**The Challenge:** Enterprise campus networks face mounting pressure to deliver agility, segmentation, and security at scale—while reducing operational complexity and time-to-value.

**The Solution:** A comprehensive Cisco Catalyst Center template framework that automates BGP EVPN VXLAN fabric deployment on Catalyst 9000 switches, enabling Infrastructure-as-Code workflows with full GitOps integration.

**Key Outcomes:**
- **80% reduction** in fabric provisioning time
- **Zero-touch** multi-tenant segmentation
- **Line-rate encryption** for IOT traffic isolation
- **Repeatable, auditable** deployments via Git version control

---

## Slide 2: Agenda

1. Business Challenges & Use Cases
2. Solution Architecture
3. Template Framework Design
4. GitOps Integration
5. Implementation Approach
6. Business Value & ROI
7. Platform Requirements
8. Next Steps

---

## Slide 3: Business Challenges Addressed

| Challenge | Impact | How We Solve It |
|-----------|--------|-----------------|
| **Manual Configuration at Scale** | Error-prone, slow deployments across 100s of switches | Template-driven automation with role-aware configuration generation |
| **Traffic Segmentation Complexity** | Difficulty isolating corporate vs. IOT workloads | Multi-VRF architecture with automatic RT/RD assignment |
| **Security for IOT Segments** | IOT devices require isolated, encrypted transport to DMZ | IPSEC-over-VXLAN with hardware-accelerated 100G encryption |
| **Multicast in Overlay Networks** | Traditional multicast breaks in VXLAN environments | Tenant Routable Multicast (TRM) with Anycast RP |
| **Audit & Compliance** | No visibility into configuration drift | GitOps workflow with commit-level traceability |

---

## Slide 4: Target Use Cases

### 1. Large-Scale Campus Fabric Deployment
- Spine-leaf architecture across multiple buildings
- Consistent configuration across hundreds of Catalyst 9000 switches
- Centralized policy management via Catalyst Center

### 2. Multi-Tenant Enterprise Segmentation
- **Corporate tenants** (VRF red): User traffic with full enterprise services access
- **IOT tenants** (VRF blue/green): Isolated segments with dedicated DHCP/DNS
- Dynamic VLAN-to-VNI mapping with automatic EVPN instance creation

### 3. Secure IOT Edge-to-DMZ Transport
- Hardware-accelerated IPSEC tunnels (Catalyst 9300X)
- Extend segmentation across campus boundaries to centralized DMZ
- Firewall inspection for all IOT traffic before northbound routing

### 4. Enterprise Multicast Optimization
- Tenant Routable Multicast (TRM) for video, voice, and collaboration
- Anycast RP for redundancy and load distribution
- Per-VRF multicast domains with dedicated group ranges

---

## Slide 5: Solution Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CISCO CATALYST CENTER                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Template   │  │  Network    │  │  Provision  │                 │
│  │  Editor     │  │  Profiles   │  │  Workflow   │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
└─────────┼────────────────┼────────────────┼─────────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    BGP EVPN VXLAN FABRIC                            │
│                                                                     │
│    ┌──────────┐              ┌──────────┐                          │
│    │  SPINE1  │◄────────────►│  SPINE2  │   Route Reflectors       │
│    │   (RR)   │   iBGP EVPN  │   (RR)   │   Anycast RP             │
│    └────┬─────┘              └────┬─────┘                          │
│         │                        │                                  │
│    ─────┼────────────────────────┼─────────────────────            │
│         │        VXLAN Fabric    │                                  │
│    ┌────┴────┐  ┌────┴────┐  ┌────┴────┐                           │
│    │  LEAF1  │  │  LEAF2  │  │  LEAF3  │   EVPN Clients            │
│    │ VRF:R,B,G│ │ VRF:R,B,G│ │ VRF:R,B,G│  Multi-Tenant            │
│    └─────────┘  └─────────┘  └─────────┘                           │
│                                                                     │
│    ┌──────────┐              ┌──────────┐                          │
│    │ BORDER1  │◄────────────►│ BORDER2  │   IPSEC Gateways         │
│    │  IPSEC   │   HA Pair    │  IPSEC   │   Multi-Cluster BGP      │
│    └────┬─────┘              └────┬─────┘                          │
└─────────┼────────────────────────┼──────────────────────────────────┘
          │      IPSEC Tunnels     │
          ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DMZ FABRIC                                  │
│              Centralized Firewall Inspection                        │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Architecture Components:**
- **Spine Layer:** BGP Route Reflectors + Anycast RP for multicast
- **Leaf Layer:** Multi-tenant VRF instances with L2/L3 overlays
- **Border Layer:** IPSEC gateways for secure inter-site transport
- **Control Plane:** iBGP EVPN with Type-2 (MAC/IP) and Type-5 (IP Prefix) routes

---

## Slide 6: Template Framework Design

### Modular Template Architecture

| Layer | Templates | Purpose |
|-------|-----------|---------|
| **Data Definitions** | `DEFN-ROLES.j2`, `DEFN-VRF.j2`, `DEFN-LOOPBACKS.j2`, `DEFN-OVERLAY.j2` | Device roles, VRF mappings, IP assignments |
| **CLI Generation** | `FABRIC-VRF.j2`, `FABRIC-EVPN.j2`, `FABRIC-NVE.j2`, `FABRIC-OVERLAY.j2` | Role-aware IOS-XE configuration |
| **Reusable Logic** | `FUNC-OBJECT-MACROS.j2` | VRF resolution, object lookups |

### Automated Configuration Flow

```
1. Define Data          2. Assign Roles         3. Provision
   ─────────────────►      ─────────────────►      ─────────────────►
   
   DEFN-VRF.j2            DEFN-ROLES.j2          Catalyst Center
   DEFN-OVERLAY.j2        DEFN-LOOPBACKS.j2      renders per-device
   DEFN-IPSEC.j2          DEFN-VRF-TO-NODE       IOS-XE CLI
```

### Role-Aware Rendering
Templates automatically adapt output based on device role:
- **Spines:** Route Reflector config, Anycast RP, no NVE interfaces
- **Leafs:** EVPN client, NVE with VNI mappings, SVI configurations
- **Borders:** IPSEC tunnels, Multi-Cluster BGP, VRF handoff

---

## Slide 7: GitOps Integration

### Infrastructure-as-Code Workflow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Engineer  │────►│    Git      │────►│   Ansible   │────►│  Catalyst   │
│   Commits   │     │  Repository │     │  Automation │     │   Center    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    Version Control
                    Change Tracking
                    Rollback Capability
```

**Benefits:**
- **Auditability:** Every change tracked with Git commit messages
- **Collaboration:** Pull request reviews before production deployment
- **Rollback:** Instant revert to any previous configuration state
- **CI/CD Ready:** Integrate with Jenkins, GitHub Actions, or GitLab CI

**Companion Automation:** [Cisco-Catalyst-Center-Templates-Github-integration](https://github.com/imanassypov/Cisco-Catalyst-Center-Templates-Github-integration)

---

## Slide 8: Implementation Approach

### Phase 1: Foundation (Week 1-2)
- [ ] Deploy Catalyst Center and discover fabric switches
- [ ] Establish underlay connectivity (OSPF, Loopback0)
- [ ] Configure template project and import Jinja2 templates
- [ ] Customize `DEFN-ROLES.j2` with device FQDNs

### Phase 2: Fabric Build (Week 3-4)
- [ ] Define VRFs and tenant segmentation in `DEFN-VRF.j2`
- [ ] Configure overlay networks in `DEFN-OVERLAY.j2`
- [ ] Create Network Profile and associate to site
- [ ] Provision Spine and Leaf switches

### Phase 3: Advanced Services (Week 5-6)
- [ ] Enable Tenant Routable Multicast (TRM)
- [ ] Configure Border switches for IPSEC transport (if required)
- [ ] Integrate NAC/802.1X for IOT authentication
- [ ] Validate end-to-end connectivity and failover

### Phase 4: Operationalize (Week 7-8)
- [ ] Implement GitOps workflow with Ansible automation
- [ ] Document runbooks and operational procedures
- [ ] Train network operations team
- [ ] Establish change management processes

---

## Slide 9: Business Value & ROI

### Quantified Benefits

| Metric | Traditional Approach | With Automation | Improvement |
|--------|---------------------|-----------------|-------------|
| **Fabric Deployment Time** | 2-3 weeks | 2-3 days | **80% faster** |
| **Configuration Errors** | 15-20% rework rate | <2% with validation | **90% reduction** |
| **Time to Add New Tenant** | 4-8 hours | 15-30 minutes | **95% faster** |
| **Change Documentation** | Manual, often incomplete | Automatic via Git | **100% audit trail** |

### Strategic Value
- **Agility:** Respond to business requirements in hours, not weeks
- **Consistency:** Identical configurations across all fabric nodes
- **Security:** Hardened templates with best-practice defaults
- **Scalability:** Add new sites by replicating template project
- **Compliance:** Full audit trail for regulatory requirements

---

## Slide 10: Platform Requirements

### Supported Hardware
| Platform | Role | Notes |
|----------|------|-------|
| Catalyst 9500 | Spine, Border | High-density 100G uplinks |
| Catalyst 9400 | Distribution Leaf | Modular chassis flexibility |
| Catalyst 9300 | Access Leaf | Stackable access deployment |
| Catalyst 9300X | Border (IPSEC) | Hardware-accelerated crypto |

### Software Requirements
- **IOS-XE:** 17.12.x minimum, 17.15.3 recommended
- **Catalyst Center:** 2.3.7.9 or later
- **Ansible:** 2.14+ with `cisco.dnac` collection

### Licensing
- Cisco DNA Advantage or Premier license
- BGP EVPN VXLAN feature set (included in DNA licenses)

---

## Slide 11: Next Steps

### Recommended Engagement Path

1. **Discovery Workshop** (1 day)
   - Review current network architecture
   - Identify segmentation and security requirements
   - Define success criteria and timeline

2. **Proof of Concept** (2 weeks)
   - Deploy in Cisco Modeling Labs (CML) environment
   - Validate template framework with customer topology
   - Demonstrate end-to-end automation workflow

3. **Pilot Deployment** (4 weeks)
   - Deploy to single campus site
   - Integrate with existing Catalyst Center
   - Train operations team on GitOps workflow

4. **Production Rollout** (Phased)
   - Expand to additional sites
   - Customize templates for site-specific requirements
   - Establish ongoing support model

---

## Contact Information

| Role | Name | Email |
|------|------|-------|
| Systems Engineer | Igor Manassypov | imanassy@cisco.com |
| Technical Solutions Architect | Keith Baldwin | kebaldwi@cisco.com |

**Resources:**
- [Template Repository](https://github.com/imanassypov/Cisco-Catalyst-Center-Templates-Github-integration)
- [Cisco DNA Center Ansible Collection](https://galaxy.ansible.com/cisco/dnac)
- [BGP EVPN VXLAN Design Guide](https://www.cisco.com/c/en/us/solutions/design-zone/networking-design-guides/campus.html)

---

*© 2024-2026 Cisco Systems, Inc. All rights reserved.*
