"""Tests for the local build-and-run loop (cwy build/run/up/down).

Two layers:
  - Unit tests on the pure Dockerfile renderer and the CLI's gate/dry-run paths.
    These need no container runtime and run everywhere, including CI.
  - Integration tests (@pytest.mark.integration, opt-in via `pytest -m
    integration`) that actually build and run a container and curl its health
    endpoint. They skip cleanly when no daemon is available (docker_ready).

The exit-code contract (0/1/2) is shared with `cwy validate`: a build refuses
on an invalid manifest with the same codes agents already loop on.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from textwrap import dedent

import pytest

from causeway.build import dockerfile, runner

FIXTURES = Path(__file__).parent / "build_fixtures"
PY_HEALTH = FIXTURES / "py-health"
NODE_HEALTH = FIXTURES / "node-health"


def _manifest(runtime: str, *, name: str = "demo", port: int = 8080,
              entrypoint: str = "python app.py", health: str = "/health") -> dict:
    return {
        "apiVersion": "causeway/v1",
        "name": name,
        "runtime": runtime,
        "entrypoint": entrypoint,
        "port": port,
        "healthEndpoint": health,
    }


# ---------------------------------------------------------------------------
# Dockerfile renderer — pure unit tests, no runtime
# ---------------------------------------------------------------------------

def test_base_image_map_covers_schema_runtimes():
    # Keep the base-image map in lockstep with the schema's runtime enum.
    schema = json.loads(
        (Path(__file__).parent.parent / "schema" / "causeway-manifest.schema.json")
        .read_text(encoding="utf-8")
    )
    runtimes = schema["properties"]["runtime"]["enum"]
    assert set(runtimes) == set(dockerfile.BASE_IMAGES), (
        "BASE_IMAGES must match the schema runtime enum exactly."
    )


@pytest.mark.parametrize("runtime,expected_family", [
    ("python3.11", "python"),
    ("python3.12", "python"),
    ("node20", "node"),
    ("node22", "node"),
])
def test_runtime_family(runtime, expected_family):
    assert dockerfile.runtime_family(runtime) == expected_family


def test_runtime_family_rejects_unknown():
    with pytest.raises(ValueError):
        dockerfile.runtime_family("ruby3.2")


def test_render_python_no_deps():
    df = dockerfile.render_dockerfile(_manifest("python3.12"), has_deps=False)
    assert "FROM python:3.12-slim" in df
    assert "WORKDIR /app" in df
    assert "EXPOSE 8080" in df
    assert 'CMD ["sh", "-c", "python app.py"]' in df
    assert 'LABEL causeway.managed="true"' in df
    # No dependency install step when there is no requirements.txt.
    assert "pip install" not in df


def test_render_python_with_deps():
    df = dockerfile.render_dockerfile(_manifest("python3.11"), has_deps=True)
    assert "FROM python:3.11-slim" in df
    assert "COPY requirements.txt ./" in df
    assert "RUN pip install --no-cache-dir -r requirements.txt" in df


def test_render_node_with_deps():
    m = _manifest("node22", port=3000, entrypoint="node server.js")
    df = dockerfile.render_dockerfile(m, has_deps=True)
    assert "FROM node:22-slim" in df
    assert "COPY package.json ./" in df
    assert "RUN npm install --omit=dev" in df
    assert "EXPOSE 3000" in df
    assert 'CMD ["sh", "-c", "node server.js"]' in df
    # Node family must not get a pip step.
    assert "pip install" not in df


def test_render_node_no_deps_has_no_install():
    df = dockerfile.render_dockerfile(_manifest("node20", entrypoint="node server.js"),
                                      has_deps=False)
    assert "npm install" not in df


def test_render_preserves_entrypoint_with_args():
    m = _manifest("python3.12", entrypoint="uvicorn main:app --host 0.0.0.0 --port 8080")
    df = dockerfile.render_dockerfile(m, has_deps=False)
    assert 'CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8080"]' in df


# ---------------------------------------------------------------------------
# CLI gate + dry-run — no runtime required (validation/render happen first)
# ---------------------------------------------------------------------------

def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["cwy", *args], capture_output=True, text=True)


def test_show_dockerfile_needs_no_runtime():
    res = _run_cli("build", str(PY_HEALTH), "--show-dockerfile")
    assert res.returncode == 0
    assert "FROM python:3.12-slim" in res.stdout
    assert '"python app.py"' in res.stdout


def test_show_dockerfile_node_fixture():
    res = _run_cli("build", str(NODE_HEALTH), "--show-dockerfile")
    assert res.returncode == 0
    assert "FROM node:22-slim" in res.stdout


def test_build_refuses_fixable_manifest(tmp_path):
    # A schema-invalid manifest must be refused with exit 1, before any build.
    (tmp_path / "causeway.yaml").write_text(dedent("""\
        apiVersion: causeway/v1
        name: bad-app
        description: A manifest missing the required port field to force a fixable error.
        runtime: python3.12
        entrypoint: python app.py
        healthEndpoint: /health
        tier: personal-team
        dataSources: []
        envVars: []
    """))
    res = _run_cli("build", str(tmp_path), "--show-dockerfile")
    assert res.returncode == 1
    assert "port" in res.stderr


def test_build_refuses_denied_manifest(tmp_path):
    # A policy violation must be refused with exit 2 (do-not-retry).
    (tmp_path / "causeway.yaml").write_text(dedent("""\
        apiVersion: causeway/v1
        name: bad-app
        description: A manifest with the forbidden load-bearing tier to force a denied error.
        runtime: python3.12
        entrypoint: python app.py
        port: 8080
        healthEndpoint: /health
        tier: load-bearing
        dataSources: []
        envVars: []
    """))
    res = _run_cli("build", str(tmp_path))
    assert res.returncode == 2
    assert "tier" in res.stderr


def test_build_missing_manifest(tmp_path):
    res = _run_cli("build", str(tmp_path))
    assert res.returncode == 1
    assert "not found" in res.stderr.lower()


# ---------------------------------------------------------------------------
# Runtime detection — in-process, monkeypatched (no real PATH change)
# ---------------------------------------------------------------------------

def test_detect_runtime_missing(monkeypatch):
    monkeypatch.setattr(runner.shutil, "which", lambda _: None)
    with pytest.raises(runner.RuntimeNotFound) as exc:
        runner.detect_runtime()
    # Message must be adoption-actionable (points at a runtime to install).
    assert "Rancher" in str(exc.value) or "runtime" in str(exc.value).lower()


def test_detect_runtime_prefers_docker(monkeypatch):
    monkeypatch.setattr(runner.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert runner.detect_runtime() == "docker"


def test_env_file_parsing(tmp_path):
    env = tmp_path / ".causeway.env"
    env.write_text("# comment\nDATABASE_URL=postgres://x\nEMPTY_LINE_BELOW=\n\nNOEQUALS\nAPI_KEY = spaced \n")
    parsed = runner.load_env_file(env)
    assert parsed["DATABASE_URL"] == "postgres://x"
    assert parsed["API_KEY"] == "spaced"
    assert parsed["EMPTY_LINE_BELOW"] == ""
    assert "NOEQUALS" not in parsed


def test_env_file_absent_returns_empty(tmp_path):
    assert runner.load_env_file(tmp_path / "nope.env") == {}


def test_image_and_container_naming():
    assert runner.image_tag("expense-tracker") == "causeway/expense-tracker:local"
    assert runner.container_name("expense-tracker") == "causeway-expense-tracker"


# ---------------------------------------------------------------------------
# Integration — real build + run + health curl. Opt-in; skips without a daemon.
# ---------------------------------------------------------------------------

def _curl(url: str, timeout: float = 5.0) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, resp.read().decode()


@pytest.mark.integration
@pytest.mark.parametrize("project,port", [
    (PY_HEALTH, 8080),
    (NODE_HEALTH, 3000),
])
def test_build_and_run_end_to_end(docker_ready, project, port):
    """The headline proof: cwy up -d → health 200 → reachable → cwy down."""
    subprocess.run(["cwy", "down", str(project)], capture_output=True)
    try:
        up = subprocess.run(
            ["cwy", "up", "-d", str(project)], capture_output=True, text=True, timeout=600
        )
        assert up.returncode == 0, f"cwy up failed:\n{up.stdout}\n{up.stderr}"
        assert "is healthy" in up.stdout
        assert f"http://localhost:{port}" in up.stdout

        status, body = _curl(f"http://localhost:{port}/health")
        assert status == 200
        assert json.loads(body)["status"] == "ok"
    finally:
        subprocess.run(["cwy", "down", str(project)], capture_output=True)
