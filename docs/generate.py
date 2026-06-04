"""
Generate derived artefacts from the schema and AGENTS.md source files.

Outputs (never edit by hand):
  docs/manifest-reference.md          — field reference from the JSON Schema
  scaffold/.cursorrules               — Cursor rule file
  scaffold/.github/copilot-instructions.md — GitHub Copilot instruction file

Run: python docs/generate.py
CI asserts: git diff --exit-code (fail if any output is stale)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "causeway-manifest.schema.json"
AGENTS_PATH = REPO_ROOT / "scaffold" / "AGENTS.md"

GENERATED_BANNER = "<!-- GENERATED — do not edit by hand. Run `python docs/generate.py` to regenerate. -->\n\n"


# ---------------------------------------------------------------------------
# Manifest reference doc
# ---------------------------------------------------------------------------

def _type_summary(prop: dict) -> str:
    if "enum" in prop:
        return " | ".join(f"`{v}`" for v in prop["enum"])
    t = prop.get("type", "")
    if t == "array":
        return "array"
    if t == "integer":
        constraints = []
        if "minimum" in prop:
            constraints.append(f"≥ {prop['minimum']}")
        if "maximum" in prop:
            constraints.append(f"≤ {prop['maximum']}")
        return "integer" + (f" ({', '.join(constraints)})" if constraints else "")
    if t == "string":
        constraints = []
        if "minLength" in prop:
            constraints.append(f"min {prop['minLength']} chars")
        if "maxLength" in prop:
            constraints.append(f"max {prop['maxLength']} chars")
        if "pattern" in prop:
            constraints.append(f"pattern: `{prop['pattern']}`")
        if "format" in prop:
            constraints.append(f"format: {prop['format']}")
        return "string" + (f" ({', '.join(constraints)})" if constraints else "")
    return t or "any"


def _examples_line(prop: dict) -> str:
    examples = prop.get("examples", [])
    if not examples:
        return ""
    return "**Examples:** " + ", ".join(f"`{e}`" for e in examples[:4])


def _render_object_fields(properties: dict, required: list[str], indent: int = 0) -> list[str]:
    lines = []
    prefix = "  " * indent
    for name, prop in properties.items():
        req_marker = " *(required)*" if name in required else " *(optional)*"
        lines.append(f"{prefix}#### `{name}`{req_marker}\n")
        lines.append(f"{prefix}**Type:** {_type_summary(prop)}\n\n")
        desc = prop.get("description", "")
        if desc:
            lines.append(f"{prefix}{desc}\n\n")
        ex = _examples_line(prop)
        if ex:
            lines.append(f"{prefix}{ex}\n\n")
        if prop.get("type") == "array" and "items" in prop:
            items = prop["items"]
            if items.get("type") == "object" and "properties" in items:
                lines.append(f"{prefix}**Item fields:**\n\n")
                lines.extend(_render_object_fields(
                    items["properties"],
                    items.get("required", []),
                    indent=indent + 1,
                ))
    return lines


def generate_manifest_reference(schema: dict) -> str:
    props = schema.get("properties", {})
    required = schema.get("required", [])

    lines: list[str] = [
        GENERATED_BANNER,
        "# Causeway Manifest Field Reference\n\n",
        f"{schema.get('description', '')}\n\n",
        "---\n\n",
    ]

    for field_name, prop in props.items():
        req_marker = " *(required)*" if field_name in required else " *(optional)*"
        lines.append(f"## `{field_name}`{req_marker}\n\n")
        lines.append(f"**Type:** {_type_summary(prop)}\n\n")
        desc = prop.get("description", "")
        if desc:
            lines.append(f"{desc}\n\n")
        ex = _examples_line(prop)
        if ex:
            lines.append(f"{ex}\n\n")
        if prop.get("type") == "array" and "items" in prop:
            items = prop["items"]
            if items.get("type") == "object" and "properties" in items:
                lines.append("**Item fields:**\n\n")
                lines.extend(_render_object_fields(
                    items["properties"],
                    items.get("required", []),
                    indent=1,
                ))
        if prop.get("type") == "object" and "properties" in prop:
            lines.append("**Fields:**\n\n")
            lines.extend(_render_object_fields(
                prop["properties"],
                prop.get("required", []),
                indent=1,
            ))
        lines.append("---\n\n")

    # Conditional section
    if_clause = schema.get("if", {})
    then_clause = schema.get("then", {})
    if if_clause and then_clause:
        tier_const = (
            if_clause.get("properties", {}).get("tier", {}).get("const", "")
        )
        extra_required = then_clause.get("required", [])
        if tier_const and extra_required:
            lines.append(
                f"## Conditional requirements\n\n"
                f"When `tier` is `{tier_const}`, the following additional fields are required:\n\n"
            )
            for field in extra_required:
                lines.append(f"- `{field}`\n")
            lines.append("\n")

    return "".join(lines)


# ---------------------------------------------------------------------------
# Tool-specific rule files (generated from AGENTS.md)
# ---------------------------------------------------------------------------

_CURSOR_PREAMBLE = """\
# Causeway — Cursor Rules
# Generated from scaffold/AGENTS.md. Do not edit this file directly.
# To update these rules, edit scaffold/AGENTS.md and run `python docs/generate.py`.

"""

_COPILOT_PREAMBLE = """\
<!-- Causeway — GitHub Copilot Instructions -->
<!-- Generated from scaffold/AGENTS.md. Do not edit this file directly. -->
<!-- To update, edit scaffold/AGENTS.md and run `python docs/generate.py`. -->

"""


def generate_cursorrules(agents_md: str) -> str:
    return _CURSOR_PREAMBLE + agents_md


def generate_copilot_instructions(agents_md: str) -> str:
    return _COPILOT_PREAMBLE + agents_md


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    agents_md = AGENTS_PATH.read_text(encoding="utf-8")

    outputs: list[tuple[Path, str]] = [
        (REPO_ROOT / "docs" / "manifest-reference.md", generate_manifest_reference(schema)),
        (REPO_ROOT / "scaffold" / ".cursorrules", generate_cursorrules(agents_md)),
        (REPO_ROOT / "scaffold" / ".github" / "copilot-instructions.md", generate_copilot_instructions(agents_md)),
    ]

    changed: list[Path] = []
    for path, content in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        if existing != content:
            path.write_text(content, encoding="utf-8")
            changed.append(path)

    if changed:
        print(f"Generated {len(changed)} file(s):")
        for p in changed:
            print(f"  {p.relative_to(REPO_ROOT)}")
    else:
        print("All generated files are up to date.")


if __name__ == "__main__":
    main()
