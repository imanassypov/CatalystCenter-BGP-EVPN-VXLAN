# Cisco Catalyst Center BGP EVPN VXLAN Campus Fabric Templates

## Project Overview

This repository contains a comprehensive collection of Cisco Catalyst Center CLI templates designed to provision and manage Campus BGP EVPN VXLAN fabric infrastructure using Cisco Catalyst 9000 series switches running IOS-XE. The templates are organized into a structured deployment sequence that enables automated configuration of modern campus network fabrics with advanced overlay capabilities.

## Scope and Intent

The template collection provides a complete solution for:
- **Campus BGP EVPN VXLAN Fabric Deployment**: Automated provisioning of spine-leaf architectures with EVPN control plane
- **Multi-Tenancy Support**: VRF-aware configurations with isolated tenant networks
- **Overlay Network Services**: L2 and L3 overlay services with VXLAN encapsulation
- **Multicast Optimization**: PIM-based multicast distribution with anycast RP
- **Border Gateway Integration**: External connectivity through border leaf switches

## Architecture Support

**Supported Platforms:**
- Cisco Catalyst 9500 Series Switches
- Cisco Catalyst 9400 Series Switches  
- Cisco Catalyst 9300 Series Switches
- Cisco Catalyst 9000 Series Virtual Switches
- IPSEC functionality requires Cisco Catalyst 9300X for hardware-accelerated IPSEC crypto function

**Software Requirements:**
- IOS-XE 17.15.3. Note that 17.12.x is also supported with the exception of Multi-Cluster BGP EVPN (ie Border Switches can run 17.15.3 while the rest of the fabric can operate on 17.12.x)
- Cisco Catalyst Center 2.3.7.9

**High Level CAMPUS-CORE-DMZ Routing Topology**
![Alt text](images/cisco_evpn_ASN.pngimage.png)

## Template Structure

The project contains two main categories of templates located in the `BGP EVPN/` folder:

### 1. Definition Templates (DEFN-*)
State and input variable definitions that store fabric-wide parameters:

#### **DEFN-ROLES**
- **Purpose**: Defines device roles within the EVPN fabric topology (Spine, Leaf, Border Leaf, Route Reflector, Client)
- **Scope**: Node classification and role-based logic for configuration templates
- **Usage**: Referenced by all numbered templates to apply role-specific configurations

#### **DEFN-LOOPBACKS** 
- **Purpose**: IP address assignments for underlay and overlay loopback interfaces
- **Scope**: Fabric-wide loopback addressing including anycast RP addresses (172.16.255.x range)
- **Usage**: Provides consistent addressing across all fabric nodes for BGP peering and VXLAN tunnels

#### **DEFN-VRF**
- **Purpose**: VRF definitions with route distinguishers and route targets
- **Scope**: Multi-tenant VRF parameters (red=901, blue=902, green=903)
- **Usage**: Defines tenant isolation boundaries and RT import/export policies

#### **DEFN-OVERLAY**
- **Purpose**: Overlay network definitions for L2/L3 services per VRF
- **Scope**: VLAN-to-VNI mappings, SVI configurations, DHCP relay, and BUM replication groups
- **Usage**: Maps tenant VLANs to VXLAN VNIs with associated IP addressing and multicast groups

#### **DEFN-VNIOFFSETS**
- **Purpose**: VNI offset values for VXLAN network identifier calculation
- **Scope**: L2VNI and L3VNI offset definitions for consistent VNI allocation
- **Usage**: Ensures non-overlapping VNI assignments across the fabric

#### **DEFN-L3OUT**
- **Purpose**: External connectivity parameters for border leaf switches
- **Scope**: L3 exit point configurations and external BGP peering interfaces
- **Usage**: Defines connectivity to external networks, WANs, and data centers

#### **DEFN-MCAST**
- **Purpose**: Multicast configuration parameters
- **Scope**: PIM sparse-mode settings and anycast RP configuration
- **Usage**: Supports VXLAN BUM traffic replication and multicast optimization

#### **DEFN-NAC-IOT**
- **Purpose**: Network Access Control and IoT device policies
- **Scope**: Class maps and policy maps for device authentication and authorization
- **Usage**: Provides micro-segmentation and device onboarding capabilities

