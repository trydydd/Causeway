"""
Tests for the cwy validate command and underlying validation logic.

Each fixture file is tested for its expected exit code and JSON output shape.
The exit-code contract (0/1/2) must not change — agent self-correction loops
and CI both depend on it.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

_MINIMAL_VALID = dedent("""\
    apiVersion: causeway/v1
    name: test-app
    description: A minimal valid manifest used as a base for parametrised error tests.
    runtime: python3.12
    entrypoint: python app.py
    port: 8080
    healthEndpoint: /health
    tier: personal-team
    dataSources: []
    envVars: []
""")


def run_cwy(path: str | Path) -> tuple[int, dict]:
    """Run `cwy validate <path> --json` and return (exit_code, parsed_json)."""
    result = subprocess.run(
        ["cwy", "validate", str(path), "--json"],
        capture_output=True,
        text=True,
    )
    output = json.loads(result.stdout)
    return result.returncode, output


def make_manifest(tmp_path: Path, overrides: str = "", *, remove_keys: list[str] | None = None) -> Path:
    """Write a manifest to tmp_path, starting from _MINIMAL_VALID.

    overrides: lines to append (or replace existing keys via a simple string patch)
    remove_keys: list of top-level keys to strip entirely from the base
    """
    lines = _MINIMAL_VALID.splitlines(keepends=True)
    if remove_keys:
        lines = [
            line for line in lines
            if not any(line.startswith(f"{key}:") for key in remove_keys)
        ]
    base = "".join(lines)
    p = tmp_path / "causeway.yaml"
    p.write_text(base + ("\n" + overrides if overrides else ""))
    return p


# ---------------------------------------------------------------------------
# Valid manifests — exit 0, valid: true
# ---------------------------------------------------------------------------

def test_valid_personal_team():
    code, data = run_cwy(FIXTURES / "valid-personal-team.yaml")
    assert code == 0
    assert data["valid"] is True
    assert data["errors"] == []


def test_valid_business_process():
    code, data = run_cwy(FIXTURES / "valid-business-process.yaml")
    assert code == 0
    assert data["valid"] is True
    assert data["errors"] == []


def test_valid_scaffold_template():
    """The pre-filled scaffold must always pass validation — CI enforces this too."""
    scaffold = Path(__file__).parent.parent / "scaffold" / "causeway.yaml"
    code, data = run_cwy(scaffold)
    assert code == 0
    assert data["valid"] is True


# ---------------------------------------------------------------------------
# File / parse errors — exit 1 (fixable at the file level)
# ---------------------------------------------------------------------------

def test_file_not_found(tmp_path):
    result = subprocess.run(
        ["cwy", "validate", str(tmp_path / "nonexistent.yaml"), "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["valid"] is False
    assert any("not found" in e["message"].lower() or "file" in e["message"].lower()
               for e in data["errors"])


def test_invalid_yaml_syntax(tmp_path):
    bad = tmp_path / "causeway.yaml"
    bad.write_text("apiVersion: causeway/v1\nname: [unclosed bracket\n")
    code, data = run_cwy(bad)
    assert code == 1
    assert data["valid"] is False
    assert any("parse" in e["message"].lower() or "yaml" in e["message"].lower()
               for e in data["errors"])


def test_yaml_not_a_mapping(tmp_path):
    bad = tmp_path / "causeway.yaml"
    bad.write_text("- item1\n- item2\n")
    code, data = run_cwy(bad)
    assert code == 1
    assert data["valid"] is False
    assert any("mapping" in e["message"].lower() or "dict" in e["message"].lower()
               for e in data["errors"])


# ---------------------------------------------------------------------------
# Fixable errors — exit 1, all errors typed "fixable"
# ---------------------------------------------------------------------------

def test_fixable_missing_port():
    code, data = run_cwy(FIXTURES / "fixable-missing-port.yaml")
    assert code == 1
    assert data["valid"] is False
    assert any(e["field"] == "port" for e in data["errors"])
    assert all(e["type"] == "fixable" for e in data["errors"])


def test_fixable_bad_runtime():
    code, data = run_cwy(FIXTURES / "fixable-bad-runtime.yaml")
    assert code == 1
    assert data["valid"] is False
    assert any(e["field"] == "runtime" for e in data["errors"])
    assert all(e["type"] == "fixable" for e in data["errors"])


def test_fixable_port_below_minimum(tmp_path):
    p = make_manifest(tmp_path, remove_keys=["port"])
    p.write_text(p.read_text() + "port: 80\n")
    code, data = run_cwy(p)
    assert code == 1
    assert any(e["field"] == "port" for e in data["errors"])
    assert all(e["type"] == "fixable" for e in data["errors"])


def test_fixable_port_above_maximum(tmp_path):
    p = make_manifest(tmp_path, remove_keys=["port"])
    p.write_text(p.read_text() + "port: 99999\n")
    code, data = run_cwy(p)
    assert code == 1
    assert any(e["field"] == "port" for e in data["errors"])


def test_fixable_health_endpoint_no_leading_slash(tmp_path):
    p = make_manifest(tmp_path, remove_keys=["healthEndpoint"])
    p.write_text(p.read_text() + "healthEndpoint: health\n")
    code, data = run_cwy(p)
    assert code == 1
    assert any(e["field"] == "healthEndpoint" for e in data["errors"])
    assert all(e["type"] == "fixable" for e in data["errors"])


def test_fixable_name_invalid_pattern(tmp_path):
    """Name with uppercase letters must fail schema validation."""
    p = make_manifest(tmp_path, remove_keys=["name"])
    p.write_text(p.read_text() + "name: MyApp\n")
    code, data = run_cwy(p)
    assert code == 1
    assert any(e["field"] == "name" for e in data["errors"])
    assert all(e["type"] == "fixable" for e in data["errors"])


def test_fixable_description_too_short(tmp_path):
    p = make_manifest(tmp_path, remove_keys=["description"])
    p.write_text(p.read_text() + "description: Too short\n")
    code, data = run_cwy(p)
    assert code == 1
    assert any(e["field"] == "description" for e in data["errors"])


def test_fixable_multiple_errors_at_once(tmp_path):
    """Missing port and bad runtime — both fixable, both reported, exit 1."""
    p = make_manifest(tmp_path, remove_keys=["port", "runtime"])
    p.write_text(p.read_text() + "runtime: python2.7\n")
    code, data = run_cwy(p)
    assert code == 1
    assert len(data["errors"]) >= 2
    assert all(e["type"] == "fixable" for e in data["errors"])
    fields = {e["field"] for e in data["errors"]}
    assert "port" in fields
    assert "runtime" in fields


# ---------------------------------------------------------------------------
# Denied errors — exit 2, at least one error typed "denied"
# ---------------------------------------------------------------------------

def test_denied_hardcoded_secret():
    code, data = run_cwy(FIXTURES / "denied-hardcoded-secret.yaml")
    assert code == 2
    denied = [e for e in data["errors"] if e["type"] == "denied"]
    assert len(denied) >= 1
    assert any("secret" in e["message"].lower() or "credential" in e["message"].lower()
               for e in denied)


def test_denied_load_bearing_tier():
    code, data = run_cwy(FIXTURES / "denied-load-bearing-tier.yaml")
    assert code == 2
    denied = [e for e in data["errors"] if e["type"] == "denied"]
    assert any(e["field"] == "tier" for e in denied)
    # Must not also appear as fixable — denied wins
    assert not any(e["field"] == "tier" and e["type"] == "fixable" for e in data["errors"])


def test_denied_missing_owner_at_bp():
    code, data = run_cwy(FIXTURES / "denied-missing-owner-at-bp.yaml")
    assert code == 2
    denied = [e for e in data["errors"] if e["type"] == "denied"]
    assert any(e["field"] == "owner" for e in denied)
    # Must not have a duplicate fixable error for the same field
    assert not any(e["field"] == "owner" and e["type"] == "fixable" for e in data["errors"])


def test_denied_env_var_name_contains_equals(tmp_path):
    """envVars[].name containing '=' means a value was embedded — policy violation."""
    p = make_manifest(tmp_path, remove_keys=["envVars"])
    p.write_text(p.read_text() + dedent("""\
        envVars:
          - name: DATABASE_URL=postgres://localhost/mydb
            description: Connection string for the database
            required: true
    """))
    code, data = run_cwy(p)
    assert code == 2
    denied = [e for e in data["errors"] if e["type"] == "denied"]
    assert any("envVars" in e["field"] for e in denied)


def test_denied_data_sources_omitted(tmp_path):
    """dataSources key absent entirely is a policy violation, not just a schema error."""
    p = make_manifest(tmp_path, remove_keys=["dataSources"])
    code, data = run_cwy(p)
    assert code == 2
    denied = [e for e in data["errors"] if e["type"] == "denied"]
    assert any(e["field"] == "dataSources" for e in denied)
    # Schema would also flag this as required — denied must win (no duplicate fixable)
    assert not any(e["field"] == "dataSources" and e["type"] == "fixable" for e in data["errors"])


def test_denied_bearer_token_in_env_var_description(tmp_path):
    """Bearer token in any string field triggers the secret check."""
    p = make_manifest(tmp_path, remove_keys=["envVars"])
    p.write_text(p.read_text() + dedent("""\
        envVars:
          - name: AUTH_TOKEN
            description: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature
            required: true
    """))
    code, data = run_cwy(p)
    assert code == 2
    assert any(e["type"] == "denied" for e in data["errors"])


def test_denied_connection_string_in_description(tmp_path):
    """Connection string with embedded credentials in any description field."""
    p = make_manifest(tmp_path, remove_keys=["dataSources"])
    p.write_text(p.read_text() + dedent("""\
        dataSources:
          - name: main-db
            type: postgres
            access: read
            description: postgres://admin:hunter2@db.internal/prod
    """))
    code, data = run_cwy(p)
    assert code == 2
    assert any(e["type"] == "denied" for e in data["errors"])


# ---------------------------------------------------------------------------
# JSON output structure contract
# ---------------------------------------------------------------------------

def test_json_output_has_required_keys():
    _, data = run_cwy(FIXTURES / "valid-personal-team.yaml")
    assert "valid" in data
    assert "errors" in data
    assert "warnings" in data


def test_json_error_items_have_required_keys():
    _, data = run_cwy(FIXTURES / "fixable-missing-port.yaml")
    for error in data["errors"]:
        assert "field" in error
        assert "message" in error
        assert "type" in error
        assert error["type"] in ("fixable", "denied")


# ---------------------------------------------------------------------------
# Exit code precedence and contract
# ---------------------------------------------------------------------------

def test_denied_exit_code_beats_fixable(tmp_path):
    """A manifest with both a policy violation and a schema error must exit 2."""
    p = make_manifest(tmp_path, remove_keys=["port", "tier"])
    # Missing port (fixable) + load-bearing tier (denied)
    p.write_text(p.read_text() + "tier: load-bearing\n")
    code, data = run_cwy(p)
    assert code == 2
    assert any(e["type"] == "denied" for e in data["errors"])


def test_valid_manifest_has_zero_errors(tmp_path):
    """A fully valid manifest must have an empty errors list, not just valid: true."""
    p = make_manifest(tmp_path)
    code, data = run_cwy(p)
    assert code == 0
    assert data["errors"] == []
    assert data["warnings"] == []


def test_error_messages_are_nonempty(tmp_path):
    """Every reported error must have a non-blank message."""
    p = make_manifest(tmp_path, remove_keys=["port", "runtime"])
    p.write_text(p.read_text() + "runtime: python2.7\n")
    _, data = run_cwy(p)
    for e in data["errors"]:
        assert e["message"].strip(), f"Empty message for field {e['field']!r}"
