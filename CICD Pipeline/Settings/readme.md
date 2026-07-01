# BGP\_EVPN Project — Settings Reference

> **As-Built Documentation**
> **Authors:** Keith Baldwin — Solutions Engineer — Automation HyperSpecialist (kebaldwi@cisco.com)
> **Copyright © 2024–2026 Cisco Systems, Inc. All rights reserved.**

This document describes the structure and purpose of [`settings.json`](settings.json) — the single source of truth that drives the entire BGP EVPN automation lifecycle across Cisco Workflows, Ansible, and Python tooling paths.

---

## Table of Contents

1. [Purpose](#purpose)
2. [Design Principle — Repeating Project Array](#design-principle--repeating-project-array)
3. [Top-Level Structure](#top-level-structure)
4. [Field Reference](#field-reference)
   - [Site Hierarchy Fields](#site-hierarchy-fields)
   - [Network Settings](#network-settings)
   - [Device Credentials](#device-credentials)
   - [Device List](#device-list)
   - [Network Profile](#network-profile)
5. [How the Tooling Consumes This File](#how-the-tooling-consumes-this-file)
6. [Adding a New Site](#adding-a-new-site)
7. [Field Null Handling](#field-null-handling)
8. [Full Example](#full-example)

---

## Purpose

`settings.json` is the declarative configuration intent file for the BGP\_EVPN project. It defines every site-specific parameter that the automation tooling needs to:

1. **Build the site hierarchy** in Catalyst Center (Area → Building → Floor)
2. **Apply network settings** per site (DNS, DHCP, NTP, SNMP, Syslog, NetFlow, AAA, banner)
3. **Create and assign device credentials** (CLI, SNMP v2c R/W, NETCONF)
4. **Run device discovery** against a defined IP range or list
5. **Bind templates to sites** via a named network profile, controlling which Day-N and Day-0 templates are associated with which devices at which sites

All three tooling paths — Cisco Workflows, Ansible, and Python — read this file from GitHub and use it as their sole source of configuration intent, ensuring consistency regardless of which automation path is used.

---

## Design Principle — Repeating Project Array

The `project` key is a **JSON array**. Each element in the array represents **one complete site definition** — a single Catalyst Center floor-level site with its own unique hierarchy location, network settings, credentials, discovery scope, and template profile.

```json
{
    "project": [
        { /* Site 1 — POD 0, Building P0, Floor 1 */ },
        { /* Site 2 — POD 1, Building P1, Floor 1 */ },
        { /* Site 3 — POD 2, Building P2, Floor 2 */ }
    ]
}
```

This design enables **finite, per-site control** over every configurable dimension:

| Dimension | Per-Site Control |
|-----------|----------------|
| Hierarchy placement | Each entry targets a unique `HierarchyArea / HierarchyBldg / HierarchyFloor` path |
| Network settings | DNS, DHCP, NTP, SNMP, Syslog, NetFlow, AAA, and banner can differ per site |
| Device credentials | Each site can use different CLI usernames, SNMP communities, or NETCONF ports |
| Discovery scope | `device_list` is scoped to the devices at that site only |
| Template binding | `network_profile` independently controls which Day-N and Day-0 templates are bound to which devices at that site |

The automation tooling iterates over every element in the `project` array and applies each definition independently, in order. Adding a new site requires only appending a new object to the array. No changes to the tooling are needed.

---

## Top-Level Structure

```
settings.json
└── project[]                          # Array — one element per site
    ├── HierarchyParent                # Catalyst Center parent path
    ├── HierarchyArea                  # Area name under parent
    ├── HierarchyBldg                  # Building name under area
    ├── HierarchyFloor                 # Floor name under building
    ├── HierarchyBldgAddress           # Physical address for building geo-location
    ├── network_settings{}             # Site-level network infrastructure settings
    │   ├── dhcp_server[]              # DHCP server IP list
    │   ├── dns_server{}               # Domain name and DNS server IPs
    │   ├── ntp_server[]               # NTP server IP list
    │   ├── timezone                   # IANA timezone string
    │   ├── message_of_the_day{}       # Login banner text and retain flag
    │   ├── snmp_server{}              # SNMP trap destination IPs
    │   ├── syslog_server{}            # Syslog destination IPs
    │   ├── netflow_server{}           # NetFlow collector IP and port
    │   ├── network_aaa               # Network AAA (null = not configured)
    │   └── client_and_endpoint_aaa{} # Client/endpoint AAA (ISE/RADIUS)
    ├── device_credentials{}           # Global device credential definitions
    │   ├── cli_credential{}           # SSH/Telnet credential
    │   ├── snmp_v2c_read{}            # SNMP v2c read-only community
    │   ├── snmp_v2c_write{}           # SNMP v2c read-write community
    │   └── netconf_credential{}       # NETCONF credential and port
    ├── device_list                    # Comma-separated discovery IP string
    └── network_profile{}              # Template-to-site binding definition
        ├── profile_name               # Switching profile name in Catalyst Center
        ├── DayNTemplateNames[]        # Day-N (post-onboarding) template bindings
        └── Day0TemplateNames[]        # Day-0 (PnP onboarding) template bindings
```

---

## Field Reference

### Site Hierarchy Fields

These five fields define where this site element lives in the Catalyst Center hierarchy. Together they form the full site path: `{HierarchyParent}/{HierarchyArea}/{HierarchyBldg}/{HierarchyFloor}`.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `HierarchyParent` | string | Full path to the parent node in Catalyst Center. Must already exist or be created by a prior site entry. | `"Global/PODS"` |
| `HierarchyArea` | string | Area name to create or reference under the parent. | `"POD 0"` |
| `HierarchyBldg` | string | Building name to create or reference under the area. | `"Building P0"` |
| `HierarchyFloor` | string | Floor name to create or reference under the building. | `"Floor 1"` |
| `HierarchyBldgAddress` | string | Physical street address for the building. Used by Catalyst Center to set geographic location metadata. | `"300 E Tasman Dr, Bldg 10, San Jose, CA 95134"` |

The hierarchy is created in parent-before-child order. If multiple project entries share the same `HierarchyArea` or `HierarchyBldg`, the tooling is idempotent — it skips creation of objects that already exist and resolves their existing UUIDs for downstream use.

---

### Network Settings

The `network_settings` object defines all site-level network infrastructure services applied to the site in Catalyst Center under **Design → Network Settings**.

#### `dhcp_server`

Array of DHCP server IP addresses assigned to this site.

```json
"dhcp_server": ["198.18.133.1"]
```

Multiple servers are supported. Each IP is registered as a DHCP server for the site scope.

#### `dns_server`

Domain name and DNS resolver configuration for the site.

| Field | Type | Description |
|-------|------|-------------|
| `domain_name` | string | Default DNS domain appended to unqualified hostnames |
| `primary_ip_address` | string | Primary DNS resolver IP |
| `secondary_ip_address` | string \| null | Secondary DNS resolver IP, or `null` if not required |

#### `ntp_server`

Array of NTP server IP addresses. Catalyst Center pushes these to managed devices at the site.

```json
"ntp_server": ["198.18.133.1"]
```

#### `timezone`

IANA timezone string applied to the site. Controls time display and log timestamps in Catalyst Center for this site scope.

```json
"timezone": "America/Toronto"
```

#### `message_of_the_day`

Login banner definition applied to the site.

| Field | Type | Description |
|-------|------|-------------|
| `banner_message` | string | The banner text to display at device login |
| `retain_existing_banner` | boolean | `false` = replace any existing banner; `true` = keep existing banner if one is set |

#### `snmp_server`

SNMP trap receiver configuration.

| Field | Type | Description |
|-------|------|-------------|
| `configure_dnac_ip` | boolean | `true` = automatically include the Catalyst Center IP as a trap receiver |
| `ip_addresses` | array | Additional SNMP trap destination IPs |

#### `syslog_server`

Syslog message receiver configuration.

| Field | Type | Description |
|-------|------|-------------|
| `configure_dnac_ip` | boolean | `true` = automatically include the Catalyst Center IP as a syslog receiver |
| `ip_addresses` | array | Additional syslog destination IPs |

#### `netflow_server`

NetFlow / telemetry collector configuration for streaming telemetry and flow data.

| Field | Type | Description |
|-------|------|-------------|
| `configure_dnac_ip` | boolean | `true` = automatically include the Catalyst Center IP as a NetFlow collector |
| `ip_address` | string | Collector IP address |
| `port` | integer | UDP destination port for NetFlow exports (standard: `2055`) |

#### `network_aaa`

Network device AAA (authentication for device management access). Set to `null` when not required for this site, or provide a structured object with `server_type`, `primary_server_address`, `protocol`, and `shared_secret` fields.

```json
"network_aaa": null
```

#### `client_and_endpoint_aaa`

Client and endpoint AAA configuration (ISE/RADIUS for 802.1X and MAB). Applied to the site to configure RADIUS authentication for end-user devices.

| Field | Type | Description |
|-------|------|-------------|
| `server_type` | string | AAA server type: `"ISE"` or `"AAA"` |
| `primary_server_address` | string | IP address of the primary RADIUS/ISE PSN node |
| `pan_address` | string | IP address of the ISE Policy Administration Node (PAN). Used when `server_type` is `"ISE"`. |
| `protocol` | string | Authentication protocol: `"RADIUS"` or `"TACACS"` |
| `shared_secret` | string | RADIUS shared secret. **Treat as a credential — use Ansible Vault or a secrets manager in production.** |
| `secondary_server_address` | string \| null | IP of secondary RADIUS/ISE PSN, or `null` |

---

### Device Credentials

The `device_credentials` object defines the global device credentials created in Catalyst Center under **Design → Credentials** and assigned to the site. These credentials are used by Catalyst Center for SNMP polling, SSH management access, and NETCONF operations.

#### `cli_credential`

SSH/Telnet access credential.

| Field | Description |
|-------|-------------|
| `description` | Label used to identify this credential in Catalyst Center (must be unique). Used by the tooling to look up the credential UUID. |
| `username` | SSH login username |
| `password` | SSH login password. **Treat as a credential — protect in production.** |
| `enable_password` | Privileged mode enable password |

#### `snmp_v2c_read`

SNMP v2c read-only community string.

| Field | Description |
|-------|-------------|
| `description` | Label used to identify this credential in Catalyst Center |
| `read_community` | SNMPv2c read community string |

#### `snmp_v2c_write`

SNMP v2c read-write community string.

| Field | Description |
|-------|-------------|
| `description` | Label used to identify this credential in Catalyst Center |
| `write_community` | SNMPv2c write community string |

#### `netconf_credential`

NETCONF over SSH credential.

| Field | Description |
|-------|-------------|
| `description` | Label used to identify this credential in Catalyst Center |
| `netconf_port` | TCP port for NETCONF sessions (standard: `"830"`) |

> **Note on credential descriptions:** The `description` field is the key the tooling uses to look up the UUID of an already-created credential. If you change a description between runs, the tooling will create a new credential rather than updating the existing one.

---

### Device List

`device_list` is a comma-separated string of management IP addresses for all devices at this site. It is used by the discovery and provisioning stages of the tooling.

```json
"device_list": "198.19.1.1,198.19.1.2,198.19.1.3,198.19.1.4,198.19.1.5,198.19.1.6"
```

- **Discovery:** The tooling splits this string and builds one or more Catalyst Center discovery jobs targeting these IPs.
- **Provisioning:** The Cisco Workflow provisioning path uses this list to determine which device UUIDs to provision and deploy templates to.
- **Network profile:** The `TemplateTarget` arrays in `network_profile` should be a subset of, or equal to, this list.

Separate site entries with non-overlapping `device_list` values ensure each device is discovered in the context of its correct site.

---

### Network Profile

The `network_profile` object binds the Catalyst Center **switching network profile** to this site's template content. This is the mechanism that connects committed templates in the Template Hub to the devices at this site for provisioning and Day-N deployment.

#### `profile_name`

The name of the switching network profile in Catalyst Center. If a profile with this name already exists, the tooling updates it. If it does not exist, the tooling creates it.

```json
"profile_name": "BGP-EVPN-Switching"
```

#### `DayNTemplateNames`

Array of Day-N template binding objects. Each element defines one template that should be bound to the network profile and optionally deployed to a set of devices.

| Field | Type | Description |
|-------|------|-------------|
| `TemplateName` | string | Exact name of the composite or member template in the Catalyst Center Template Hub. Must match the committed template name. |
| `TemplateTag` | string | Tag label used by the tooling to filter and identify templates. |
| `Project` | string | The Catalyst Center template project the template belongs to. Used to resolve the template UUID. |
| `TemplateTarget` | array | List of device IP addresses to deploy this template to during the provisioning workflow. Must be a subset of `device_list`. |
| `DeployTemplate` | boolean | `true` = the provisioning workflow will deploy this template to all IPs in `TemplateTarget`; `false` = profile binding only, no deployment. |

Multiple Day-N template objects can be listed in the array to bind and optionally deploy more than one template to devices at this site.

#### `Day0TemplateNames`

Array of Day-0 (PnP onboarding) template binding objects. Follows the same structure as `DayNTemplateNames`. Used to bind PnP claim templates to the network profile for zero-touch device onboarding.

Set individual fields to `null` and `TemplateTarget` to `[]` when no Day-0 template is required for a site entry.

```json
"Day0TemplateNames": [
    {
        "TemplateName":   null,
        "TemplateTag":    null,
        "Project":        null,
        "TemplateTarget": [],
        "DeployTemplate": null
    }
]
```

---

## How the Tooling Consumes This File

All three automation paths read `settings.json` from GitHub and iterate over every element in the `project` array:

| Tooling Stage | Cisco Workflow | Ansible Playbook | Python Script | Fields Used |
|---------------|---------------|-----------------|--------------|-------------|
| Build Hierarchy | `GitOps-BuildHierarchy-v3` | `site_hierarchy.yml` | `site_hierarchy.py` | `HierarchyParent/Area/Bldg/Floor`, `HierarchyBldgAddress` |
| Network Settings | `GitOps-BuildSettings-v3` | `network_settings.yml` | `network_settings.py` | `network_settings.*` |
| Device Credentials | `GitOps-BuildSettings-v3` | `credentials.yml` | `credentials.py` | `device_credentials.*` |
| Device Discovery | `GitOps-DeviceDiscovery-v3` | `device_discovery.yml` | `device_discovery.py` | `device_list`, `device_credentials.*` |
| Network Profile | `GitOps-BuildNetworkProfile-v3` | `network_profile.yml` | `network_profile.py` | `network_profile.*` |
| Provisioning | `GitOps-Provisioning-v3` | `provision_devices.yml` + `deploy_composite_template.yml` | `deploy_composite.py` | `device_list`, `network_profile.DayNTemplateNames` |

Each tooling path processes one project array element per loop iteration, applying all relevant fields for that site before moving to the next element.

---

## Adding a New Site

To commission a new site, append a new object to the `project` array. Copy an existing entry and update all fields to reflect the new site's hierarchy placement, network addresses, credentials, discovery scope, and template profile.

```json
{
    "project": [
        { /* existing site 1 */ },
        {
            "HierarchyArea": "POD 1",
            "HierarchyBldg": "Building P1",
            "HierarchyFloor": "Floor 1",
            "HierarchyParent": "Global/PODS",
            "HierarchyBldgAddress": "300 E Tasman Dr, Bldg 11, San Jose, CA 95134",
            "network_settings": { },
            "device_credentials": { },
            "device_list": "198.19.2.1,198.19.2.2",
            "network_profile": { }
        }
    ]
}
```

No changes to the automation tooling are required. The next run will process the new entry, create the new hierarchy path, apply settings, run discovery against the new IP range, and bind the specified templates to the new site profile.

---

## Field Null Handling

Fields and nested objects set to `null` are treated as "not configured" by all three tooling paths:

| Field | `null` Behavior |
|-------|----------------|
| `dns_server.secondary_ip_address` | No secondary DNS server configured for this site |
| `network_aaa` | Network device AAA is not applied to this site |
| `client_and_endpoint_aaa.secondary_server_address` | No secondary RADIUS/ISE PSN for this site |
| `Day0TemplateNames[*].TemplateName` | No Day-0 template bound to the profile |
| `Day0TemplateNames[*].DeployTemplate` | No PnP deployment triggered |

---

## Full Example

The following is a complete, annotated single-site `settings.json` entry:

```json
{
    "project": [
        {
            "HierarchyParent": "Global/PODS",
            "HierarchyArea":   "POD 0",
            "HierarchyBldg":   "Building P0",
            "HierarchyFloor":  "Floor 1",
            "HierarchyBldgAddress": "300 E Tasman Dr, Bldg 10, San Jose, CA 95134",

            "network_settings": {
                "dhcp_server":  ["198.18.133.1"],
                "dns_server": {
                    "domain_name":          "dcloud.cisco.com",
                    "primary_ip_address":   "198.18.133.1",
                    "secondary_ip_address": null
                },
                "ntp_server":  ["198.18.133.1"],
                "timezone":    "America/Toronto",
                "message_of_the_day": {
                    "banner_message":         "DNAC Template Lab P0!",
                    "retain_existing_banner": false
                },
                "snmp_server": {
                    "configure_dnac_ip": true,
                    "ip_addresses": ["198.18.133.27"]
                },
                "syslog_server": {
                    "configure_dnac_ip": true,
                    "ip_addresses": ["198.18.133.27"]
                },
                "netflow_server": {
                    "configure_dnac_ip": true,
                    "ip_address": "198.18.133.27",
                    "port": 2055
                },
                "network_aaa": null,
                "client_and_endpoint_aaa": {
                    "server_type":              "ISE",
                    "primary_server_address":   "198.18.133.27",
                    "pan_address":              "198.18.133.27",
                    "protocol":                 "RADIUS",
                    "shared_secret":            "C1sco12345",
                    "secondary_server_address": null
                }
            },

            "device_credentials": {
                "cli_credential": {
                    "description":     "CLI-net-admin",
                    "username":        "net-admin",
                    "password":        "C1sco12345",
                    "enable_password": "C1sco12345"
                },
                "snmp_v2c_read": {
                    "description":    "RO",
                    "read_community": "RO"
                },
                "snmp_v2c_write": {
                    "description":     "RW",
                    "write_community": "RW"
                },
                "netconf_credential": {
                    "description":  "NETCONF-netadmin",
                    "netconf_port": "830"
                }
            },

            "device_list": "198.19.1.1,198.19.1.2,198.19.1.3,198.19.1.4,198.19.1.5,198.19.1.6",

            "network_profile": {
                "profile_name": "BGP-EVPN-Switching",
                "DayNTemplateNames": [
                    {
                        "TemplateName":   "BGP-EVPN-BUILD.j2",
                        "TemplateTag":    "DEMO",
                        "Project":        "Building P0",
                        "TemplateTarget": [
                            "198.19.1.1","198.19.1.2","198.19.1.3",
                            "198.19.1.4","198.19.1.5","198.19.1.6"
                        ],
                        "DeployTemplate": true
                    }
                ],
                "Day0TemplateNames": [
                    {
                        "TemplateName":   null,
                        "TemplateTag":    null,
                        "Project":        null,
                        "TemplateTarget": [],
                        "DeployTemplate": null
                    }
                ]
            }
        }
    ]
}
```