### 2. Configuration Templates (1-7 Sequence)
Jinja2-based CLI templates located in `BGP EVPN/` that render actual device configurations:

#### **1. FABRIC-VRF.j2**
- **Purpose**: VRF instance configuration with route targets and export/import policies
- **Scope**: Creates tenant VRF definitions with proper route distribution for multi-tenancy
- **Target Devices**: All fabric nodes (Spine, Leaf, Border Leaf)
- **Dependencies**: DEFN-VRF, DEFN-ROLES, DEFN-LOOPBACKS
- **Function**: Establishes VRF routing domains with BGP RT configuration
- **Renders To**: VRF definition blocks in all node configs with RD assignment based on loopback IP

#### **2. FABRIC-LOOPBACKS.j2**
- **Purpose**: Loopback interface configuration for underlay and overlay services
- **Scope**: Configures system loopbacks for BGP peering and overlay VRF termination
- **Target Devices**: All fabric nodes with role-specific variations
- **Dependencies**: DEFN-LOOPBACKS, DEFN-ROLES, DEFN-VRF
- **Function**: Creates underlay Loopback0 and VRF-specific overlay loopbacks for non-spine nodes
- **Renders To**: Interface configuration blocks with PIM sparse-mode enabled

#### **3. FABRIC-NVE.j2**
- **Purpose**: Network Virtualization Edge (NVE) and L3VNI VLAN configuration
- **Scope**: VLAN creation and VNI mapping for L3 services per VRF
- **Target Devices**: Leaf and Border Leaf switches (excludes Spines)
- **Dependencies**: DEFN-VRF, DEFN-ROLES, DEFN-VNIOFFSETS
- **Function**: Creates L3VNI VLANs and maps them to L3VNIs for inter-subnet routing
- **Renders To**: VLAN and VLAN configuration blocks in Leaf/Border configs

#### **4. FABRIC-MCAST.j2**
- **Purpose**: Multicast routing and PIM configuration for VXLAN BUM traffic
- **Scope**: Global and VRF-specific multicast routing with anycast RP on spines
- **Target Devices**: All fabric nodes with role-specific anycast RP on spines
- **Dependencies**: DEFN-VRF, DEFN-ROLES, DEFN-LOOPBACKS, DEFN-MCAST
- **Function**: Enables multicast routing, configures anycast RP interface on spines
- **Renders To**: Multicast routing commands and anycast loopback interfaces

#### **5. FABRIC-EVPN.j2**
- **Purpose**: BGP EVPN peering, route reflector configuration, and L3OUT interfaces
- **Scope**: Establishes EVPN control plane with RR topology and external connectivity
- **Target Devices**: All fabric nodes with role-specific BGP configurations
- **Dependencies**: DEFN-ROLES, DEFN-LOOPBACKS, DEFN-VNIOFFSETS, DEFN-L3OUT
- **Function**: Creates BGP EVPN sessions, peer templates, and L3OUT interface configuration
- **Renders To**: Router BGP blocks with EVPN AF, peer sessions, and external interfaces

#### **6. FABRIC-OVERLAY.j2**
- **Purpose**: Overlay service configuration for tenant networks and L2 services
- **Scope**: EVPN instances, VLAN-to-VNI mapping, and SVI configuration per VRF
- **Target Devices**: Leaf and Border Leaf switches (excludes Spines for L2 config)
- **Dependencies**: DEFN-OVERLAY, DEFN-VRF, DEFN-VNIOFFSETS, DEFN-ROLES
- **Function**: Delivers L2VPN EVPN instances, SVIs, and BGP VRF address-families
- **Renders To**: L2VPN EVPN instances, VLAN configs, SVI interfaces, and BGP VRF sections

#### **7. FABRIC-NAC-IOT.j2**
- **Purpose**: Network Access Control and IoT device policy configuration
- **Scope**: Class maps, policy maps, and device authentication rules per VRF
- **Target Devices**: Access layer leaf switches where endpoints connect
- **Dependencies**: DEFN-VRF, DEFN-NAC-IOT
- **Function**: Provides micro-segmentation, device authentication, and policy enforcement
- **Renders To**: Class-map and policy-map configurations for device onboarding and security

