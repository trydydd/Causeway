"""Shared test fixtures.

``docker_ready`` skips integration tests cleanly when no container runtime
daemon is up, so the build-loop integration tests never fail on a machine (or
CI job) without Docker — they simply don't run.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest


def _docker_ready() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(
            ["docker", "info"], capture_output=True, timeout=15
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.fixture(scope="session")
def docker_ready() -> None:
    if not _docker_ready():
        pytest.skip("no running container runtime (docker daemon) available")
