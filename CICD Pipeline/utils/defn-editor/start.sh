#!/usr/bin/env bash
# Start DEFN editor (Docker). Run from anywhere.
set -euo pipefail
cd "$(dirname "$0")"
exec docker compose up --build
