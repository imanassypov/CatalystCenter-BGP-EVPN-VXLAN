"""Serialize Python values back into DEFN {% set %} Jinja source."""

from __future__ import annotations

from typing import Any

INDENT = "  "


def render_jinja_literal(value: Any, indent_level: int = 0) -> str:
    """Render a Python value as a Jinja expression literal."""
    pad = INDENT * indent_level

    if value is None:
        return "none"

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"

    if isinstance(value, list):
        if not value:
            return "[]"
        lines = ["["]
        for item in value:
            lines.append(f"{pad}{INDENT}{render_jinja_literal(item, indent_level + 1)},")
        lines.append(f"{pad}]")
        return "\n".join(lines)

    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        for key, item in value.items():
            key_lit = render_jinja_literal(str(key), 0)
            val_lit = render_jinja_literal(item, indent_level + 1)
            if "\n" in val_lit:
                val_lines = val_lit.splitlines()
                first = f"{pad}{INDENT}{key_lit}: {val_lines[0]}"
                rest = [f"{pad}{INDENT}{line}" for line in val_lines[1:]]
                lines.append("\n".join([first, *rest]) + ",")
            else:
                lines.append(f"{pad}{INDENT}{key_lit}: {val_lit},")
        lines.append(f"{pad}}}")
        return "\n".join(lines)

    raise TypeError(f"Unsupported value type for Jinja literal: {type(value)!r}")


def render_set_block(name: str, value: Any, preamble: str = "") -> str:
    expr = render_jinja_literal(value, indent_level=1)
    if "\n" in expr:
        block = f"{{% set {name} = {expr}\n%}}"
    else:
        block = f"{{% set {name} = {expr} %}}"
    if preamble:
        return f"{preamble}{block}"
    return block


def render_defn_file(
    catc_header: str,
    file_leading: str,
    sets: list[dict[str, Any]],
    file_trailing: str = "",
) -> str:
    """Rebuild a DEFN file from parsed metadata and updated values."""
    parts: list[str] = []
    if catc_header:
        parts.append(catc_header.rstrip("\n"))
    if file_leading:
        parts.append(file_leading.rstrip("\n"))

    for item in sets:
        preamble = item.get("preamble", "")
        name = item["name"]
        value = item["value"]
        block = render_set_block(name, value, preamble=preamble)
        parts.append(block.rstrip())
        trailing = item.get("trailing", "")
        if trailing.strip():
            parts.append(trailing.rstrip("\n"))

    if file_trailing.strip():
        parts.append(file_trailing.rstrip("\n"))

    text = "\n".join(parts)
    if not text.endswith("\n"):
        text += "\n"
    return text
