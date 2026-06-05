from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from causeway import loader
from causeway.build import dockerfile, runner
from causeway.validate import validate


@click.command("validate")
@click.argument("path", default="causeway.yaml", type=click.Path(dir_okay=False))
@click.option("--json", "as_json", is_flag=True, help="Output structured JSON instead of human-readable text")
def validate_cmd(path: str, as_json: bool) -> None:
    """Validate a Causeway application manifest.

    PATH defaults to ./causeway.yaml if not specified.

    Exit codes:\n
      0  Valid — no errors\n
      1  Fixable errors — schema/correctness issues; agent may self-correct and re-run\n
      2  Denied errors — policy violations; do not auto-retry
    """
    manifest_path = Path(path)

    if not manifest_path.exists():
        if as_json:
            click.echo(json.dumps({
                "valid": False,
                "errors": [{"field": "manifest", "message": f"File not found: {path}", "type": "fixable"}],
                "warnings": [],
            }))
        else:
            click.echo(f"Error: file not found: {path}", err=True)
        sys.exit(1)

    result = validate(manifest_path)

    if as_json:
        click.echo(json.dumps({
            "valid": result.valid,
            "errors": [{"field": e.field, "message": e.message, "type": e.type} for e in result.errors],
            "warnings": [{"field": w.field, "message": w.message, "type": w.type} for w in result.warnings],
        }, indent=2))
    else:
        if result.valid:
            click.echo(f"✓ {path} is valid")
        else:
            click.echo(f"Validating {path}...\n")
            denied_count = sum(1 for e in result.errors if e.type == "denied")
            fixable_count = sum(1 for e in result.errors if e.type == "fixable")
            for error in result.errors:
                click.echo(f"ERROR [{error.type}] {error.field}")
                # Indent the message
                for line in error.message.splitlines():
                    click.echo(f"  {line}")
                click.echo()
            parts = []
            if denied_count:
                parts.append(f"{denied_count} denied")
            if fixable_count:
                parts.append(f"{fixable_count} fixable")
            click.echo(f"{len(result.errors)} error(s): {', '.join(parts)}")
            if result.has_denied:
                click.echo("Exit: 2 (policy violation — do not auto-retry)")
            else:
                click.echo("Exit: 1 (fixable — correct the fields above and re-run)")

    if result.has_denied:
        sys.exit(2)
    elif result.errors:
        sys.exit(1)
    else:
        sys.exit(0)


# ---------------------------------------------------------------------------
# Local dev loop: build / run / up / down (D33–D37)
#
# These commands turn a validated manifest + app source into a running
# container on localhost — the run-and-see path the human's real verification
# depends on (PLANNING §2). They are NOT deploy: promotion stays gated through
# CI (D2, D13). The platform owns the Dockerfile; the user never writes one.
# ---------------------------------------------------------------------------

def _resolve_project(path: str) -> tuple[Path, Path]:
    """Resolve a build/run argument to (project_dir, manifest_path).

    Accepts either a project directory (looks for causeway.yaml inside) or a
    manifest file directly (its parent is the project dir)."""
    p = Path(path)
    if p.is_file():
        return p.parent, p
    return p, p / "causeway.yaml"


def _load_valid_manifest(manifest_path: Path) -> dict:
    """Validate the manifest and return its dict, or exit with the 0/1/2 contract.

    Build refuses to run on an invalid manifest — the gate comes before any
    container work, reusing the exact exit-code contract agents already loop on."""
    if not manifest_path.exists():
        click.echo(f"Error: manifest not found: {manifest_path}", err=True)
        click.echo("Run this from a project directory containing causeway.yaml.", err=True)
        sys.exit(1)

    result = validate(manifest_path)
    if result.errors:
        click.echo(f"Cannot build — {manifest_path} has errors:\n", err=True)
        for error in result.errors:
            click.echo(f"  ERROR [{error.type}] {error.field}: {error.message}", err=True)
        if result.has_denied:
            click.echo("\nExit: 2 (policy violation — do not auto-retry)", err=True)
            sys.exit(2)
        click.echo("\nExit: 1 (fixable — correct the fields above and re-run)", err=True)
        sys.exit(1)

    return loader.load(manifest_path).data


def _require_runtime() -> str:
    try:
        return runner.detect_runtime()
    except runner.RuntimeNotFound as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)


