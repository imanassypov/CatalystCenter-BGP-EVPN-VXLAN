#!/usr/bin/env bash
# Verify CML dynamic inventory from repo layout (safe .env load; paths with spaces OK).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ANSIBLE_DIR="${ROOT}/ansible"
ENV_FILE="${ROOT}/.env"
VENV="${ROOT}/.venv"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${VENV}/bin/activate"
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}" >&2
  exit 1
fi

set -a
# shellcheck source=/dev/null
source "${ENV_FILE}"
set +a

cd "${ANSIBLE_DIR}"
ANSIBLE_INVENTORY="${VENV}/bin/ansible-inventory"
if [[ ! -x "${ANSIBLE_INVENTORY}" ]]; then
  ANSIBLE_INVENTORY="ansible-inventory"
fi
echo "CML_HOST=${CML_HOST:-<unset>}  CML_LAB=${CML_LAB:-<unset>}"
echo "Running: ${ANSIBLE_INVENTORY} -i inventory/cml.yml --graph"
echo "---"
"${ANSIBLE_INVENTORY}" -i inventory/cml.yml --graph