## Initial Preparation
Before attempting to deploy the collection, the following DEFN Input Variables must be adjusted to suite your environment:
1. DEFN_LOOPBACKS: device hostnames must match those configured on the target devices, ie 'spine01.dcloud.cisco.com' must match
```
spine01#sh run | i hostname | domain
hostname spine01
ip domain lookup source-interface Loopback0
ip domain name dcloud.cisco.com
```
2. DEFN_ROLES: device hostanmes to match, same as (1) above
3. DEFN_L3OUT: Interface names, vlan id, and neighbor parameters must match your core-facing interface configuration, as well as core BGP ASN.

Ensure that basic underlay routing is configured and operational (ie OSPF neighbours are established, spines have BGP established towards the cores)

```
spine01#sh ip ospf neighbor 

Neighbor ID     Pri   State           Dead Time   Address         Interface
172.16.255.7      0   FULL/  -        00:00:39    172.16.16.6     GigabitEthernet1/0/5
172.16.255.6      0   FULL/  -        00:00:36    172.16.15.5     GigabitEthernet1/0/4
172.16.255.5      0   FULL/  -        00:00:33    172.16.14.5     GigabitEthernet1/0/3
172.16.255.4      0   FULL/  -        00:00:31    172.16.13.4     GigabitEthernet1/0/2
172.16.255.3      0   FULL/  -        00:00:32    172.16.12.3     GigabitEthernet1/0/1
```

```
spine02#sh ip ospf neighbor 

Neighbor ID     Pri   State           Dead Time   Address         Interface
172.16.255.7      0   FULL/  -        00:00:38    172.16.26.6     GigabitEthernet1/0/5
172.16.255.6      0   FULL/  -        00:00:31    172.16.25.5     GigabitEthernet1/0/4
172.16.255.5      0   FULL/  -        00:00:38    172.16.24.5     GigabitEthernet1/0/3
172.16.255.4      0   FULL/  -        00:00:36    172.16.23.4     GigabitEthernet1/0/2
172.16.255.3      0   FULL/  -        00:00:39    172.16.22.3     GigabitEthernet1/0/1
```

```
spine01#sh ip bgp summary 
BGP router identifier 172.16.255.1, local AS number 65001
BGP table version is 24, main routing table version 24
23 network entries using 5704 bytes of memory
24 path entries using 3264 bytes of memory
4/4 BGP path/bestpath attribute entries using 1184 bytes of memory
1 BGP AS-PATH entries using 40 bytes of memory
2 BGP extended community entries using 100 bytes of memory
0 BGP route-map cache entries using 0 bytes of memory
0 BGP filter-list cache entries using 0 bytes of memory
BGP using 10292 total bytes of memory
BGP activity 29/0 prefixes, 30/0 paths, scan interval 60 secs
23 networks peaked at 16:57:51 Aug 12 2025 UTC (00:01:52.693 ago)

Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
172.17.1.2      4        65002       7      10       24    0    0 00:03:00        1
172.17.2.2      4        65002       7      11       24    0    0 00:02:59        1
```

```
spine02#sh ip bgp summary 
BGP router identifier 172.16.255.2, local AS number 65001
BGP table version is 24, main routing table version 24
23 network entries using 5704 bytes of memory
24 path entries using 3264 bytes of memory
4/4 BGP path/bestpath attribute entries using 1184 bytes of memory
1 BGP AS-PATH entries using 40 bytes of memory
2 BGP extended community entries using 100 bytes of memory
0 BGP route-map cache entries using 0 bytes of memory
0 BGP filter-list cache entries using 0 bytes of memory
BGP using 10292 total bytes of memory
BGP activity 29/0 prefixes, 30/0 paths, scan interval 60 secs
23 networks peaked at 16:57:26 Aug 12 2025 UTC (00:02:37.869 ago)

Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
172.17.3.2      4        65002       7      10       24    0    0 00:02:38        1
172.17.4.2      4        65002       7      10       24    0    0 00:02:36        1
```

## Final Rendered Configurations

The `Node Configs/` folder contains the final rendered switch configurations that result from applying the above templates:

### **Spine Configurations (SPINE1.cfg, SPINE2.cfg)**
- **Role**: Route Reflectors and Anycast RP nodes
- **Key Features**: BGP RR configuration, anycast RP interfaces, MSDP peering
- **Templates Applied**: 1, 2, 4, 5 (excludes overlay L2 services and NVE)
- **Notable Config**: Route reflector clients, anycast loopback interfaces, VRF definitions

