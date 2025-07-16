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

**Software Requirements:**
- IOS-XE with BGP EVPN and VXLAN support

## Template Structure

The project contains two categories of templates:

### 1. Definition Templates (DEFN-*)
State and input variable definitions that store fabric-wide parameters:

#### **DEFN-ROLES**
- **Purpose**: Defines device roles within the EVPN fabric topology
- **Scope**: Node classification for spine, leaf, border leaf, route reflector, and client roles
- **Usage**: Referenced by all configuration templates to apply role-specific configurations

#### **DEFN-LOOPBACKS** 
- **Purpose**: IP address assignments for underlay and overlay loopback interfaces
- **Scope**: Fabric-wide loopback IP addressing scheme including anycast RP addresses
- **Usage**: Provides consistent addressing across all fabric nodes

#### **DEFN-VRF**
- **Purpose**: VRF definitions with route distinguishers and route targets
- **Scope**: Multi-tenant VRF configuration parameters including multicast settings
- **Usage**: Defines tenant isolation boundaries and routing policies

#### **DEFN-OVERLAY**
- **Purpose**: Overlay network definitions for L2/L3 services
- **Scope**: VLAN-to-VNI mappings, SVI configurations, and DHCP relay settings
- **Usage**: Maps tenant VLANs to VXLAN VNIs with associated IP addressing

#### **DEFN-VNIOFFSETS**
- **Purpose**: VNI offset values for VXLAN network identifier calculation
- **Scope**: L2VNI and L3VNI offset definitions for consistent VNI allocation
- **Usage**: Ensures non-overlapping VNI assignments across the fabric

#### **DEFN-L3OUT**
- **Purpose**: External connectivity parameters for border leaf switches
- **Scope**: L3 exit point configurations and external BGP peering
- **Usage**: Defines connectivity to external networks and data centers

### 2. Configuration Templates (Numeric Sequence)
Jinja2-based CLI templates that render actual device configurations:

#### **0. BGP-EVPN**
- **Purpose**: Base BGP configuration for EVPN control plane
- **Scope**: Establishes BGP process with EVPN address family support
- **Target Devices**: All fabric nodes (Spine, Leaf, Border Leaf)
- **Dependencies**: Requires DEFN-ROLES, DEFN-LOOPBACKS
- **Function**: Sets up foundational BGP parameters for EVPN operation

#### **1. FABRIC-VRF**
- **Purpose**: VRF instance configuration with route targets and multicast settings
- **Scope**: Creates tenant VRF definitions with proper route distribution
- **Target Devices**: All fabric nodes
- **Dependencies**: DEFN-VRF, DEFN-ROLES, DEFN-LOOPBACKS
- **Function**: Establishes multi-tenant routing domains with EVPN integration

#### **2. FABRIC-LOOPBACKS**
- **Purpose**: Loopback interface configuration for underlay and overlay services
- **Scope**: Configures system loopbacks for BGP peering and overlay termination
- **Target Devices**: All fabric nodes with role-specific variations
- **Dependencies**: DEFN-LOOPBACKS, DEFN-ROLES, DEFN-VRF
- **Function**: Provides stable endpoints for BGP sessions and VXLAN tunnels

#### **3. FABRIC-NVE**
- **Purpose**: Network Virtualization Edge (NVE) interface configuration
- **Scope**: VXLAN tunnel endpoint configuration with ingress replication
- **Target Devices**: Leaf and Border Leaf switches only
- **Dependencies**: DEFN-LOOPBACKS, DEFN-ROLES
- **Function**: Establishes VXLAN tunnel infrastructure for overlay transport

#### **4. FABRIC-EVPN**
- **Purpose**: BGP EVPN peering and route reflector configuration
- **Scope**: Establishes EVPN control plane with route reflection topology
- **Target Devices**: All fabric nodes with role-specific BGP configurations
- **Dependencies**: DEFN-ROLES, DEFN-LOOPBACKS, DEFN-VNIOFFSETS
- **Function**: Creates BGP EVPN sessions between spine (RR) and leaf (client) nodes

#### **5. FABRIC-L3OUT**
- **Purpose**: External Layer 3 connectivity for border leaf switches
- **Scope**: BGP peering with external networks and route redistribution
- **Target Devices**: Border Leaf switches only
- **Dependencies**: DEFN-L3OUT, DEFN-ROLES, DEFN-LOOPBACKS
- **Function**: Provides campus fabric connectivity to external networks/WAN

#### **6. FABRIC-OVERLAY**
- **Purpose**: Overlay service configuration for tenant networks
- **Scope**: EVPN instances, VLAN-to-VNI mapping, and SVI configuration
- **Target Devices**: Leaf and Border Leaf switches
- **Dependencies**: DEFN-OVERLAY, DEFN-VRF, DEFN-VNIOFFSETS
- **Function**: Delivers L2/L3 overlay services to connected endpoints

## Deployment Sequence

The templates should be deployed in numerical order to ensure proper dependency resolution:

1. **Definition Templates**: Deploy all DEFN-* templates first to establish fabric parameters
2. **Base Configuration**: Deploy templates 0-1 for foundational BGP and VRF setup
3. **Infrastructure**: Deploy templates 2-4 for loopbacks, NVE, and EVPN peering
4. **Services**: Deploy templates 5-6 for external connectivity and overlay services

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
