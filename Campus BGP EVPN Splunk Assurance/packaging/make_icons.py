#!/usr/bin/env python3
"""Generate Splunk app launcher icons for campus_evpn_assurance.

Renders a simple spine-leaf fabric glyph (two top nodes, three bottom nodes,
mesh links) on a transparent background, in dark and light variants, at 36px
and 72px. No external assets required — pure PIL drawing.
"""
import sys
from PIL import Image, ImageDraw

# (node_fill, link_color) per variant
VARIANTS = {
    "appIcon": ((0x12, 0xA5, 0xD6), (0x6F, 0xC9, 0xE8)),       # dark UI: cisco blue
    "appIconAlt": ((0x0B, 0x5A, 0x8A), (0x3A, 0x7C, 0xA5)),    # light UI: darker blue
}

# Layout in a 72x72 design space; scaled for 36.
SPINES = [(24, 20), (48, 20)]
LEAFS = [(16, 52), (36, 52), (56, 52)]


def draw_icon(size: int, node_fill, link_color) -> Image.Image:
    SS = 4  # supersample for smooth edges
    img = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    scale = (size * SS) / 72.0

    def pt(p):
        return (p[0] * scale, p[1] * scale)

    lw = max(1, int(2.2 * scale))
    # mesh links (every spine to every leaf)
    for s in SPINES:
        for l in LEAFS:
            d.line([pt(s), pt(l)], fill=link_color + (255,), width=lw)

    r = 6.5 * scale  # node radius
    for p in SPINES + LEAFS:
        x, y = pt(p)
        d.ellipse([x - r, y - r, x + r, y + r], fill=node_fill + (255,))

    return img.resize((size, size), Image.LANCZOS)


def main(out_dir: str):
    import os
    os.makedirs(out_dir, exist_ok=True)
    for base, (node_fill, link_color) in VARIANTS.items():
        draw_icon(36, node_fill, link_color).save(os.path.join(out_dir, f"{base}.png"))
        draw_icon(72, node_fill, link_color).save(os.path.join(out_dir, f"{base}_2x.png"))
        print(f"wrote {base}.png (36x36) and {base}_2x.png (72x72)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