### **Leaf Configurations (LEAF1.cfg, LEAF2.cfg, LEAF3.cfg)**
- **Role**: EVPN clients providing overlay services to connected endpoints
- **Key Features**: NVE interfaces, L2VPN EVPN instances, SVI interfaces, overlay loopbacks
- **Templates Applied**: 1, 2, 3, 4, 5, 6, 7 (full template set)
- **Notable Config**: VXLAN tunnel endpoints, tenant SVIs, L2/L3 VNI mappings

### **Border Leaf Configurations (BORDER1.cfg, BORDER2.cfg)**
- **Role**: External connectivity gateways for campus fabric
- **Key Features**: L3OUT interfaces, external BGP peering, fabric edge services
- **Templates Applied**: 1, 2, 3, 4, 5, 6 (excludes NAC/IoT policies)
- **Notable Config**: External interfaces with VRF forwarding, BGP peering to external networks

### **DMZ Configuration (DMZ1.cfg)**
- **Role**: Demilitarized zone services and external connectivity
- **Key Features**: Security policies, external service interfaces
- **Templates Applied**: Subset based on DMZ role requirements
- **Notable Config**: Security-focused configurations for external service delivery

## Deployment Sequence

The templates should be deployed in numerical order (1-7) to ensure proper dependency resolution:

1. **Definition Templates**: Deploy all DEFN-* templates first to establish fabric parameters
2. **Foundation**: Deploy template 1 (FABRIC-VRF) for VRF establishment
3. **Infrastructure**: Deploy templates 2-4 (LOOPBACKS, NVE, MCAST) for basic fabric services
4. **Control Plane**: Deploy template 5 (FABRIC-EVPN) for BGP EVPN peering and L3OUT
5. **Data Plane**: Deploy template 6 (FABRIC-OVERLAY) for overlay services
6. **Security**: Deploy template 7 (FABRIC-NAC-IOT) for access control policies

## Template-to-Config Mapping

The following table shows how templates render into the final node configurations:

| Template | Spine | Leaf | Border | DMZ | Function |
|----------|-------|------|--------|-----|----------|
| 1. FABRIC-VRF | ✓ | ✓ | ✓ | ✓ | VRF definitions with RD/RT |
| 2. FABRIC-LOOPBACKS | ✓ | ✓ | ✓ | ✓ | Underlay + overlay loopbacks |
| 3. FABRIC-NVE | ✗ | ✓ | ✓ | ✓ | L3VNI VLANs (spines excluded) |
| 4. FABRIC-MCAST | ✓ | ✓ | ✓ | ✓ | Multicast + anycast RP |
| 5. FABRIC-EVPN | ✓ | ✓ | ✓ | ✓ | BGP EVPN + L3OUT interfaces |
| 6. FABRIC-OVERLAY | ✗ | ✓ | ✓ | ✓ | L2VPN instances + SVIs |
| 7. FABRIC-NAC-IOT | ✗ | ✓ | ✗ | ✗ | Access control policies |

## Template Walkthrough: Building BGP EVPN Campus Fabric

This section provides a detailed walkthrough of how each template contributes to building a Cisco IOS-XE Catalyst 9000 BGP EVPN VXLAN campus fabric:

### **Template 1: FABRIC-VRF.j2 - Foundation Layer**
**Campus Fabric Building Logic:**
- **VRF Creation**: Establishes isolated routing domains for tenant separation (red, blue, green VRFs)
- **Route Distinguisher Assignment**: Uses device's underlay loopback IP + VRF ID for unique RD per device per VRF
- **Route Target Configuration**: Sets up BGP EVPN import/export policies using AS:VRF_ID format
- **Multi-Tenancy Foundation**: Creates the fundamental isolation mechanism for campus network segmentation

**Jinja2 Logic Flow:**
1. Iterates through `vrf_list` parameter to process only selected VRFs
2. Resolves VRF objects from `DEFN_VRF` definitions 
3. Assigns unique RD using `DEFN_LOOP_UNDERLAY[__device.hostname]:vrf.id`
4. Configures RT import/export with `FABRIC_BGP_ASN:vrf.id` for tenant isolation
5. Applies to ALL fabric nodes regardless of role

