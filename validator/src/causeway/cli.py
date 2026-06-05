from __future__ import annotations

import json
import sys
from pathlib import Path

import click

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


@click.group()
def main() -> None:
    """Causeway platform CLI."""


main.add_command(validate_cmd)

if __name__ == "__main__":
    main()
