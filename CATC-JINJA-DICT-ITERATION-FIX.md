# CatC Jinja2 Bug: Dict Iteration in Included-Scope Templates

## Root Cause

Cisco Catalyst Center's Jinja2 rendering engine fails to resolve `dict[key]`
when the key originates from iterating a dict defined in an **included** file
(`{% include "..." %}`). The loop variable resolves correctly and `loop.index`
works, but bracket notation `dict[key]` returns **empty string** — producing
invalid CLI such as `permit /32` with no IP address.

This affects **all** dict iteration patterns in included-scope files:

| Pattern | Broken? | Why |
|---|---|---|
| `{% for k in dict %}` → `dict[k]` | **Yes** | Loop var is key-iterator object, not a plain string |
| `{% for k, v in dict.items() %}` | **Yes** | Two-variable loop unsupported entirely in CatC Jinja |
| `{% for k in some_list %}` → `dict[k]` | **No** | List iteration yields plain strings; bracket lookup works |

> **Scope matters.** This bug only manifests in dicts defined inside included
> `DEFN-*.j2` files. Dicts defined directly in the same FABRIC template are
> unaffected, but the correct pattern should be used universally.

---

## Symptom

Template renders with missing IP addresses:

```
ip prefix-list NODE-LOOPBACKS seq 1 permit /32
                                            ^^^^^
                                            missing IP — dict[key] returned empty
```

Device rejects the config:

```
Leaf-02(config)#ip prefix-list NODE-LOOPBACKS seq 7 permit /32
                                                           ^
% Invalid input detected at '^' marker.
```

---

## Fix: Companion List Pattern

For every dict in a `DEFN-*.j2` file that needs to be iterated, define a
companion flat list containing the same keys. Iterate the **list** in
`FABRIC-*.j2` templates and use the list item (a plain string) as the bracket
key into the dict.

---

## DEFN-LOOPBACKS.j2 — Before / After

### Before

```jinja
{% set DEFN_LOOP_UNDERLAY =
    {
      'Spine-01.dcloud.cisco.com':   '198.19.1.1',
      'Spine-02.dcloud.cisco.com':   '198.19.1.2',
      'Leaf-01.dcloud.cisco.com':    '198.19.1.3',
      'Leaf-02.dcloud.cisco.com':    '198.19.1.4',
      'Border-01.dcloud.cisco.com':  '198.19.1.5',
      'Border-02.dcloud.cisco.com':  '198.19.1.6'
    }
%}
{% set DEFN_LOOP_MCLUSTER =
    {
      'dmz1.dcloud.cisco.com': {'ip': '198.19.1.200', 'asn': '65003'}
    }
%}
```

### After

```jinja
{# Flat list companion - iterate this to avoid CatC dict-key-iterator bracket lookup failure #}
{% set DEFN_ALL_NODES = [
    'Spine-01.dcloud.cisco.com',
    'Spine-02.dcloud.cisco.com',
    'Leaf-01.dcloud.cisco.com',
    'Leaf-02.dcloud.cisco.com',
    'Border-01.dcloud.cisco.com',
    'Border-02.dcloud.cisco.com'
] %}
{% set DEFN_LOOP_UNDERLAY =
    {
      'Spine-01.dcloud.cisco.com':   '198.19.1.1',
      'Spine-02.dcloud.cisco.com':   '198.19.1.2',
      'Leaf-01.dcloud.cisco.com':    '198.19.1.3',
      'Leaf-02.dcloud.cisco.com':    '198.19.1.4',
      'Border-01.dcloud.cisco.com':  '198.19.1.5',
      'Border-02.dcloud.cisco.com':  '198.19.1.6'
    }
%}
{# Flat list companion - iterate this to avoid CatC dict-key-iterator bracket lookup failure #}
{% set DEFN_MCLUSTER_NODES = [
    'dmz1.dcloud.cisco.com'
] %}
{% set DEFN_LOOP_MCLUSTER =
    {
      'dmz1.dcloud.cisco.com': {'ip': '198.19.1.200', 'asn': '65003'}
    }
%}
```

---

## FABRIC-EVPN.j2 — Before / After

### Change 1: NODE-LOOPBACKS prefix-list (local nodes)

**Before** — iterates dict directly; `DEFN_LOOP_UNDERLAY[node]` returns empty:
```jinja
{% for node in DEFN_LOOP_UNDERLAY %}
ip prefix-list NODE-LOOPBACKS seq {{loop.index}} permit {{DEFN_LOOP_UNDERLAY[node]}}/32
{% endfor %}
```