### **Template 2: FABRIC-LOOPBACKS.j2 - Addressing Layer**
**Campus Fabric Building Logic:**
- **Underlay Infrastructure**: Configures Loopback0 as BGP router-ID and VXLAN source interface
- **Overlay Termination**: Creates VRF-specific loopbacks on leaf/border nodes for L3 service termination
- **PIM Integration**: Enables sparse-mode for multicast traffic distribution
- **Role-Based Logic**: Spines get only underlay loopbacks; leaves/borders get both underlay + overlay

**Jinja2 Logic Flow:**
1. Configures `DEFN_LOOP_NAME['UNDERLAY']` (Loopback0) on all devices with PIM sparse-mode
2. Uses `DEFN_LOOP_UNDERLAY[__device.hostname]` for device-specific addressing
3. Role check: IF NOT spine/border, THEN create overlay loopbacks per VRF
4. Overlay loopback addressing: `DEFN_LOOP_OVERLAY[vrf.name] + last_octet_of_underlay_IP`
5. VRF forwarding assignment for overlay loopbacks

### **Template 3: FABRIC-NVE.j2 - VXLAN Infrastructure**
**Campus Fabric Building Logic:**
- **L3VNI VLAN Creation**: Creates transit VLANs for inter-subnet routing within each VRF
- **VNI Mapping**: Maps L3VNI VLANs to corresponding VXLAN VNIs for routing traffic
- **SVI Configuration**: Creates unnumbered SVIs for L3VNI traffic processing
- **NVE Interface**: Establishes the VXLAN tunnel endpoint for overlay transport

**Jinja2 Logic Flow:**
1. Creates VLAN with `vrf.id` for each VRF (e.g., VLAN 901 for red VRF)
2. Maps VLAN to L3VNI using `L3VNIOFFSET + vrf.id` calculation
3. Creates unnumbered SVI interface referencing underlay loopback
4. Configures NVE1 interface with underlay loopback as source
5. Adds VNI-to-VRF membership on NVE interface

### **Template 4: FABRIC-MCAST.j2 - Multicast Foundation**
**Campus Fabric Building Logic:**
- **Global Multicast**: Enables IP multicast routing for BUM traffic handling
- **Anycast RP**: Configures redundant rendezvous points on spine switches
- **MSDP Peering**: Establishes spine-to-spine MSDP sessions for RP redundancy
- **VRF Multicast**: Configures per-VRF multicast with MDT auto-discovery for VXLAN

**Jinja2 Logic Flow:**
1. Enables global `ip multicast-routing` and per-VRF multicast
2. Role check: IF spine, THEN configure anycast RP interface and MSDP peers
3. Creates ACLs for fabric and enterprise RP scope definitions
4. Configures PIM RP addresses for fabric and enterprise scopes
5. Enables VRF-specific MDT settings for VXLAN multicast transport
6. Applies PIM sparse-mode to L3OUT interfaces for external multicast

### **Template 5: FABRIC-EVPN.j2 - Control Plane**
**Campus Fabric Building Logic:**
- **BGP EVPN Peering**: Establishes MP-BGP sessions with L2VPN EVPN and IPv4 MVPN address families
- **Route Reflection**: Configures spines as route reflectors, leaves/borders as clients
- **Peer Templates**: Standardizes BGP session and policy configurations
- **L3OUT Interfaces**: Configures external connectivity interfaces on border nodes

**Jinja2 Logic Flow:**
1. Role-based peer template creation:
   - IF RR (spine): Creates leaf peer session/policy templates with RR-client config
   - IF CLIENT (leaf/border): Creates spine peer session/policy templates
2. Configures BGP router-ID, graceful restart, and disables IPv4 unicast default
3. Establishes BGP neighbors using loopback IP addresses from `DEFN_LOOP_UNDERLAY`
4. Activates neighbors in L2VPN EVPN and IPv4 MVPN address families
5. Configures L3OUT interfaces with dot1Q encapsulation and VRF forwarding
6. Creates prefix-lists and route-maps for border leaf loop prevention

