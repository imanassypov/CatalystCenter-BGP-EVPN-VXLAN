"""Parse DEFN-*.j2 files and extract {% set %} variables with preamble preservation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, nodes
from jinja2.nativetypes import NativeEnvironment

CATC_HEADER_RE = re.compile(r"^\{##.*##\}\s*\n?", re.MULTILINE)
SET_BLOCK_RE = re.compile(
    r"(?P<preamble>(?:[^{]|\{(?!%))*?)\{%\s*set\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<expr>.*?)\s*%\}",
    re.DOTALL,
)


@dataclass
class ParsedDefnFile:
    path: Path
    catc_header: str = ""
    file_leading: str = ""
    sets: list[dict[str, Any]] = field(default_factory=list)
    file_trailing: str = ""

    def variables(self) -> dict[str, Any]:
        return {item["name"]: item["value"] for item in self.sets}


def parse_defn_file(path: Path) -> ParsedDefnFile:
    source = path.read_text(encoding="utf-8")
    return parse_defn_source(source, path.name)


def parse_defn_source(source: str, filename: str) -> ParsedDefnFile:
    parsed = ParsedDefnFile(path=Path(filename))

    header_match = CATC_HEADER_RE.match(source)
    if header_match:
        parsed.catc_header = header_match.group(0)
        remainder = source[header_match.end() :]
    else:
        remainder = source

    matches = list(SET_BLOCK_RE.finditer(remainder))
    if not matches:
        parsed.file_leading = remainder
        return parsed

    parsed.file_leading = remainder[: matches[0].start()]
    env = NativeEnvironment(extensions=["jinja2.ext.do"])

    for idx, match in enumerate(matches):
        name = match.group("name")
        expr = match.group("expr").strip()
        preamble = match.group("preamble")
        try:
            compiled = env.compile_expression(expr)
            value = compiled()
        except Exception as exc:
            raise ValueError(f"{filename}: failed to evaluate set '{name}': {exc}") from exc

        block_end = match.end()
        if idx + 1 < len(matches):
            trailing = remainder[block_end : matches[idx + 1].start()]
        else:
            trailing = remainder[block_end:]

        parsed.sets.append(
            {
                "name": name,
                "value": value,
                "preamble": preamble,
                "expr_source": expr,
                "trailing": trailing,
            }
        )

    last = matches[-1]
    parsed.file_trailing = remainder[last.end() :]
    return parsed


def validate_jinja_syntax(source: str, label: str = "") -> None:
    env = Environment(extensions=["jinja2.ext.do"])
    try:
        env.parse(source)
    except Exception as exc:
        prefix = f"{label}: " if label else ""
        raise ValueError(f"{prefix}Jinja2 syntax error: {exc}") from exc


def list_defn_files(folder: Path) -> list[Path]:
    return sorted(folder.glob("DEFN-*.j2"))


def walk_set_nodes(source: str) -> list[str]:
    """Return set variable names using Jinja AST (sanity check)."""
    env = Environment(extensions=["jinja2.ext.do"])
    ast = env.parse(source)
    names: list[str] = []
    for node in ast.find_all(nodes.Assign):
        if isinstance(node.target, nodes.Name):
            names.append(node.target.name)
    return names
