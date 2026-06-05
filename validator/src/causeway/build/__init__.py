"""Local build-and-run loop for the Causeway platform.

This package is what lets a builder go from a validated ``causeway.yaml`` plus
application source to a *running container on localhost* with one command —
without ever authoring a Dockerfile. The platform owns the container recipe
(D3); the user owns the manifest and the app code (per scaffold/AGENTS.md).

Scope is deliberately the *local dev loop* only — the run-and-see path the
human's real verification depends on (PLANNING §2, "behavioral verification").
It is NOT deploy: promotion stays gated through CI (D2, D13). See PLANNING.md
decisions D33–D37.
"""
from causeway.build.dockerfile import (
    BASE_IMAGES,
    DEPENDENCY_FILE,
    render_dockerfile,
    runtime_family,
)

__all__ = [
    "BASE_IMAGES",
    "DEPENDENCY_FILE",
    "render_dockerfile",
    "runtime_family",
]