### **Template 6: FABRIC-OVERLAY.j2 - Data Plane Services**
**Campus Fabric Building Logic:**
- **L2VPN EVPN Instances**: Creates VLAN-based EVPN instances for L2 connectivity
- **VLAN-to-VNI Mapping**: Maps tenant VLANs to L2VNIs for L2 extension
- **SVI Creation**: Builds tenant gateways with DHCP relay and routing
- **BGP VRF Address-Family**: Enables EVPN route advertisement per VRF

**Jinja2 Logic Flow:**
1. Configures BGP VRF address-families with EVPN advertisement
2. Role check: IF NOT spine/border for L2 config, THEN create L2VPN instances
3. Iterates through overlay definitions to create:
   - L2VPN EVPN instances with static replication
   - VLANs with descriptive naming
   - VLAN-to-VNI configuration using `L2VNIOFFSET + vlan_id`
   - NVE VNI membership with multicast groups
4. Creates SVIs with VRF forwarding, MAC addresses, and DHCP relay
5. Enables BGP route redistribution and maximum-paths for load balancing

### **Template 7: FABRIC-NAC-IOT.j2 - Security Layer**
**Campus Fabric Building Logic:**
- **Device Classification**: Creates class-maps for device type identification
- **Authentication Policies**: Configures 802.1X and MAB authentication flows
- **Authorization Policies**: Maps authenticated devices to appropriate network segments
- **Micro-Segmentation**: Enables fine-grained access control per device type

**Jinja2 Logic Flow:**
1. Creates class-maps for various authentication scenarios:
   - AAA server timeout conditions
   - 802.1X success/failure states
   - MAB authentication results
   - Device authorization status
2. Configures policy-maps linking device classes to network actions
3. Enables per-VRF policy application for tenant-specific security
4. Provides framework for dynamic VLAN assignment and micro-segmentation

## Fabric Build Sequence Logic

The templates work together in a layered approach to build the campus EVPN fabric:

1. **Foundation (Templates 1-2)**: Establishes VRFs and addressing infrastructure
2. **Transport (Template 3)**: Creates VXLAN tunnel infrastructure and L3VNI services  
3. **Multicast (Template 4)**: Enables BUM traffic handling and anycast RP redundancy
4. **Control Plane (Template 5)**: Establishes BGP EVPN peering and external connectivity
5. **Data Plane (Template 6)**: Delivers L2/L3 overlay services to endpoints
6. **Security (Template 7)**: Applies access control and device policies

Each template includes role-based conditional logic ensuring spines focus on control plane functions while leaves/borders provide edge services. The result is a fully automated, scalable campus EVPN fabric with multi-tenant capabilities.

## Template Parameters

### Common Parameters:
- **`__device`**: System-provided device context for hostname-based logic
- **`FABRIC_BGP_ASN`**: BGP Autonomous System Number for the fabric (default: 65001)
- **`vrf_list`**: Multi-select list of VRF names to configure
- **`FABRIC_RP_SCOPE`**: IP scope for PIM rendezvous point assignment

### VRF Selection Options:
- **red** (VNI 901)
- **green** (VNI 902) 
- **blue** (VNI 903)

## Key Features

- **Role-Based Configuration**: Templates automatically adapt based on device role assignments
- **Jinja2 Logic**: Conditional configuration blocks for different device types
- **Parameter Validation**: Built-in error checking and dependency validation
- **Incremental Deployment**: Support for phased rollout and selective VRF deployment
- **Multicast Optimization**: Integrated PIM sparse mode with anycast RP
- **DHCP Relay**: Automated DHCP relay configuration for overlay SVIs

## Best Practices

1. **Pre-Deployment**: Validate all DEFN-* templates contain accurate fabric parameters
2. **Staging**: Test templates in lab environment before production deployment
3. **Rollback**: Maintain configuration backups before template application
4. **Monitoring**: Verify BGP EVPN sessions and VXLAN tunnel status post-deployment
5. **Documentation**: Update network documentation to reflect deployed overlay services

## Support and Troubleshooting

This template collection supports modern campus network requirements including:
- Zero-touch provisioning through Catalyst Center
- Consistent configuration across heterogeneous hardware platforms  
- Simplified operations through declarative infrastructure management
- Scalable growth through standardized overlay deployment patterns

For optimal results, ensure all fabric devices are running compatible IOS-XE versions with full BGP EVPN and VXLAN feature support.
