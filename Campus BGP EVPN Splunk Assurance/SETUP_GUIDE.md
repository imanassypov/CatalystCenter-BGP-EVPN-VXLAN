# Campus BGP EVPN Splunk Assurance Setup Guide

This guide installs both parts of the assurance stack:

1. the Splunk app `campus_evpn_assurance`, and
2. the patched OpenTelemetry collector that terminates Cisco IOS-XE MDT gRPC dial-out.

> **Before you start:** if you are new to streaming telemetry or OpenTelemetry, read
> [`README.md`](README.md) sections
> [Audience and how to read this document](README.md#audience-and-how-to-read-this-document),
> [From CLI to Streaming YANG](README.md#from-cli-to-streaming-yang), and
> [Telemetry Foundations](README.md#telemetry-foundations--how-the-data-gets-to-splunk)
> for the EVPN-to-MDT mental model. This guide assumes you understand *why* the collector
> listens on gRPC `:57444` and writes to Splunk HEC `:8088`.

The patched receiver source bundle `otel-collector/receiver_yang_26_05_27.tar.gz`
is included in this repository and is shipped inside the handoff bundle built by
`packaging/build-handoff-bundle.sh`.

## 1. Build the handoff bundle

From the repository:

```bash
cd "Campus BGP EVPN Splunk Assurance"
./packaging/build-handoff-bundle.sh
```

Output:

- `packaging/dist/campus_evpn_assurance-1.5.0.spl`
- `packaging/dist/campus-bgp-evpn-splunk-assurance-bundle-1.5.0.tar.gz`

The bundle contains:

- the installable Splunk app package
- this `SETUP_GUIDE.md`
- `otel-collector/` including `receiver_yang_26_05_27.tar.gz`, `builder.yaml`,
  `agent_config.running.yaml`, and `systemd/override.conf.example`
- `telemetry-subscriptions.ios-xe.cfg`
- `evpn_device_inventory.template.csv`

## 2. Splunk prerequisites

Before installing the app or the collector, prepare Splunk:

1. Create a **metrics** index named `evpn_assurance`.
2. Create an HEC token that can write to `evpn_assurance`.
3. Confirm HEC is enabled on port `8088`.

The collector config in this repo expects the HEC endpoint to stay
`https://localhost:8088/services/collector`.

## 3. Install the Splunk app

Install `campus_evpn_assurance-1.5.0.spl` on the Splunk host with Splunk Web or the
CLI.

### Splunk Web

Go to **Apps > Manage Apps > Install app from file**, select the `.spl`, and
install it.

### Splunk CLI

```bash
sudo /opt/splunk/bin/splunk install app /path/to/campus_evpn_assurance-1.5.0.spl
```

The app package is marked `state = enabled`, so it comes up enabled after install.

### Update the device inventory lookup

Replace the packaged lookup with your actual devices. Use the bundled
`evpn_device_inventory.template.csv` as the template and upload it as:

`campus_evpn_assurance/lookups/evpn_device_inventory.csv`

The required columns are:

```csv
source,hostname,ip_address,loopback,site,role,description
```

> **Map external (core / DMZ) eBGP peers too.** The Device × Peer matrices resolve each
> peer's IP to a name with `lookup evpn_device_inventory loopback AS <peer-ip> OUTPUT hostname`.
> Any peer IP that is **not** in the `loopback` column is shown as a raw IP address. To label
> external neighbours (upstream core routers, DMZ gateways), add one row per peer IP with a
> distinct `role` (e.g. `core`, `dmz`) so they never collide with the `spine`/`leaf`/`border`
> role filters used by the per-role panels. A device with several peer links gets one row per
> link IP, all sharing the same `hostname`. Example:
>
> ```csv
> dmz1.dcloud.cisco.com,dmz1,198.19.1.200,198.19.1.200,Building P0,dmz,DMZ Gateway (external eBGP EVPN peer)
> Core-01,Core-01,198.19.2.49,198.19.2.49,Building P0,core,Enterprise Core 01 (Spine-01 uplink1)
> Core-01,Core-01,198.19.2.57,198.19.2.57,Building P0,core,Enterprise Core 01 (Spine-02 uplink1)
> Core-02,Core-02,198.19.2.53,198.19.2.53,Building P0,core,Enterprise Core 02 (Spine-01 uplink2)
> Core-02,Core-02,198.19.2.61,198.19.2.61,Building P0,core,Enterprise Core 02 (Spine-02 uplink2)
> ```

## 4. Install the patched OTel collector

Install the Splunk OpenTelemetry Collector package on the Linux collector host
first. Then apply the repo's config and custom binary.

### 4.1 Stage the repo files on the collector host

Copy the bundle contents to the host, then stage the collector files:

```bash
sudo mkdir -p /etc/otel/collector
sudo cp otel-collector/agent_config.running.yaml /etc/otel/collector/agent_config.yaml
```

Edit `/etc/otel/collector/agent_config.yaml` and set the real HEC token under
`exporters.splunk_hec.token`.

### 4.2 Build `otelcol-yangfix` from the bundled receiver tarball

The repo bundles the patched receiver as source, not as a prebuilt binary. Build
the collector on a Linux host that matches your deployment target.

Prerequisites:

- Go **1.25+**
- `ocb` (OpenTelemetry Collector Builder) **v0.150.0**

Recommended build workflow:

```bash
mkdir -p /tmp/otelbuild/src
cp otel-collector/builder.yaml /tmp/otelbuild/builder.yaml
cp otel-collector/receiver_yang_26_05_27.tar.gz /tmp/otelbuild/
cd /tmp/otelbuild
tar -xzf receiver_yang_26_05_27.tar.gz -C ./src
ocb --config builder.yaml
sudo install -o root -g root -m 0755 ./_build/otelcol-yangfix /usr/local/bin/otelcol-yangfix
```

`builder.yaml` already pins the collector to the receiver's compatible versions and
replaces the stock `yanggrpcreceiver` with the patched source extracted from the
bundled tarball.

If you already have a trusted linux/amd64 `otelcol-yangfix` binary built from this
same source tarball, you may skip the build and install that binary directly to:

`/usr/local/bin/otelcol-yangfix`

### 4.3 Point systemd at the custom binary

Install the bundled override file:

```bash
sudo mkdir -p /etc/systemd/system/splunk-otel-collector.service.d
sudo cp otel-collector/systemd/override.conf.example \
  /etc/systemd/system/splunk-otel-collector.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart splunk-otel-collector.service
```

The override changes only the `ExecStart` line:

```ini
[Service]
ExecStart=
ExecStart=/usr/local/bin/otelcol-yangfix --config=${SPLUNK_CONFIG}
```

### 4.4 Restart behavior you must expect

The old process does not drain active gRPC dial-out streams cleanly on `SIGTERM`.
On restart, systemd typically waits out `TimeoutStopSec` and force-kills the old
process before the new one starts. Expect roughly a **90 second telemetry gap**
during each restart.

Do not repeatedly restart the service while waiting for devices to reconnect.

## 5. Verify the collector install

After restart, confirm the custom collector is active:

```bash
systemctl show -p ExecStart splunk-otel-collector.service
sudo journalctl -u splunk-otel-collector --since '5 min ago' --no-pager | grep 'Everything is ready'
ss -tnp | grep ':57444' | wc -l
curl -s localhost:8888/metrics | grep otelcol_exporter_send_failed_metric_points
```

Expected results:

- `ExecStart` points to `/usr/local/bin/otelcol-yangfix`
- the journal shows `Everything is ready`
- the `:57444` check returns **6** once all fabric devices reconnect
- exporter send failures stay at `0` or are absent

From Splunk, confirm metrics are landing:

```spl
| mstats latest("cisco.cp-vnis.") WHERE index=evpn_assurance BY "cisco.node_id"
| `evpn_lookup`
```

## 6. Apply the IOS-XE telemetry subscriptions

Use `model-config-snippets/telemetry-subscriptions.ios-xe.cfg` on each fabric node
and point the MDT receiver to the collector host:

```text
receiver ip address <collector-ip> 57444 protocol grpc-tcp
```

## 7. Verify the Splunk app dashboards

Open the **Campus EVPN Assurance** app in Splunk Web. You should see three tabs:

| Tab | Purpose |
|---|---|
| **Summary** | Fabric-wide posture — scorecards and trends |
| **Details** | Role-scoped deep dive (use **Fabric Node Role**: Leafs / Spines / Borders) |
| **Alerts** | Active alarms and BGP session detail |

1. Confirm the **Site** dropdown lists your inventory sites.
2. On **Summary**, scorecard tiles should show non-zero ▲ counts when telemetry is flowing.
3. On **Details**, switch **Fabric Node Role** and confirm panels filter to that tier.
4. If panels are empty, see [`campus_evpn_assurance/README.md`](campus_evpn_assurance/README.md) troubleshooting
   and the operator guide in [`README.md`](README.md#operators-guide-reading-the-dashboards).

Optional: on the **Splunk host**, validate all Dashboard Studio views and panel SPL:

```bash
cd "Campus BGP EVPN Splunk Assurance"
python3 tools/validate_studio.py <splunk-admin-user> '<password>'
```

The script checks `executive_overview` (Summary), `node_details` (Details), and `alerts`.

## 8. Roll back to the stock collector

If you need to back out the custom build:

```bash
sudo rm /etc/systemd/system/splunk-otel-collector.service.d/override.conf
sudo rmdir /etc/systemd/system/splunk-otel-collector.service.d 2>/dev/null || true
sudo systemctl daemon-reload
sudo systemctl restart splunk-otel-collector.service
```

This returns the service to the untouched rpm-provided `/usr/bin/otelcol`. Numeric
YANG list keys such as `vni`, `vni-id`, and `evni` will no longer be emitted when
running the stock receiver.

---

## Related documentation

| Document | Contents |
|---|---|
| [`README.md`](README.md) | Architecture, telemetry primer, operator guide |
| [`campus_evpn_assurance/README.md`](campus_evpn_assurance/README.md) | App macros, `mstats` patterns, inventory lookup |
| [`otel-collector/README.md`](otel-collector/README.md) | Collector config, numeric-key patch, troubleshooting |
| [`model-config-snippets/telemetry-subscriptions.ios-xe.cfg`](model-config-snippets/telemetry-subscriptions.ios-xe.cfg) | Subscription IDs 40101–40121 |
