"""Drive a container runtime to build and run a Causeway app on localhost.

Thin wrapper over the ``docker`` (or ``nerdctl``) CLI. Responsibilities:
  - locate a container runtime, or fail with an adoption-friendly message (D7);
  - assemble an *ephemeral* build context so the user's project stays free of
    any Dockerfile (D3);
  - build, run with port + env injection, poll the health endpoint, tear down.

Everything here is local dev loop only. Nothing in this module ships an image
or talks to a registry for promotion — that path stays in CI (D2, D13).
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from causeway.build.dockerfile import (
    CONTEXT_EXCLUDES,
    dependency_file,
    render_dockerfile,
)

_RUNTIME_BINARIES = ("docker", "nerdctl")
_HEALTH_TIMEOUT_S = 30.0
_HEALTH_INTERVAL_S = 0.5


class RuntimeNotFound(Exception):
    """No container runtime (docker/nerdctl) is installed or on PATH."""


class ContainerError(Exception):
    """A build or run command returned non-zero."""


# ---------------------------------------------------------------------------
# Naming — derived from the manifest name so commands are idempotent.
# ---------------------------------------------------------------------------

def image_tag(name: str) -> str:
    return f"causeway/{name}:local"


def container_name(name: str) -> str:
    return f"causeway-{name}"


# ---------------------------------------------------------------------------
# Runtime detection
# ---------------------------------------------------------------------------

def detect_runtime() -> str:
    """Return the container runtime binary to use, or raise RuntimeNotFound.

    The error text points at Rancher Desktop (D7) — installing a runtime is the
    single biggest adoption blocker (D8), so the message has to be actionable.
    """
    for binary in _RUNTIME_BINARIES:
        if shutil.which(binary):
            return binary
    raise RuntimeNotFound(
        "No container runtime found. Causeway builds your app into a container "
        "locally, which needs Docker or nerdctl on PATH.\n"
        "Recommended: install Rancher Desktop (https://rancherdesktop.io) — it is "
        "free and does not require admin/WSL2 reconfiguration on locked-down machines.\n"
        "Once it is running, re-run this command."
    )


def runtime_available() -> bool:
    """True if a runtime binary exists AND its daemon answers. Used to skip the
    live build path (e.g. integration tests) cleanly when no daemon is up."""
    try:
        binary = detect_runtime()
    except RuntimeNotFound:
        return False
    try:
        return subprocess.run(
            [binary, "info"], capture_output=True, timeout=15
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_image(
    project_dir: Path,
    manifest: dict,
    *,
    binary: str | None = None,
    quiet: bool = False,
) -> str:
    """Build the app image from an ephemeral context and return its tag.

    The user's project is copied into a temp dir (minus CONTEXT_EXCLUDES); the
    Dockerfile and .dockerignore are written there, never into the project. This
    is how infra stays invisible (D3) while the manifest stays the only surface
    the user touches.
    """
    binary = binary or detect_runtime()
    tag = image_tag(manifest["name"])
    has_deps = (project_dir / dependency_file(manifest["runtime"])).is_file()
    dockerfile = render_dockerfile(manifest, has_deps=has_deps)

    with tempfile.TemporaryDirectory(prefix="causeway-build-") as tmp:
        context = Path(tmp) / "context"
        shutil.copytree(
            project_dir, context, ignore=shutil.ignore_patterns(*CONTEXT_EXCLUDES)
        )
        (context / "Dockerfile").write_text(dockerfile, encoding="utf-8")
        (context / ".dockerignore").write_text(
            "\n".join(CONTEXT_EXCLUDES) + "\n", encoding="utf-8"
        )

        cmd = [binary, "build", "-t", tag, str(context)]
        if quiet:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise ContainerError(
                    f"Build failed (exit {proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
                )
        else:
            # Stream build output so the user sees progress — this is run-and-see.
            if subprocess.run(cmd).returncode != 0:
                raise ContainerError("Build failed. See the output above.")

    return tag


def image_exists(name: str, *, binary: str | None = None) -> bool:
    binary = binary or detect_runtime()
    return subprocess.run(
        [binary, "image", "inspect", image_tag(name)], capture_output=True
    ).returncode == 0


# ---------------------------------------------------------------------------
# Run / health / teardown
# ---------------------------------------------------------------------------

def run_container(
    manifest: dict,
    *,
    env: dict[str, str] | None = None,
    port: int | None = None,
    binary: str | None = None,
) -> str:
    """Start the app detached and return its container name.

    Any previous container of the same name is removed first so the loop is
    idempotent (disposability — PLANNING §2). Env values are injected at run
    time only; they are never baked into the image (D36).
    """
    binary = binary or detect_runtime()
    name = manifest["name"]
    cname = container_name(name)
    internal_port = manifest["port"]
    external_port = port or internal_port

    # Idempotent: clear any stale container from a previous run.
    subprocess.run([binary, "rm", "-f", cname], capture_output=True)

    cmd = [binary, "run", "-d", "--name", cname,
           "-p", f"{external_port}:{internal_port}"]
    for key, value in (env or {}).items():
        cmd += ["-e", f"{key}={value}"]
    cmd.append(image_tag(name))

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ContainerError(f"Failed to start container:\n{proc.stderr.strip()}")
    return cname


def wait_healthy(
    port: int,
    health_path: str,
    *,
    timeout: float = _HEALTH_TIMEOUT_S,
) -> bool:
    """Poll http://localhost:<port><health_path> until it returns 2xx or timeout.

    This is the platform performing the same health gate it promises in the
    manifest (healthEndpoint) — locally, before declaring the app ready."""
    url = f"http://localhost:{port}{health_path}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= resp.status < 300:
                    return True
        except (urllib.error.URLError, OSError):
            pass  # not up yet
        time.sleep(_HEALTH_INTERVAL_S)
    return False


def container_logs(name: str, *, tail: int | None = None, binary: str | None = None) -> None:
    """Print recent logs (best-effort) — used when health never goes green."""
    binary = binary or detect_runtime()
    cmd = [binary, "logs"]
    if tail is not None:
        cmd += ["--tail", str(tail)]
    cmd.append(container_name(name))
    subprocess.run(cmd)


def stream_logs(name: str, *, binary: str | None = None) -> None:
    """Follow logs in the foreground until interrupted (Ctrl-C)."""
    binary = binary or detect_runtime()
    subprocess.run([binary, "logs", "-f", container_name(name)])


def stop_container(name: str, *, binary: str | None = None) -> None:
    binary = binary or detect_runtime()
    subprocess.run([binary, "rm", "-f", container_name(name)], capture_output=True)


# ---------------------------------------------------------------------------
# Local env file (.causeway.env) — names must match the manifest's envVars.
# ---------------------------------------------------------------------------

def load_env_file(path: Path) -> dict[str, str]:
    """Parse a gitignored ``.causeway.env`` (KEY=VALUE per line) for local runs.

    This is the local stand-in for the platform secrets manager (D36). The file
    is local-only and excluded from the build context — values never enter the
    image. Real secret injection is an off-localhost concern, deferred.
    """
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env
