# Telegraf — EVPN Fabric Telemetry Collector (`telegraf_igor`)

## Overview

This directory contains the Telegraf configuration for the **`telegraf_igor`** instance running on the Splunk Heavy Forwarder (`10.0.10.104`). This instance collects Model-Driven Telemetry (MDT) from the EVPN fabric devices via IOS-XE gRPC dial-out and forwards all metrics to Splunk via HEC in `splunkmetric` format.

### What It Does

| Capability | Detail |
|---|---|
| Receives IOS-XE MDT dial-out | gRPC listener on `:57345`, `encode-kvgpb` encoding |
| EVPN fabric coverage | Spine-01/02, Leaf-01/02, Border-01/02 |
| YANG models collected | `Cisco-IOS-XE-evpn-oper`, `Cisco-IOS-XE-nve-oper` |
| Subscription IDs | 40101–40112 (on-change + periodic pairs) |
| Output destination | Splunk HEC on `10.0.10.104:8088` |
| Splunk index | `evpn_assurance` (metrics index) |
| BGP session state | Numeric mapping applied to `bgp_status` measurements |

---

## Infrastructure

| Component | Value |
|---|---|
| Host | `maple-splunk-vm4-hf` — Splunk Heavy Forwarder |
| Host IP | `10.0.10.104` |
| Config path (live) | `/etc/telegraf_igor/telegraf.conf` |
| Systemd service | `telegraf_igor.service` |
| MDT listen port | `:57345` (gRPC/TCP) |
| Splunk HEC endpoint | `https://10.0.10.104:8088/services/collector` |
| Splunk HEC token | `9b20f6a2-8c0b-45d8-b0df-4efb7f4a97e4` (token name: `Igor_Telegraf`) |
| Splunk index | `evpn_assurance` |
| Search Head | `http://10.0.10.101:8000` |

> This is a second Telegraf instance running alongside the primary `telegraf` instance. They use separate config directories, service units, ports, and HEC tokens. Only `telegraf_igor` is in scope for the EVPN assurance project.

---

## Directory Structure

```
/etc/telegraf_igor/
├── telegraf.conf          # Main configuration file (source of truth: telegraf/telegraf.conf in this repo)
└── telegraf.d/            # Drop-in config directory (currently empty)

/etc/systemd/system/
└── telegraf_igor.service  # Systemd service unit

/etc/default/
└── telegraf_igor          # Environment file
```

### Systemd Service Unit

File: `/etc/systemd/system/telegraf_igor.service`

```ini
[Unit]
Description=Telegraf - Igor Instance
Documentation=https://github.com/influxdata/telegraf
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
NotifyAccess=all
EnvironmentFile=-/etc/default/telegraf_igor
User=telegraf
ImportCredential=telegraf.*
ExecStart=/usr/bin/telegraf --config /etc/telegraf_igor/telegraf.conf --config-directory /etc/telegraf_igor/telegraf.d $TELEGRAF_OPTS
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartForceExitStatus=SIGPIPE
KillMode=mixed
LimitMEMLOCK=8M:8M
PrivateMounts=true
RuntimeDirectory=telegraf_igor
PIDFile=/run/telegraf_igor/telegraf_igor.pid

[Install]
WantedBy=multi-user.target
```

### Port Allocation

| Plugin | Primary (`telegraf`) | Igor (`telegraf_igor`) |
|---|---|---|
| `cisco_telemetry_mdt` | `:57344` | `:57345` |

---

## EVPN Fabric Devices

These are the devices configured to dial out to this collector.

| Device | Role | Mgmt IP | Loopback0 (VTEP) |
|---|---|---|---|
| Spine-01 | Spine | 198.18.128.101 | 198.19.1.1 |
| Spine-02 | Spine | 198.18.128.102 | 198.19.1.2 |
| Leaf-01 | Leaf | 198.18.128.103 | 198.19.1.3 |
| Leaf-02 | Leaf | 198.18.128.104 | 198.19.1.4 |
| Border-01 | Border Leaf | 198.18.128.105 | 198.19.1.5 |
| Border-02 | Border Leaf | 198.18.128.106 | 198.19.1.6 |

All devices use subscription IDs 40101–40112 targeting `10.0.10.104:57345` via `grpc-tcp` from `Mgmt-vrf`.

---

## Configuration Reference

### Agent

```toml
[agent]
  interval = "10s"
  round_interval = true
  metric_batch_size = 1000
  metric_buffer_limit = 10000
  collection_jitter = "0s"
  flush_interval = "10s"
  flush_jitter = "0s"
  precision = "0s"
  omit_hostname = true
```

