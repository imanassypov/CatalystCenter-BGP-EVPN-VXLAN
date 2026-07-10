#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ASSURANCE_DIR=$(cd -- "${SCRIPT_DIR}/.." && pwd)
DIST_DIR="${SCRIPT_DIR}/dist"
APP_DIR="${ASSURANCE_DIR}/campus_evpn_assurance"
OTEL_DIR="${ASSURANCE_DIR}/otel-collector"

"${SCRIPT_DIR}/build-app.sh" >/dev/null

version=$(
  awk '
    $0 == "[app]" { in_app = 1; next }
    /^\[/ && $0 != "[app]" { in_app = 0 }
    in_app && $1 == "version" { print $3; exit }
  ' "${APP_DIR}/default/app.conf"
)

if [[ -z "${version}" ]]; then
  echo "Could not determine app version from ${APP_DIR}/default/app.conf" >&2
  exit 1
fi

if [[ ! -f "${OTEL_DIR}/receiver_yang_26_05_27.tar.gz" ]]; then
  echo "Missing required collector source bundle: ${OTEL_DIR}/receiver_yang_26_05_27.tar.gz" >&2
  exit 1
fi

mkdir -p "${DIST_DIR}"

app_package="${DIST_DIR}/campus_evpn_assurance-${version}.spl"
bundle_name="campus-bgp-evpn-splunk-assurance-bundle-${version}"
bundle_path="${DIST_DIR}/${bundle_name}.tar.gz"
stage_dir=$(mktemp -d "${TMPDIR:-/tmp}/campus_evpn_bundle.XXXXXX")
bundle_root="${stage_dir}/${bundle_name}"

cleanup() {
  rm -rf "${stage_dir}"
}
trap cleanup EXIT

mkdir -p "${bundle_root}"

cp "${app_package}" "${bundle_root}/"
cp "${ASSURANCE_DIR}/SETUP_GUIDE.md" "${bundle_root}/"
cp "${ASSURANCE_DIR}/README.md" "${bundle_root}/"
cp "${ASSURANCE_DIR}/model-config-snippets/telemetry-subscriptions.ios-xe.cfg" "${bundle_root}/"
cp "${SCRIPT_DIR}/evpn_device_inventory.template.csv" "${bundle_root}/evpn_device_inventory.template.csv"
cp "${SCRIPT_DIR}/evpn_segment_inventory.template.csv" "${bundle_root}/evpn_segment_inventory.template.csv"

rsync -a \
  --exclude '.DS_Store' \
  --exclude '._*' \
  "${OTEL_DIR}/" "${bundle_root}/otel-collector/"

rm -f "${bundle_path}"
(
  cd "${stage_dir}"
  COPYFILE_DISABLE=1 tar -czf "${bundle_path}" "${bundle_name}"
)

echo "Created ${bundle_path}"
shasum -a 256 "${bundle_path}"
