#!/usr/bin/env python3
"""
Thorough validation of the deployed Dashboard Studio (_studio) views.

Runs ON the Splunk EC2 host (reaches https://localhost:8089).

Three tiers:
  1. SERVER-SIDE FETCH  — pull each _studio view definition via REST; proves Splunk
     accepted the version-2 XML + embedded JSON (no parse rejection on load).
  2. STRUCTURE          — every viz.dataSources.primary resolves; every layout item
     references a real viz; globalInputs resolve; every dataSource query is non-empty;
     Sankey panels use splunk.sankey and their SPL ends in a 3-col from,to,value shape.
  3. EXECUTE SPL        — run every unique panel query (oneshot, -4h..now) and report
     resultCount + any error/fatal messages from the search pipeline.
"""
import json
import re
import ssl
import sys
import urllib.parse
import urllib.request

BASE = "https://localhost:8089"
USER = sys.argv[1]
PASS = sys.argv[2]
VIEWS = [
    "alerts",
    "executive_overview",
    "spines",
    "leafs",
    "borders",
]

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def _auth():
    import base64

    tok = base64.b64encode(("%s:%s" % (USER, PASS)).encode()).decode()
    return {"Authorization": "Basic " + tok}


def get(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_auth())
    with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
        return r.read().decode()


def post(path, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(path if path.startswith("http") else BASE + path,
                                 data=body, headers=_auth())
    with urllib.request.urlopen(req, context=CTX, timeout=180) as r:
        return r.read().decode()


def fetch_definition(view):
    """Tier 1: pull the view's eai:data (the raw version-2 XML) from REST."""
    raw = get(
        "/servicesNS/nobody/campus_evpn_assurance/data/ui/views/%s" % view,
        {"output_mode": "json"},
    )
    obj = json.loads(raw)
    return obj["entry"][0]["content"]["eai:data"]


def sub_tokens(q):
    q = q.replace("$site$", "Ottawa")
    q = q.replace("$timeRange.earliest$", "-4h")
    q = q.replace("$timeRange.latest$", "now")
    return q


def run_search(q):
    """Tier 3: oneshot execute; return (resultCount, [messages])."""
    q = sub_tokens(q).strip()
    if not q.startswith("|") and not q.lower().startswith("search"):
        q = "search " + q
    try:
        raw = post(
            "/services/search/jobs",
            {
                "search": q,
                "exec_mode": "oneshot",
                "earliest_time": "-4h",
                "latest_time": "now",
                "output_mode": "json",
                "count": "0",
            },
        )
    except urllib.error.HTTPError as e:
        return None, ["HTTP %s: %s" % (e.code, e.read().decode()[:200])]
    obj = json.loads(raw)
    msgs = []
    for m in obj.get("messages", []):
        if m.get("type") in ("ERROR", "FATAL", "WARN"):
            msgs.append("%s: %s" % (m["type"], m["text"][:160]))
    return len(obj.get("results", [])), msgs


def validate():
    grand = {"views": 0, "panels": 0, "struct_err": 0, "spl_err": 0, "empty": 0}
    seen_queries = {}

    for view in VIEWS:
        print("\n" + "=" * 78)
        print("VIEW:", view)
        print("=" * 78)
        # ---- Tier 1 ----
        try:
            xml = fetch_definition(view)
        except Exception as e:  # noqa
            print("  TIER1 FAIL: could not fetch from REST:", e)
            grand["struct_err"] += 1
            continue
        m = re.search(r"<definition><!\[CDATA\[(.*?)\]\]></definition>", xml, re.S)
        if not m:
            print("  TIER1 FAIL: no <definition> CDATA in server copy")
            grand["struct_err"] += 1
            continue
        try:
            d = json.loads(m.group(1))
        except Exception as e:  # noqa
            print("  TIER1 FAIL: embedded JSON did not parse on server copy:", e)
            grand["struct_err"] += 1
            continue
        grand["views"] += 1
        viz = d["visualizations"]
        ds = d["dataSources"]
        inp = d.get("inputs", {})
        layout = d["layout"]
        print("  TIER1 OK: server accepted version-2; JSON parsed. "
              "viz=%d ds=%d inputs=%d" % (len(viz), len(ds), len(inp)))

        # ---- Tier 2 ----
        s_err = 0
        for vid, v in viz.items():
            prim = v.get("dataSources", {}).get("primary")
            if prim not in ds:
                print("  TIER2 ERR: viz %s -> missing dataSource %s" % (vid, prim))
                s_err += 1
        for item in layout["structure"]:
            if item["item"] not in viz:
                print("  TIER2 ERR: layout item %s not in visualizations" % item["item"])
                s_err += 1
        for gi in layout.get("globalInputs", []):
            if gi not in inp:
                print("  TIER2 ERR: globalInput %s not in inputs" % gi)
                s_err += 1
        for dsid, dd in ds.items():
            if not dd.get("options", {}).get("query", "").strip():
                print("  TIER2 ERR: dataSource %s has empty query" % dsid)
                s_err += 1
        # Sankey-specific
        for vid, v in viz.items():
            if v["type"] == "splunk.sankey":
                q = ds[v["dataSources"]["primary"]]["options"]["query"]
                tail = q.strip().split("|")[-1].lower()
                if "value" not in tail or (" by " not in tail and "from" not in q.lower()):
                    print("  TIER2 WARN: sankey %s tail may not be 3-col: ...%s"
                          % (vid, tail.strip()[:70]))
        if s_err == 0:
            print("  TIER2 OK: all viz/ds/layout/input references resolve")
        grand["struct_err"] += s_err

        # ---- Tier 3 ----
        print("  TIER3: executing %d panel searches (-4h..now)..." % len(viz))
        for vid, v in viz.items():
            q = ds[v["dataSources"]["primary"]]["options"]["query"]
            title = v.get("title", vid)[:46]
            key = sub_tokens(q).strip()
            if key in seen_queries:
                rc, msgs = seen_queries[key]
            else:
                rc, msgs = run_search(q)
                seen_queries[key] = (rc, msgs)
            grand["panels"] += 1
            errs = [x for x in msgs if x.startswith(("ERROR", "FATAL"))]
            warns = [x for x in msgs if x.startswith("WARN")]
            if errs:
                grand["spl_err"] += 1
                print("    [ERR ] %-46s  %s" % (title, errs[0]))
            elif rc == 0:
                grand["empty"] += 1
                tag = "WARN:" + warns[0][5:40] if warns else "no rows in window"
                print("    [0row] %-46s  %s" % (title, tag))
            else:
                print("    [ %3d] %-46s  ok" % (rc, title))

    print("\n" + "#" * 78)
    print("SUMMARY:", json.dumps(grand))
    print("#" * 78)
    if grand["struct_err"] or grand["spl_err"]:
        print("RESULT: FAIL (structure or SPL errors present)")
        return 1
    print("RESULT: PASS (0-row panels are expected when a role/window has no data)")
    return 0


if __name__ == "__main__":
    sys.exit(validate())
