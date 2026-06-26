#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ASSURANCE_DIR=$(cd -- "${SCRIPT_DIR}/.." && pwd)
APP_DIR="${ASSURANCE_DIR}/campus_evpn_assurance"
DIST_DIR="${SCRIPT_DIR}/dist"

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

mkdir -p "${DIST_DIR}"

stage_dir=$(mktemp -d "${TMPDIR:-/tmp}/campus_evpn_assurance.XXXXXX")
cleanup() {
  rm -rf "${stage_dir}"
}
trap cleanup EXIT

rsync -a \
  --exclude 'local/' \
  --exclude '.DS_Store' \
  --exclude '._*' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "${APP_DIR}/" "${stage_dir}/campus_evpn_assurance/"

package_path="${DIST_DIR}/campus_evpn_assurance-${version}.spl"
rm -f "${package_path}"

(
  cd "${stage_dir}"
  COPYFILE_DISABLE=1 tar -czf "${package_path}" campus_evpn_assurance
)

echo "Created ${package_path}"
shasum -a 256 "${package_path}"
