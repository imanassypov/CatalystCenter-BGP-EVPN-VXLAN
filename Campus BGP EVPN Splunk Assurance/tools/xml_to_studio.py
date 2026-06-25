#!/usr/bin/env python3
"""
Convert Splunk Simple XML (classic) dashboards to Dashboard Studio (version 2).

Reads each `<name>.xml` Simple XML view and writes a side-by-side
`<name>_studio.xml` version-2 dashboard whose JSON definition is embedded in a
<definition><![CDATA[ ... ]]></definition> block.

Design notes:
- SPL queries are copied VERBATIM from the source (ElementTree reads them in full,
  regardless of line length) and JSON-escaped by json.dumps — no manual escaping.
- Tokens ($site$, $timeRange.earliest$/$timeRange.latest$) are preserved unchanged.
- The classic custom Sankey (<viz type="sankey-viz.sankey-viz">) maps to the NATIVE
  Dashboard Studio Sankey (splunk.sankey). The Sankey SPL already emits 3 columns in
  source/target/value order, which splunk.sankey reads positionally.
- Option/format fidelity (colors, axis titles, legends) is best-effort; final polish
  is expected against the live instance ("auto-convert then hand-fix" plan).

Run:
    python3 tools/xml_to_studio.py
"""
from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS_DIR = os.path.join(
    REPO_ROOT, "campus_evpn_assurance", "default", "data", "ui", "views"
)
SOURCES = ["alerts", "executive_overview", "spines", "leafs", "borders"]

# Absolute-layout geometry (Dashboard Studio default canvas width = 1440).
CANVAS_W = 1440
GAP = 10
HEIGHTS = {
    "splunk.singlevalue": 130,
    "splunk.table": 330,
    "splunk.line": 300,
    "splunk.area": 300,
    "splunk.column": 300,
    "splunk.bar": 300,
    "splunk.sankey": 420,
}

# Simple XML panel element -> Studio visualization type.
PANEL_TYPE = {
    "single": "splunk.singlevalue",
    "table": "splunk.table",
    "viz": "splunk.sankey",  # only custom viz used in this app is the sankey
}
CHART_SUBTYPE = {
    "line": "splunk.line",
    "area": "splunk.area",
    "column": "splunk.column",
    "bar": "splunk.bar",
}


def text(el):
    return el.text if el is not None and el.text is not None else None


def hex0x(value):
    """Convert "0x53a051" -> "#53A051"; pass through "#rrggbb"."""
    if value is None:
        return None
    value = value.strip().strip('"')
    if value.startswith("0x"):
        return "#" + value[2:].upper()
    if value.startswith("#"):
        return value.upper()
    return value


def parse_color_map(palette_text):
    """Parse `{"ESTABLISHED":#53a051,"DOWN":#dc4e41}` -> ordered list of (match, color)."""
    pairs = re.findall(r'"([^"]+)"\s*:\s*(#[0-9a-fA-F]{6})', palette_text or "")
    return [(m, c.upper()) for m, c in pairs]


def build_datasource(ds_id, name, search_el):
    query = text(search_el.find("query")) if search_el is not None else None
    options = {"query": query or ""}
    qp = {}
    earliest = text(search_el.find("earliest")) if search_el is not None else None
    latest = text(search_el.find("latest")) if search_el is not None else None
    if earliest is not None:
        qp["earliest"] = earliest
    if latest is not None:
        qp["latest"] = latest
    if qp:
        options["queryParameters"] = qp
    ds = {"type": "ds.search", "options": options}
    if name:
        ds["name"] = name
    return ds


def map_chart_options(opts):
    """Translate a subset of classic charting.* options to Studio chart options."""
    out = {}
    legend = opts.get("charting.legend.placement")
    if legend:
        out["legendDisplay"] = "off" if legend == "none" else legend
    if opts.get("charting.axisTitleX.visibility") == "collapsed":
        out["xAxisTitleVisibility"] = "hide"
    if opts.get("charting.axisTitleY.text"):
        out["yAxisTitleText"] = opts["charting.axisTitleY.text"]
    nvm = opts.get("charting.chart.nullValueMode")
    if nvm:
        out["nullValueDisplay"] = nvm  # connect | zero | gaps
    if opts.get("charting.chart.stackMode") == "stacked":
        out["stackMode"] = "stacked"
    return out