| Setting | Value | Reason |
|---|---|---|
| `interval` | `10s` | Base collection tick — aligns with MDT periodic subscriptions |
| `metric_batch_size` | `1000` | Max metrics per HEC POST — tuned for EVPN event bursts |
| `metric_buffer_limit` | `10000` | In-memory queue depth before drops — covers HF-to-indexer forwarding latency |
| `omit_hostname` | `true` | Prevents Telegraf host from being injected as `host` tag — source identity comes from the device's MDT subscription, not the collector |
| `precision` | `0s` | Uses native timestamp precision from the telemetry stream |

---

### Output — Splunk HEC

```toml
[[outputs.http]]
  url = "https://10.0.10.104:8088/services/collector"
  data_format = "splunkmetric"
  splunkmetric_hec_routing = true
  insecure_skip_verify = true

  [outputs.http.headers]
    Content-Type = "application/json"
    Authorization = "Splunk 9b20f6a2-8c0b-45d8-b0df-4efb7f4a97e4"
    X-Splunk-Request-Channel = "9b20f6a2-8c0b-45d8-b0df-4efb7f4a97e4"
```

| Setting | Value | Reason |
|---|---|---|
| `url` | `https://10.0.10.104:8088/services/collector` | HEC endpoint on the local Heavy Forwarder — Telegraf sends locally, HF forwards to indexers |
| `data_format` | `splunkmetric` | Formats each metric as a Splunk HEC metric event (`{"metric_name":..., "fields":{"_value":...}}`) |
| `splunkmetric_hec_routing` | `true` | Enables per-metric `index`, `source`, `sourcetype` routing via HEC metadata — allows the device's originating `source` tag to appear as the Splunk `source` field |
| `insecure_skip_verify` | `true` | Required — HF uses a self-signed TLS certificate |
| `X-Splunk-Request-Channel` | HEC token UUID | Required by Splunk HEC for acknowledgement channel tracking |

> The HEC token is configured in `/opt/splunk/etc/apps/ta_cisco_thousandeyes/local/inputs.conf` on the HF under stanza `[http://Igor_Telegraf]`. The token routes metrics to the `evpn_assurance` index.

#### Data Flow

```
IOS-XE Device (gRPC dial-out)
        |
        v  :57345 (grpc-tcp)
Telegraf_igor (10.0.10.104)
        |
        v  HEC POST (splunkmetric)
Splunk HF HEC (10.0.10.104:8088)
        |
        v  TCP 9997
Splunk Indexers (10.0.10.102, 10.0.10.103)
        |
        v  mstats / mcatalog
Splunk Search Head (10.0.10.101) → evpn_fabric_assurance dashboard
```

---

### Processor — BGP Session State Enum

```toml
[[processors.enum]]
  namepass = ["bgp_status"]
  [[processors.enum.mapping]]
    field = "session_state"
    [processors.enum.mapping.value_mappings]
      "ACTIVE"      = 1
      "IDLE"        = 0
      "CONNECT"     = 2
      "OPENSENT"    = 3
      "OPENCONFIRM" = 4
      "ESTABLISHED" = 5
```

Converts the string `session_state` field in `bgp_status` measurements to an integer so it can be stored as a numeric metric in Splunk's metrics index (string fields cannot be stored as metric values).

| String State | Integer | Meaning |
|---|---|---|
| `IDLE` | 0 | BGP not attempting to connect |
| `ACTIVE` | 1 | Attempting to establish TCP connection |
| `CONNECT` | 2 | TCP SYN sent, waiting for reply |
| `OPENSENT` | 3 | TCP connected, OPEN message sent |
| `OPENCONFIRM` | 4 | OPEN received, waiting for KEEPALIVE |
| `ESTABLISHED` | 5 | Full BGP session — the only healthy state |

`namepass = ["bgp_status"]` ensures this processor only runs on BGP measurements and has no effect on EVPN/NVE metrics.

---

### Input — IOS-XE MDT (`cisco_telemetry_mdt`)

```toml
[[inputs.cisco_telemetry_mdt]]
  transport       = "grpc"
  service_address = ":57345"
  max_msg_size    = 8000000
```

| Setting | Value | Reason |
|---|---|---|
| `transport` | `grpc` | IOS-XE uses gRPC for MDT dial-out (`protocol grpc-tcp` on device) |
| `service_address` | `:57345` | Listens on all interfaces on port 57345 — matches `receiver ip address 10.0.10.104 57345` on all fabric devices |
| `max_msg_size` | `8000000` (8 MB) | Increased from the 4 MB default to handle large EVPN/NVE bulk updates on-change bursts |

