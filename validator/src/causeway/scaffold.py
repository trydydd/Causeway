"""Scaffold a new Causeway project from the bundled template (`cwy init`).

The scaffold files (manifest + agent rules) are bundled into the package by
docs/generate.py and loaded here via importlib.resources — the installed CLI
cannot see the repo's scaffold/ dir (same constraint as the bundled schema, D9).
`cwy init` writes them into a project directory so the builder never has to
mkdir + copy by hand (D38). It deliberately scaffolds guidance only, never app
code: app authoring stays a blank slate (D37).
"""
from __future__ import annotations

import re
from importlib.resources import files
from pathlib import Path

# Mirrors the schema's name pattern. Used to decide whether a directory name is
# usable as the manifest `name` (so we can pre-fill it and save the user an edit).
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")

# (bundled filename in data/scaffold, filename written into the project).
# .cursorrules is bundled without its leading dot so package_data globbing picks
# it up; it is written back out as a dotfile here.
_SCAFFOLD_FILES: list[tuple[str, str]] = [
    ("causeway.yaml", "causeway.yaml"),
    ("AGENTS.md", "AGENTS.md"),
    ("cursorrules", ".cursorrules"),
]


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

    Refuses to overwrite an existing causeway.yaml so re-running is safe and
    never destroys work. Pre-fills the manifest ``name`` when ``app_name`` is a
    valid name. Returns the list of files written.
    """
    manifest_path = target / "causeway.yaml"
    if manifest_path.exists():
        raise InitError(
            f"{manifest_path} already exists — refusing to overwrite it. "
            "Run `cwy init` in an empty directory, or remove the existing manifest first."
        )

    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for bundled_name, out_name in _SCAFFOLD_FILES:
        content = _read_bundled(bundled_name)
        if out_name == "causeway.yaml" and app_name and valid_app_name(app_name):
            content = _set_manifest_name(content, app_name)
        out_path = target / out_name
        out_path.write_text(content, encoding="utf-8")
        written.append(out_path)
    return written
