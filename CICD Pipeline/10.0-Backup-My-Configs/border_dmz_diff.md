# Border to dmz Diff Report

## Scope

- Previous backup: 20260625-123721
- Latest backup: 20260625-132618
- Devices analyzed:
  - Border01
  - Border02
  - dmz1

## Method

The two snapshots were normalized before comparison to remove backup wrapper formatting differences in IOS-XE outputs.

Normalization steps:

- Removed the top two metadata lines:
  - ! Host: ...
  - ! Collected: ...
- Decoded escaped newlines from the IOS-XE string payload format.
- Ignored timestamp-only metadata when interpreting operational impact:
  - Current configuration size
  - Last configuration change time

## Border01 Changes

### 1) New loopbacks introduced

- Added interface Loopback1
  - description GRE TUNNEL SOURCE
  - ip address 10.100.1.1/32
  - ip ospf 1 area 0

- Added interface Loopback2
  - description GRE EVPN PEER NETWORK
  - ip address 10.101.1.2/32
  - ip pim sparse-mode
  - ip ospf 100 area 0

### 2) New GRE tunnel to dmz introduced

- Added interface Tunnel10
  - description GRE TO dmz1.dcloud.cisco.com
  - ip address 10.100.100.2/30
  - no ip redirects
  - no ip unreachables
  - ip pim sparse-mode
  - ip ospf network point-to-point
  - ip ospf 100 area 0
  - tunnel source Loopback1
  - tunnel destination 10.100.2.1
  - tunnel path-mtu-discovery

### 3) New OSPF process 100 introduced

- Added router ospf 100
  - router-id 10.101.1.2
  - redistribute connected route-map LOOPBACK0-INTO-OSPF100

### 4) BGP peer fall-over policy changed

In peer-session policy:

- Removed: fall-over route-map MCLUSTER-LOOPBACKS
- Added: fall-over route-map NODE-LOOPBACKS

### 5) BGP neighbor 198.19.1.200 activated in IPv4 AF

Under address-family ipv4:

- Added: neighbor 198.19.1.200 activate
- Added: neighbor 198.19.1.200 inherit peer-policy OVERLAY-MCLUSTER-EVPN-PEER-POLICY

### 6) VRF unicast BGP AF blocks added

- Added address-family ipv4 vrf blue
  - advertise l2vpn evpn
  - import path selection all
  - redistribute connected
  - maximum-paths ibgp 2

- Added address-family ipv4 vrf green
  - advertise l2vpn evpn
  - import path selection all
  - redistribute connected
  - maximum-paths ibgp 2

### 7) New prefix-list and route-maps added

- Added ip prefix-list NODE-LOOPBACKS seq 1-7
  - permits 198.19.1.1/32 through 198.19.1.6/32
  - permits 198.19.1.200/32

- Added route-map NODE-LOOPBACKS permit 10
  - match ip address prefix-list NODE-LOOPBACKS

- Added route-map LOOPBACK0-INTO-OSPF100 permit 10
  - match interface Loopback0

## Border02 Changes

Border02 changed in the same pattern as Border01, with Border02-specific addressing.

### 1) New loopbacks introduced

- Added interface Loopback1
  - description GRE TUNNEL SOURCE
  - ip address 10.100.3.1/32
  - ip ospf 1 area 0

- Added interface Loopback2
  - description GRE EVPN PEER NETWORK
  - ip address 10.101.2.2/32
  - ip pim sparse-mode
  - ip ospf 100 area 0

### 2) New GRE tunnel to dmz introduced

- Added interface Tunnel11
  - description GRE TO dmz1.dcloud.cisco.com
  - ip address 10.100.101.2/30
  - no ip redirects
  - no ip unreachables
  - ip pim sparse-mode
  - ip ospf network point-to-point
  - ip ospf 100 area 0
  - tunnel source Loopback1
  - tunnel destination 10.100.2.1
  - tunnel path-mtu-discovery

### 3) New OSPF process 100 introduced

- Added router ospf 100
  - router-id 10.101.2.2
  - redistribute connected route-map LOOPBACK0-INTO-OSPF100

### 4) BGP peer fall-over policy changed

In peer-session policy:

- Removed: fall-over route-map MCLUSTER-LOOPBACKS
- Added: fall-over route-map NODE-LOOPBACKS

### 5) BGP neighbor 198.19.1.200 activated in IPv4 AF

Under address-family ipv4:

- Added: neighbor 198.19.1.200 activate
- Added: neighbor 198.19.1.200 inherit peer-policy OVERLAY-MCLUSTER-EVPN-PEER-POLICY

### 6) VRF unicast BGP AF blocks added

- Added address-family ipv4 vrf blue
  - advertise l2vpn evpn
  - import path selection all
  - redistribute connected
  - maximum-paths ibgp 2

- Added address-family ipv4 vrf green
  - advertise l2vpn evpn
  - import path selection all
  - redistribute connected
  - maximum-paths ibgp 2

### 7) New prefix-list and route-maps added

- Added ip prefix-list NODE-LOOPBACKS seq 1-7
  - permits 198.19.1.1/32 through 198.19.1.6/32
  - permits 198.19.1.200/32

- Added route-map NODE-LOOPBACKS permit 10
  - match ip address prefix-list NODE-LOOPBACKS

- Added route-map LOOPBACK0-INTO-OSPF100 permit 10
  - match interface Loopback0

## dmz1 Changes

No configuration changes detected between the two snapshots after normalization.

- No added lines
- No removed lines
- No changes to tunnel, loopback, OSPF, BGP, route-map, or static route configuration

## Border to dmz Focused Impact Notes

The Border devices introduced new GRE and OSPF100 control-plane constructs pointing to tunnel destination 10.100.2.1, while dmz1 remained unchanged between these snapshots.

This creates a strong asymmetry indicator for the observed Border01 and Border02 to dmz1 connectivity impact after the push.