def map_single_options(opts):
    """Translate classic single-value block coloring to Studio dynamic coloring."""
    out = {"sparklineDisplay": "off", "trendDisplay": "off"}
    color_mode = opts.get("colorMode")
    range_colors = opts.get("rangeColors")
    ranges = opts.get("ranges")
    context = {}
    if color_mode == "block" and range_colors and ranges:
        try:
            colors = [hex0x(c) for c in json.loads(range_colors)]
            bounds = json.loads(ranges)
        except (ValueError, TypeError):
            colors, bounds = [], []
        # Build a from/to/value config. Two colors + boundary at bounds[-1]:
        # value < boundary -> colors[0] (good), value >= boundary -> colors[-1] (bad).
        if len(colors) >= 2 and bounds:
            boundary = bounds[-1]
            cfg = [
                {"to": boundary, "value": colors[0]},
                {"from": boundary, "value": colors[-1]},
            ]
            context["singleValueColorConfig"] = cfg
            out["backgroundColor"] = (
                "> primary | seriesByIndex(0) | lastPoint() "
                "| rangeValue(singleValueColorConfig)"
            )
    return out, context


def map_table_formats(format_els):
    """Translate <format type='color' field='X'><colorPalette type='map'>...} to Studio."""
    column_format = {}
    context = {}
    for fmt in format_els:
        if fmt.get("type") != "color":
            continue
        field = fmt.get("field")
        palette = fmt.find("colorPalette")
        if field is None or palette is None or palette.get("type") != "map":
            continue
        mapping = parse_color_map(text(palette))
        if not mapping:
            continue
        cfg_name = re.sub(r"[^A-Za-z0-9]", "", field) + "ColorConfig"
        context[cfg_name] = [{"match": m, "value": c} for m, c in mapping]
        column_format[field] = {
            "color": '> table | seriesByName("%s") | matchValue(%s)'
            % (field, cfg_name)
        }
    return column_format, context


