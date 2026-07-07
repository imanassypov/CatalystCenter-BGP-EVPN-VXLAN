# Diagram assets

Committed PNG diagrams for the assurance documentation. Each diagram has a Mermaid
source (`.mmd`) in this folder for maintainers; **published README files embed the
PNG only** — they do not render `.mmd` inline.

| PNG | Source `.mmd` | Used in |
|---|---|---|
| `build-assure-lifecycle.png` | `build-assure-lifecycle.mmd` | [`../README.md`](../README.md) — Build vs. Assure |
| `pipeline-flow.png` | `pipeline-flow.mmd` | [`../README.md`](../README.md), [`../Model Maps/README.md`](../Model Maps/README.md) |
| `telemetry-two-halves.png` | `telemetry-two-halves.mmd` | [`../README.md`](../README.md) — Telemetry Foundations |
| `metric-journey.png` | `metric-journey.mmd` | [`../README.md`](../README.md) — Worked Example |
| `splunk_executive.png` | *(screenshot)* | [`../README.md`](../README.md) — Summary dashboard |

## Regenerate diagram PNGs

Requires [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) (`mmdc`) and a Chrome/Chromium
binary (set `PUPPETEER_EXECUTABLE_PATH` on macOS if needed).

```bash
cd "Campus BGP EVPN Splunk Assurance/images"
./regenerate-diagrams.sh
```

Or manually:

```bash
export PUPPETEER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
mmdc -i build-assure-lifecycle.mmd -o build-assure-lifecycle.png -b white -w 1200
mmdc -i pipeline-flow.mmd -o pipeline-flow.png -b white -w 1200
mmdc -i telemetry-two-halves.mmd -o telemetry-two-halves.png -b white -w 1200
mmdc -i metric-journey.mmd -o metric-journey.png -b white -w 1200
```

Commit the updated `.mmd` and `.png` files together.