**Rendered (broken):**
```
ip prefix-list NODE-LOOPBACKS seq 1 permit /32
ip prefix-list NODE-LOOPBACKS seq 2 permit /32
...
```

**After** — iterates companion list; bracket lookup works:
```jinja
{% for node in DEFN_ALL_NODES %}
ip prefix-list NODE-LOOPBACKS seq {{loop.index}} permit {{DEFN_LOOP_UNDERLAY[node]}}/32
{% endfor %}
```

**Rendered (correct):**
```
ip prefix-list NODE-LOOPBACKS seq 1 permit 198.19.1.1/32
ip prefix-list NODE-LOOPBACKS seq 2 permit 198.19.1.2/32
ip prefix-list NODE-LOOPBACKS seq 3 permit 198.19.1.3/32
ip prefix-list NODE-LOOPBACKS seq 4 permit 198.19.1.4/32
ip prefix-list NODE-LOOPBACKS seq 5 permit 198.19.1.5/32
ip prefix-list NODE-LOOPBACKS seq 6 permit 198.19.1.6/32
```

---

### Change 2: NODE-LOOPBACKS prefix-list (MCLUSTER remote peers)

**Before** — iterates dict directly; `DEFN_LOOP_MCLUSTER[remote]['ip']` returns empty:
```jinja
{% for remote in DEFN_LOOP_MCLUSTER %}
ip prefix-list NODE-LOOPBACKS seq {{DEFN_LOOP_UNDERLAY | length + loop.index}} permit {{DEFN_LOOP_MCLUSTER[remote]['ip']}}/32
{% endfor %}
```

**Rendered (broken):**
```
ip prefix-list NODE-LOOPBACKS seq 7 permit /32
```

**After** — iterates companion list:
```jinja
{% for remote in DEFN_MCLUSTER_NODES %}
ip prefix-list NODE-LOOPBACKS seq {{DEFN_LOOP_UNDERLAY | length + loop.index}} permit {{DEFN_LOOP_MCLUSTER[remote]['ip']}}/32
{% endfor %}
```

**Rendered (correct):**
```
ip prefix-list NODE-LOOPBACKS seq 7 permit 198.19.1.200/32
```

---

### Change 3: BGP neighbor block (BORDER nodes only)

**Before:**
```jinja
{% for remote in DEFN_LOOP_MCLUSTER %}
  neighbor {{DEFN_LOOP_MCLUSTER[remote]['ip']}} remote-as {{DEFN_LOOP_MCLUSTER[remote]['asn']}}
  neighbor {{DEFN_LOOP_MCLUSTER[remote]['ip']}} inherit peer-session OVERLAY-MCLUSTER-EVPN-PEER-SESSION-POLICY
{% endfor %}
```

**After:**
```jinja
{% for remote in DEFN_MCLUSTER_NODES %}
  neighbor {{DEFN_LOOP_MCLUSTER[remote]['ip']}} remote-as {{DEFN_LOOP_MCLUSTER[remote]['asn']}}
  neighbor {{DEFN_LOOP_MCLUSTER[remote]['ip']}} inherit peer-session OVERLAY-MCLUSTER-EVPN-PEER-SESSION-POLICY
{% endfor %}
```

---

### Change 4: l2vpn evpn address-family neighbor block (BORDER nodes only)

**Before:**
```jinja
{% for remote in DEFN_LOOP_MCLUSTER %}
   neighbor {{DEFN_LOOP_MCLUSTER[remote]['ip']}} activate
   neighbor {{DEFN_LOOP_MCLUSTER[remote]['ip']}} inherit peer-policy OVERLAY-MCLUSTER-EVPN-PEER-POLICY
{% endfor %}
```

**After:**
```jinja
{% for remote in DEFN_MCLUSTER_NODES %}
   neighbor {{DEFN_LOOP_MCLUSTER[remote]['ip']}} activate
   neighbor {{DEFN_LOOP_MCLUSTER[remote]['ip']}} inherit peer-policy OVERLAY-MCLUSTER-EVPN-PEER-POLICY
{% endfor %}
```

---

## Rule for New Dicts

Whenever you add a new dict to any `DEFN-*.j2` file that will be iterated
in a `FABRIC-*.j2` template, you **must** also define a companion flat list:

```jinja
{# 1. Companion list — iterate this in FABRIC templates #}
{% set DEFN_MY_NODES = [
    'node-a.example.com',
    'node-b.example.com'
] %}
{# 2. Dict — used only for lookups, never for iteration #}
{% set DEFN_MY_DICT = {
    'node-a.example.com': '10.0.0.1',
    'node-b.example.com': '10.0.0.2'
} %}
```

Keep both in sync whenever entries are added or removed.
