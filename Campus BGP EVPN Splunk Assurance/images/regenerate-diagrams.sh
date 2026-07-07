#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "${SCRIPT_DIR}"

if [[ -z "${PUPPETEER_EXECUTABLE_PATH:-}" ]] && [[ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]]; then
  export PUPPETEER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
fi

for name in build-assure-lifecycle pipeline-flow telemetry-two-halves metric-journey; do
  echo "Rendering ${name}.png ..."
  mmdc -i "${name}.mmd" -o "${name}.png" -b white -w 1200
done

echo "Done. Updated PNGs in ${SCRIPT_DIR}"
