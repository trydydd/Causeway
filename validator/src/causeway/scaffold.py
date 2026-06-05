"""Scaffold a new Causeway project from the bundled template (`cwy init`).

Two genuine source files are bundled into the package and loaded here via
importlib.resources — the installed CLI cannot see the repo's scaffold/ dir
(same constraint as the bundled schema, D9): the manifest template and AGENTS.md.
The tool-specific agent rule files (.cursorrules, copilot) are NOT bundled — they
are *derived* from the bundled AGENTS.md via the shared registry in rules.py, so
there is one transform and no drift (D39). `cwy init` deliberately scaffolds
guidance only, never app code: app authoring stays a blank slate (D37).
"""
from __future__ import annotations

import re
from importlib.resources import files
from pathlib import Path

from causeway import rules

# Mirrors the schema's name pattern. Used to decide whether a directory name is
# usable as the manifest `name` (so we can pre-fill it and save the user an edit).
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")

# The genuine source files bundled in data/scaffold/ (not derived from anything).
_BUNDLED_SOURCES = ("causeway.yaml", "AGENTS.md")


class InitError(Exception):
    """An init target is unsafe to write (e.g. would clobber an existing manifest)."""


def valid_app_name(name: str) -> bool:
    return bool(_NAME_RE.match(name))


def _read_bundled(name: str) -> str:
    return (
        files("causeway.data").joinpath("scaffold").joinpath(name)
        .read_text(encoding="utf-8")
    )


def _set_manifest_name(manifest_text: str, app_name: str) -> str:
    """Replace the template's top-level `name:` line with the given app name."""
    return re.sub(r"(?m)^name:.*$", f"name: {app_name}", manifest_text, count=1)


def init_project(target: Path, *, app_name: str | None = None) -> list[Path]:
    """Write the scaffold (manifest + agent rules) into ``target``.

    Writes the two bundled sources (causeway.yaml, AGENTS.md), then derives each
    tool rule file in ``rules.RULE_FILES`` from the bundled AGENTS.md. Refuses to
    overwrite an existing causeway.yaml so re-running is safe and never destroys
    work. Pre-fills the manifest ``name`` when ``app_name`` is valid. Returns the
    list of files written.
    """
    manifest_path = target / "causeway.yaml"
    if manifest_path.exists():
        raise InitError(
            f"{manifest_path} already exists — refusing to overwrite it. "
            "Run `cwy init` in an empty directory, or remove the existing manifest first."
        )

    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # 1. The bundled source files.
    for name in _BUNDLED_SOURCES:
        content = _read_bundled(name)
        if name == "causeway.yaml" and app_name and valid_app_name(app_name):
            content = _set_manifest_name(content, app_name)
        out_path = target / name
        out_path.write_text(content, encoding="utf-8")
        written.append(out_path)

    # 2. Tool rule files, derived from the bundled AGENTS.md (one transform — no
    #    drift with the repo's generated copies; see rules.py).
    agents_md = _read_bundled("AGENTS.md")
    for rule in rules.RULE_FILES:
        out_path = target / rule.path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rules.render(rule, agents_md), encoding="utf-8")
        written.append(out_path)

    return written