def _run_app(project_dir: Path, manifest: dict, *, detach: bool, env_file: str) -> None:
    """Start the (already-built) image, health-check it, print the URL."""
    binary = _require_runtime()
    name = manifest["name"]
    port = manifest["port"]
    health = manifest["healthEndpoint"]

    env = runner.load_env_file(project_dir / env_file)
    for var in manifest.get("envVars", []) or []:
        if isinstance(var, dict) and var.get("required") and var.get("name") not in env:
            click.echo(
                f"⚠ required env var {var.get('name')} has no value in {env_file} "
                "— the app may fail to start.",
                err=True,
            )

    try:
        runner.run_container(manifest, env=env, binary=binary)
    except runner.ContainerError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    click.echo(f"Waiting for {name} to become healthy at {health} ...")
    if runner.wait_healthy(port, health):
        click.echo(f"✓ {name} is healthy")
        click.echo(f"\n→ http://localhost:{port}\n")
    else:
        click.echo("⚠ health check did not pass within the timeout. Recent logs:", err=True)
        runner.container_logs(name, tail=40, binary=binary)

    if detach:
        click.echo(f"Running in the background. Stop it with: cwy down {project_dir}")
        return

    click.echo("Streaming logs — press Ctrl-C to stop and remove the container.")
    try:
        runner.stream_logs(name, binary=binary)
    except KeyboardInterrupt:
        pass
    finally:
        runner.stop_container(name, binary=binary)
        click.echo(f"\nStopped and removed {name}.")


@click.command("build")
@click.argument("path", default=".", type=click.Path())
@click.option("--show-dockerfile", is_flag=True,
              help="Print the Dockerfile the platform would build, without building it.")
def build_cmd(path: str, show_dockerfile: bool) -> None:
    """Build PATH's app into a container image (the platform writes the Dockerfile).

    PATH is a project directory (or a manifest file); defaults to the current
    directory. The manifest is validated first — a build is refused on any error.
    """
    project_dir, manifest_path = _resolve_project(path)
    manifest = _load_valid_manifest(manifest_path)

    if show_dockerfile:
        has_deps = (project_dir / dockerfile.dependency_file(manifest["runtime"])).is_file()
        click.echo(dockerfile.render_dockerfile(manifest, has_deps=has_deps), nl=False)
        return

    binary = _require_runtime()
    click.echo(
        f"Building {runner.image_tag(manifest['name'])} "
        f"(runtime {manifest['runtime']}) — the platform owns this Dockerfile.\n"
    )
    try:
        tag = runner.build_image(project_dir, manifest, binary=binary)
    except runner.ContainerError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
    click.echo(f"\n✓ Built {tag}")


@click.command("run")
@click.argument("path", default=".", type=click.Path())
@click.option("-d", "--detach", is_flag=True, help="Run in the background instead of streaming logs.")
@click.option("--env-file", default=".causeway.env", show_default=True,
              help="Local env file (KEY=VALUE) injected at run time; names must match envVars.")
def run_cmd(path: str, detach: bool, env_file: str) -> None:
    """Run PATH's app, building the image first if it does not exist yet."""
    project_dir, manifest_path = _resolve_project(path)
    manifest = _load_valid_manifest(manifest_path)
    binary = _require_runtime()
    if not runner.image_exists(manifest["name"], binary=binary):
        click.echo("Image not built yet — building first.\n")
        try:
            runner.build_image(project_dir, manifest, binary=binary)
        except runner.ContainerError as exc:
            click.echo(str(exc), err=True)
            sys.exit(1)
    _run_app(project_dir, manifest, detach=detach, env_file=env_file)


@click.command("up")
@click.argument("path", default=".", type=click.Path())
@click.option("-d", "--detach", is_flag=True, help="Run in the background instead of streaming logs.")
@click.option("--env-file", default=".causeway.env", show_default=True,
              help="Local env file (KEY=VALUE) injected at run time; names must match envVars.")
def up_cmd(path: str, detach: bool, env_file: str) -> None:
    """Build PATH's app and run it — the one-command run-and-see front door."""
    project_dir, manifest_path = _resolve_project(path)
    manifest = _load_valid_manifest(manifest_path)
    binary = _require_runtime()
    click.echo(
        f"Building {runner.image_tag(manifest['name'])} "
        f"(runtime {manifest['runtime']}) ...\n"
    )
    try:
        runner.build_image(project_dir, manifest, binary=binary)
    except runner.ContainerError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
    click.echo()
    _run_app(project_dir, manifest, detach=detach, env_file=env_file)


@click.command("down")
@click.argument("path", default=".", type=click.Path())
def down_cmd(path: str) -> None:
    """Stop and remove PATH's running container."""
    _, manifest_path = _resolve_project(path)
    if not manifest_path.exists():
        click.echo(f"Error: manifest not found: {manifest_path}", err=True)
        sys.exit(1)
    data = loader.load(manifest_path).data
    if not isinstance(data, dict) or "name" not in data:
        click.echo("Error: could not read 'name' from the manifest.", err=True)
        sys.exit(1)
    binary = _require_runtime()
    runner.stop_container(data["name"], binary=binary)
    click.echo(f"Stopped and removed {data['name']} (if it was running).")


@click.group()
def main() -> None:
    """Causeway platform CLI."""


main.add_command(validate_cmd)
main.add_command(build_cmd)
main.add_command(run_cmd)
main.add_command(up_cmd)
main.add_command(down_cmd)

if __name__ == "__main__":
    main()