def convert(name):
    src_path = os.path.join(VIEWS_DIR, name + ".xml")
    tree = ET.parse(src_path)
    root = tree.getroot()
    theme = root.get("theme", "light")
    label = text(root.find("label")) or name

    data_sources = {}
    visualizations = {}
    inputs = {}
    structure = []
    global_inputs = []
    defaults_context = {}

    # ---- Inputs (fieldset) ----
    fieldset = root.find("fieldset")
    if fieldset is not None:
        for idx, inp in enumerate(fieldset.findall("input")):
            itype = inp.get("type")
            token = inp.get("token")
            ilabel = text(inp.find("label")) or token
            input_id = "input_%s_%d" % (name, idx)
            if itype == "dropdown":
                ds_id = "ds_%s_input%d" % (name, idx)
                data_sources[ds_id] = build_datasource(
                    ds_id, ilabel, inp.find("search")
                )
                default = text(inp.find("default"))
                inputs[input_id] = {
                    "type": "input.dropdown",
                    "dataSources": {"primary": ds_id},
                    "title": ilabel,
                    "options": {
                        "items": [],
                        "token": token,
                        **({"defaultValue": default} if default else {}),
                    },
                    "encoding": {"value": "primary[0]", "label": "primary[0]"},
                }
                global_inputs.append(input_id)
            elif itype == "time":
                default = inp.find("default")
                earliest = text(default.find("earliest")) if default is not None else "-24h"
                latest = text(default.find("latest")) if default is not None else "now"
                inputs[input_id] = {
                    "type": "input.timerange",
                    "title": ilabel,
                    "options": {
                        "token": token,
                        "defaultValue": "%s,%s" % (earliest or "-24h", latest or "now"),
                    },
                }
                global_inputs.append(input_id)

    # ---- Panels (rows) ----
    panel_idx = 0
    y = 0
    for row in root.findall("row"):
        panels = row.findall("panel")
        if not panels:
            continue
        n = len(panels)
        col_w = (CANVAS_W - GAP * (n - 1)) // n
        row_h = 0
        for i, panel in enumerate(panels):
            # The visualization element is the first recognized child of the panel.
            viz_el = None
            for child in panel:
                if child.tag in ("single", "table", "chart", "viz", "event"):
                    viz_el = child
                    break
            if viz_el is None:
                continue

            tag = viz_el.tag
            if tag == "chart":
                opts_raw = {
                    o.get("name"): text(o) for o in viz_el.findall("option")
                }
                vtype = CHART_SUBTYPE.get(opts_raw.get("charting.chart"), "splunk.line")
            else:
                vtype = PANEL_TYPE.get(tag, "splunk.table")

            title = text(viz_el.find("title"))
            description = text(viz_el.find("description"))
            search_el = viz_el.find("search")

            ds_id = "ds_%s_%d" % (name, panel_idx)
            viz_id = "viz_%s_%d" % (name, panel_idx)
            data_sources[ds_id] = build_datasource(ds_id, title, search_el)

            viz = {"type": vtype, "dataSources": {"primary": ds_id}}
            if title:
                viz["title"] = title
            if description:
                viz["description"] = description

            options = {}
            context = {}
            opts_raw = {o.get("name"): text(o) for o in viz_el.findall("option")}

            if vtype.startswith("splunk.line") or vtype in (
                "splunk.area",
                "splunk.column",
                "splunk.bar",
            ):
                options.update(map_chart_options(opts_raw))
            elif vtype == "splunk.singlevalue":
                so, sctx = map_single_options(opts_raw)
                options.update(so)
                context.update(sctx)
            elif vtype == "splunk.table":
                cf, cctx = map_table_formats(viz_el.findall("format"))
                if cf:
                    options["columnFormat"] = cf
                context.update(cctx)
            elif vtype == "splunk.sankey":
                options["seriesColors"] = [
                    "#1D6FA4",
                    "#53A051",
                    "#F8BE34",
                    "#DC4E41",
                    "#F1813F",
                    "#6DB7C6",
                ]

            if options:
                viz["options"] = options
            if context:
                viz["context"] = context

            visualizations[viz_id] = viz

            h = HEIGHTS.get(vtype, 300)
            row_h = max(row_h, h)
            x = i * (col_w + GAP)
            structure.append(
                {
                    "item": viz_id,
                    "type": "block",
                    "position": {"x": x, "y": y, "w": col_w, "h": h},
                }
            )
            panel_idx += 1
        y += row_h + GAP

    definition = {
        "title": label,
        "visualizations": visualizations,
        "dataSources": data_sources,
        "inputs": inputs,
        "layout": {
            "type": "absolute",
            "options": {"width": CANVAS_W, "height": max(y, 400), "display": "auto"},
            "structure": structure,
            "globalInputs": global_inputs,
        },
    }
    if defaults_context:
        definition["defaults"] = defaults_context

    json_blob = json.dumps(definition, indent=2)
    meta = (
        '{"hideEdit":false,"hideOpenInSearch":false,"hideExport":false}'
    )
    out = (
        '<dashboard version="2" theme="%s">\n'
        "  <label>%s (Studio)</label>\n"
        "  <definition><![CDATA[\n"
        "%s\n"
        "  ]]></definition>\n"
        '  <meta type="hiddenElements"><![CDATA[%s]]></meta>\n'
        "</dashboard>\n"
    ) % (theme, label, json_blob, meta)

    dst_path = os.path.join(VIEWS_DIR, name + "_studio.xml")
    with open(dst_path, "w", encoding="utf-8") as fh:
        fh.write(out)
    return dst_path, len(visualizations), len(inputs)


def main():
    for name in SOURCES:
        dst, nviz, ninp = convert(name)
        print("wrote %s  (%d panels, %d inputs)" % (os.path.relpath(dst, REPO_ROOT), nviz, ninp))


if __name__ == "__main__":
    main()