#### Why No `embedded_tags`?

For **IOS-XE `encode-kvgpb`**, the Telegraf `cisco_telemetry_mdt` plugin automatically maps YANG list keys to metric dimensions. No `embedded_tags` configuration is needed — confirmed by the `vlan_id`, `evpn_inst_id`, and `peer_ip_addr` dimensions arriving correctly in Splunk without it.

#### YANG Models and Subscription Mapping

| Sub IDs | YANG Path | Model | Policy | Splunk Metric Prefix |
|---|---|---|---|---|
| 101 / 102 | `/nve-oper-data/nve-oper` | `Cisco-IOS-XE-nve-oper` | on-change / periodic 5 min | `Cisco-IOS-XE-nve-oper:nve-oper-data/nve-oper/...` |
| 103 / 104 | `/nve-oper-data/nve-oper/nve-vni-oper` | `Cisco-IOS-XE-nve-oper` | on-change / periodic 10 min | `Cisco-IOS-XE-nve-oper:nve-oper-data/nve-oper/nve-vni-oper/...` |
| 105 / 106 | `/nve-oper-data/nve-oper/nve-peer-oper` | `Cisco-IOS-XE-nve-oper` | on-change / periodic 5 min | `Cisco-IOS-XE-nve-oper:nve-oper-data/nve-oper/nve-peer-oper/...` |
| 107 / 108 | `/evpn-oper-data/evpn-inst` | `Cisco-IOS-XE-evpn-oper` | on-change / periodic 10 min | `Cisco-IOS-XE-evpn-oper:evpn-oper-data/evpn-inst/...` |
| 109 / 110 | `/evpn-oper-data/evpn-inst/evpn-vlan` | `Cisco-IOS-XE-evpn-oper` | on-change / periodic 10 min | `Cisco-IOS-XE-evpn-oper:evpn-oper-data/evpn-inst/evpn-vlan/...` |
| 111 / 112 | `/evpn-oper-data/evpn-inst/evpn-vlan/evpn-peer` | `Cisco-IOS-XE-evpn-oper` | on-change / periodic 5 min | `Cisco-IOS-XE-evpn-oper:evpn-oper-data/evpn-inst/evpn-vlan/evpn-peer/...` |
| **114** | **`/bgp-state-data/neighbors/neighbor`** | **`Cisco-IOS-XE-bgp-oper`** | **periodic 30 s** | **`Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors/neighbor.*`** |

> Sub 40113 (EVPN Route Statistics) is deployed on all 6 devices and `Valid` on IOS-XE 26.2.x using the parent-container XPath `/evpn-oper-data/evpn-stats`. The child path `/evpn-oper-data/evpn-stats/evpn-vni-rtcnt` is rejected as `Invalid` on this build, so the parent container (which carries the same per-VNI route-count data) is used instead.

#### Key Dimensions Arriving in Splunk

| Dimension | Source | Used For |
|---|---|---|
| `source` | Originating device hostname (set by device) | Device identity in all panels |
| `vlan_id` | YANG list key in `evpn-vlan` | Per-VLAN filtering |
| `evpn_inst_id` | YANG list key in `evpn-inst` | Per-EVI filtering |
| `peer_ip_addr` | YANG list key in `evpn-peer` | VTEP peer identification |
| `subscription` | Telegraf-injected subscription ID | Subscription health tracking |
| `path` | YANG path of the streaming data | Model path tracing |

---

## Service Management

SSH to the Heavy Forwarder (`10.0.10.104`, user: `cisco`) and use `sudo` for service commands:

```bash
# Status
sudo systemctl status telegraf_igor

# Restart (e.g. after config change)
sudo systemctl restart telegraf_igor

# Follow live logs
sudo journalctl -u telegraf_igor -f

# Last 50 log lines
sudo journalctl -u telegraf_igor -n 50 --no-pager

# Test config syntax before applying
sudo telegraf --config /etc/telegraf_igor/telegraf.conf --test
```

### Deploying a Config Change

1. Edit config locally in this repo
2. Copy to HF:
   ```bash
   scp telegraf/telegraf.conf cisco@10.0.10.104:/tmp/telegraf_igor.conf
   ```
3. On the HF, validate and apply:
   ```bash
   sudo telegraf --config /tmp/telegraf_igor.conf --test
   sudo cp /tmp/telegraf_igor.conf /etc/telegraf_igor/telegraf.conf
   sudo systemctl restart telegraf_igor
   sudo systemctl status telegraf_igor
   ```

---

## Validation

### 1. Confirm Telegraf is receiving MDT data

