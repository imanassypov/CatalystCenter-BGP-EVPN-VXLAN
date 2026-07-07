#!/usr/bin/env bash
# Deploy campus_evpn_assurance .spl to Splunk (jump host → EC2).
# Credentials: CICD Pipeline/utils/mcp-ssh-server/.env (never commit secrets).
set -euo pipefail

# Resolve symlinks so invocation via .cursor/skills/.../deploy-splunk-app.sh works.
SOURCE="${BASH_SOURCE[0]}"
while [[ -L "${SOURCE}" ]]; do
  link_dir=$(cd -- "$(dirname -- "${SOURCE}")" && pwd)
  SOURCE=$(readlink "${SOURCE}")
  [[ "${SOURCE}" != /* ]] && SOURCE="${link_dir}/${SOURCE}"
done
SCRIPT_DIR=$(cd -- "$(dirname -- "${SOURCE}")" && pwd)
ASSURANCE_DIR=$(cd -- "${SCRIPT_DIR}/.." && pwd)
REPO_ROOT=$(cd -- "${ASSURANCE_DIR}/.." && pwd)
ENV_FILE="${REPO_ROOT}/CICD Pipeline/utils/mcp-ssh-server/.env"
APP_CONF="${ASSURANCE_DIR}/campus_evpn_assurance/default/app.conf"
DEPLOY_PY="${SCRIPT_DIR}/scripts/deploy_splunk.py"

SKIP_BUILD=false
VERIFY_MARKER=""

usage() {
  cat <<'EOF'
Usage: deploy-splunk-app.sh [OPTIONS]

Deploy campus_evpn_assurance to Splunk via jump host (paramiko).

Options:
  --skip-build              Skip ./build-app.sh (use latest .spl in dist/)
  --verify-marker STRING    After restart, verify marker in executive_overview REST
  -h, --help                Show this help

Requires .env with SCRIPT_SERVER_SSH_PASS, SPLUNK_ADMIN_USER, SPLUNK_ADMIN_PASS,
and SPLUNK_SSH_KEY_PATH (default: splunk-creds/ec2user-splunk.pem relative to .env).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-build)
      SKIP_BUILD=true
      shift
      ;;
    --verify-marker)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --verify-marker requires a value" >&2
        exit 1
      fi
      VERIFY_MARKER="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  set +a
else
  echo "WARNING: ${ENV_FILE} not found — ensure env vars are exported" >&2
fi

if [[ "${SKIP_BUILD}" != true ]]; then
  echo "==> Building .spl package"
  "${SCRIPT_DIR}/build-app.sh"
else
  echo "==> Skipping build (--skip-build)"
fi

shopt -s nullglob
spl_files=("${SCRIPT_DIR}/dist"/campus_evpn_assurance-*.spl)
shopt -u nullglob

if [[ ${#spl_files[@]} -eq 0 ]]; then
  echo "ERROR: no .spl found in ${SCRIPT_DIR}/dist/ — run build-app.sh first" >&2
  exit 1
fi

# Use newest package if multiple versions exist
SPL_FILE=$(ls -t "${spl_files[@]}" | head -1)
echo "==> Deploying ${SPL_FILE}"

deploy_args=(
  python3 "${DEPLOY_PY}"
  --spl "${SPL_FILE}"
  --local-app-conf "${APP_CONF}"
)

if [[ -f "${ENV_FILE}" ]]; then
  deploy_args+=(--env-file "${ENV_FILE}")
fi

if [[ -n "${VERIFY_MARKER}" ]]; then
  deploy_args+=(--verify-marker "${VERIFY_MARKER}")
fi

"${deploy_args[@]}"
