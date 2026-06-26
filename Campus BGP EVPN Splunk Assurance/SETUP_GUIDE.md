# Campus BGP EVPN Splunk Assurance Setup Guide

This guide installs both parts of the assurance stack:

1. the Splunk app `campus_evpn_assurance`, and
2. the patched OpenTelemetry collector that terminates Cisco IOS-XE MDT gRPC dial-out.

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
```

## 6. Apply the IOS-XE telemetry subscriptions

Use `model-config-snippets/telemetry-subscriptions.ios-xe.cfg` on each fabric node
and point the MDT receiver to the collector host:

```text
receiver ip address <collector-ip> 57444 protocol grpc-tcp
```

## 7. Roll back to the stock collector

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
