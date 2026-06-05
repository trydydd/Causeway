"""Tests for `cwy init` and the bundled scaffold it writes.

`cwy init` removes the manual mkdir + copy friction (D38). It scaffolds guidance
only — manifest + agent rules — never application code (blank slate, D37).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from causeway import scaffold

REPO_ROOT = Path(__file__).parent.parent


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["cwy", *args], capture_output=True, text=True, cwd=cwd)


# ---------------------------------------------------------------------------
# Bundled scaffold must match the canonical scaffold (drift guard, like the
# schema). CI's validate-generated-files job also catches this; this is the
# fast local signal pointing at `python docs/generate.py`.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bundled,canonical", [
    ("causeway.yaml", "scaffold/causeway.yaml"),
    ("AGENTS.md", "scaffold/AGENTS.md"),
    ("cursorrules", "scaffold/.cursorrules"),
])
def test_bundled_scaffold_matches_canonical(bundled, canonical):
    bundled_text = (
        REPO_ROOT / "validator" / "src" / "causeway" / "data" / "scaffold" / bundled
    ).read_text(encoding="utf-8")
    canonical_text = (REPO_ROOT / canonical).read_text(encoding="utf-8")
    assert bundled_text == canonical_text, (
        f"Bundled scaffold '{bundled}' is out of sync with '{canonical}'. "
        "Run `python docs/generate.py` to regenerate it."
    )


# ---------------------------------------------------------------------------
# cwy init behaviour
# ---------------------------------------------------------------------------

def test_init_named_creates_project(tmp_path):
    res = _run("init", "expense-tracker", cwd=tmp_path)
    assert res.returncode == 0
    project = tmp_path / "expense-tracker"
    assert (project / "causeway.yaml").is_file()
    assert (project / "AGENTS.md").is_file()
    assert (project / ".cursorrules").is_file()


def test_init_prefills_name_from_dir(tmp_path):
    _run("init", "expense-tracker", cwd=tmp_path)
    manifest = (tmp_path / "expense-tracker" / "causeway.yaml").read_text()
    assert "name: expense-tracker" in manifest


def test_init_does_not_scaffold_app_code(tmp_path):
    # Blank slate (D37): init must not plant app.py/server.js or a deps file.
    _run("init", "myapp", cwd=tmp_path)
    project = tmp_path / "myapp"
    for forbidden in ("app.py", "server.js", "requirements.txt", "package.json"):
        assert not (project / forbidden).exists(), f"init should not create {forbidden}"


def test_init_generated_manifest_validates(tmp_path):
    _run("init", "myapp", cwd=tmp_path)
    res = _run("validate", str(tmp_path / "myapp" / "causeway.yaml"))
    assert res.returncode == 0


def test_init_current_directory(tmp_path):
    here = tmp_path / "in-place"
    here.mkdir()
    res = _run("init", cwd=here)
    assert res.returncode == 0
    assert (here / "causeway.yaml").is_file()
    # Name is taken from the (valid) directory name.
    assert "name: in-place" in (here / "causeway.yaml").read_text()


def test_init_refuses_to_clobber(tmp_path):
    _run("init", "myapp", cwd=tmp_path)
    res = _run("init", "myapp", cwd=tmp_path)
    assert res.returncode == 1
    assert "already exists" in res.stderr


def test_init_invalid_dir_name_leaves_default(tmp_path):
    # An uppercase dir name is not a valid app name; init must not write an
    # invalid name into the manifest — it leaves the template default.
    res = _run("init", "MyApp", cwd=tmp_path)
    assert res.returncode == 0
    manifest = (tmp_path / "MyApp" / "causeway.yaml").read_text()
    assert "name: MyApp" not in manifest


# ---------------------------------------------------------------------------
# scaffold module units
# ---------------------------------------------------------------------------

def test_valid_app_name():
    assert scaffold.valid_app_name("expense-tracker")
    assert not scaffold.valid_app_name("MyApp")
    assert not scaffold.valid_app_name("ab")  # below 3-char minimum


def test_init_project_returns_written_paths(tmp_path):
    written = scaffold.init_project(tmp_path / "proj", app_name="proj")
    names = {p.name for p in written}
    assert names == {"causeway.yaml", "AGENTS.md", ".cursorrules"}
