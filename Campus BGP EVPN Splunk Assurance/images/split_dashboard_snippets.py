#!/usr/bin/env python3
"""Split full Splunk dashboard screenshots into horizontal row snippets.

Each snippet aligns to a Dashboard Studio layout row (panel bottom border).
Row boundaries are derived from layout Y coordinates, scaled to the screenshot,
then refined by scanning for horizontal panel borders.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

BASE = Path(__file__).resolve().parent.parent

EXEC_NAMES = [
    "scorecards",
    "bgp_trends_vrf_sankey",
    "segment_inventory",
    "l2_segment_placement",
    "busiest_vxlan",
    "bgp_health_matrix",
    "nve_overlay_counts",
    "evpn_route_updates",
    "evpn_rib_churn",
    "bgp_session_drops",
]

DETAIL_NAMES = [
    "scorecards",
    "tunnel_interface_status",
    "bgp_session_state",
    "bgp_vni_trends",
    "bgp_drops_rib_churn",
    "nve_peers_tunnels",
    "nve_peer_adjacency",
    "evpn_binding_control_plane",
    "evpn_binding_data_plane",
    "vxlan_throughput_bum",
    "vxlan_packet_rate_top",
]


def parse_layout(xml_path: Path) -> dict:
    text = xml_path.read_text(encoding="utf-8")
    match = re.search(
        r"<definition><!\[CDATA\[(\{.*\})\]\]></definition>", text, re.DOTALL
    )
    if not match:
        raise ValueError(f"No layout JSON in {xml_path}")
    return json.loads(match.group(1))["layout"]


def row_starts(layout: dict) -> tuple[list[int], int]:
    starts = sorted({block["position"]["y"] for block in layout["structure"]})
    return starts, layout["options"]["height"]


def rgb_at(px, x: int, y: int) -> tuple[int, int, int]:
    val = px[x, y]
    if isinstance(val, int):
        return val, val, val
    return val[0], val[1], val[2]


def border_strength(img: Image.Image, y: int) -> float:
    w = img.size[0]
    px = img.load()
    score = 0.0
    samples = 0
    for x in range(0, w, 6):
        r, g, b = rgb_at(px, x, y)
        total = r + g + b
        if 40 <= total <= 180:
            score += 1.0
        elif total < 40:
            score += 0.5
        samples += 1
    return score / samples


def find_chrome_offset(img: Image.Image) -> int:
    """Y offset where Dashboard Studio panel grid begins (layout y=0)."""
    w, h = img.size
    px = img.load()
    for y in range(40, min(400, h)):
        dark = sum(1 for x in range(0, w, 20) if sum(rgb_at(px, x, y)) < 30)
        if dark > (w // 20) * 0.6:
            return max(0, y - 12)
    return 0


def refine_border(img: Image.Image, expected_y: int, window: int = 40) -> int:
    best_y, best = expected_y, -1.0
    for y in range(max(0, expected_y - window), min(img.size[1], expected_y + window)):
        strength = border_strength(img, y)
        if strength > best:
            best, best_y = strength, y
    return best_y


def split_dashboard(
    img_path: Path,
    layout: dict,
    out_dir: Path,
    prefix: str,
    row_names: list[str],
) -> list[tuple[str, int, int, int]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(img_path).convert("RGB")
    w_px, h_px = img.size
    starts, layout_h = row_starts(layout)
    chrome = find_chrome_offset(img)
    scale_y = (h_px - chrome) / layout_h

    cuts = [0]
    for start in starts[1:]:
        expected = int(chrome + start * scale_y)
        cuts.append(refine_border(img, expected))
    cuts.append(h_px)

    results: list[tuple[str, int, int, int]] = []
    for i in range(len(cuts) - 1):
        top, bottom = cuts[i], cuts[i + 1]
        if bottom - top < 40:
            continue
        name = row_names[i] if i < len(row_names) else f"row{i + 1:02d}"
        fname = f"{prefix}_{name}.png"
        img.crop((0, top, w_px, bottom)).save(out_dir / fname, optimize=True)
        results.append((fname, top, bottom, bottom - top))
    return results


def main() -> int:
    out_dir = Path(__file__).resolve().parent / "snippets"
    views = BASE / "campus_evpn_assurance" / "default" / "data" / "ui" / "views"
    layout_exec = parse_layout(views / "executive_overview.xml")
    layout_node = parse_layout(views / "node_details.xml")
    images = Path(__file__).resolve().parent

    jobs = [
        (images / "splunk_executive.png", layout_exec, "summary", EXEC_NAMES),
        (images / "splunk_leafs.png", layout_node, "leafs", DETAIL_NAMES),
        (images / "splunk_spines.png", layout_node, "spines", DETAIL_NAMES),
        (images / "splunk_borders.png", layout_node, "borders", DETAIL_NAMES),
    ]

    for img_path, layout, prefix, names in jobs:
        if not img_path.exists():
            print(f"SKIP missing {img_path}", file=sys.stderr)
            continue
        results = split_dashboard(img_path, layout, out_dir, prefix, names)
        print(f"{prefix}: {len(results)} snippets")
        for fname, top, bottom, height in results:
            print(f"  {fname}: y={top}-{bottom} h={height}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