```bash
sudo journalctl -u telegraf_igor -f | grep -i "cisco_telemetry_mdt\|metric\|error"
```

Look for lines like:
```
cisco_telemetry_mdt: Accepted connection from 10.0.1.101:XXXXX
```

### 2. Confirm metrics are landing in Splunk

Run in Splunk Search Head (`http://10.0.10.101:8000`):

```spl
| mcatalog values(metric_name) WHERE index=evpn_assurance | head 20
```

Expected: metric names prefixed with `Cisco-IOS-XE-evpn-oper:`, `Cisco-IOS-XE-nve-oper:`, and `Cisco-IOS-XE-bgp-oper:`.

```spl
| mcatalog values(source) WHERE index=evpn_assurance
```

Expected: `Leaf-01`, `Leaf-02`, `Spine-01`, `Spine-02`, `Border-01`, `Border-02`.

### 3. Check event volume by source

```spl
| mstats count WHERE index=evpn_assurance earliest=-1h BY source
| sort - count
```

> Use `earliest=-24h` if the fabric has been stable (on-change subscriptions only push on state change, not periodically).

### 4. Confirm no write errors to Splunk HEC

```bash
sudo journalctl -u telegraf_igor -n 100 --no-pager | grep -i "error\|failed\|rejected"
```

A healthy run shows no errors. Common issues:

| Error | Cause | Fix |
|---|---|---|
| `connection refused` to HEC | Splunk HF HEC not listening | Check `sudo systemctl status splunk` on HF |
| `403 Forbidden` from HEC | HEC token invalid or disabled | Verify token in Splunk Settings → Data Inputs → HTTP Event Collector |
| `invalid token` | Wrong `Authorization` header | Re-check token UUID in `telegraf.conf` matches `inputs.conf` stanza |
| `metric buffer limit reached` | Downstream Splunk too slow | Increase `metric_buffer_limit` or check indexer performance |

---

## Differences from Primary Telegraf Instance

| Item | Primary (`telegraf`) | Igor (`telegraf_igor`) |
|---|---|---|
| Config directory | `/etc/telegraf/` | `/etc/telegraf_igor/` |
| Systemd service | `telegraf.service` | `telegraf_igor.service` |
| MDT listen port | `:57344` | `:57345` |
| Splunk HEC token | `f3c8f5db-51d9-4844-8646-315d15f950ab` | `9b20f6a2-8c0b-45d8-b0df-4efb7f4a97e4` |
| Splunk index | *(primary index)* | `evpn_assurance` |
| Scope | General lab telemetry | EVPN fabric assurance only |
| PID file | `/run/telegraf/` | `/run/telegraf_igor/` |

Both instances run as the `telegraf` system user and share the same binary at `/usr/bin/telegraf`.

---

## Troubleshooting

| Symptom | Likely Cause | Resolution |
|---|---|---|
| No data in `evpn_assurance` index | HEC token misconfigured or Telegraf not running | Check `systemctl status telegraf_igor`; verify HEC token |
| Only Leaf-01/02 show EVPN metrics | Correct — Spines/Borders have no EVPN VLAN instances | Spine/Border data appears in NVE subscriptions (40101–40106) |
| `source` shows device IP instead of hostname | Device sending IP as source tag | Verify device `hostname` is set and MDT source-address is not overriding |
| Subscriptions 40101–40106 were `Invalid` | Wrong XPath node names — concatenated instead of hyphenated | Fixed: correct paths are `/nve-oper-data/nve-oper`, `/nve-oper/nve-vni-oper`, `/nve-oper/nve-peer-oper` |
| Sub 40113 child path `Invalid` | `/evpn-oper-data/evpn-stats/evpn-vni-rtcnt` is rejected on 26.02 (V262) | Subscribe to parent container `/evpn-oper-data/evpn-stats` instead (Valid + Connected) |
| Sub 40114 BGP panels empty in Splunk | Wrong metric names | IOS-XE uses `Cisco-IOS-XE-bgp-oper:*` and dimensions `vrf_name`/`neighbor_id`; session state uses `hold_time>0` not counter arithmetic |
| Sub 40114 receiver stuck `Transport requested` | Used `receiver-type protocol` (named receiver mode) | Use `receiver ip address 10.0.10.104 57345 protocol grpc-tcp` with `source-vrf Mgmt-vrf` |
| gRPC `Connecting` (never `Active`) | `pubd` crashed on device | Run `show platform software yang-management process` — restart `pubd` or reload device |
| Metrics arrive but with wrong dimensions | `embedded_tags` misconfiguration | Not needed for IOS-XE kvgpb — list keys are auto-mapped to tags |
