from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from causeway import loader, schema as schema_mod

_REQUIRED_RE = re.compile(r"'([^']+)' is a required property")


@dataclass
class FieldError:
    field: str
    message: str
    type: Literal["fixable", "denied"]


@dataclass
class ValidationResult:
    valid: bool
    errors: list[FieldError] = field(default_factory=list)
    warnings: list[FieldError] = field(default_factory=list)

    @property
    def has_denied(self) -> bool:
        return any(e.type == "denied" for e in self.errors)


def _jsonschema_path(error) -> str:
    """Convert a jsonschema ValidationError to a readable dot-notation field name."""
    parts = list(error.absolute_path)

    if error.validator == "required":
        # For required errors the absolute_path points to the parent object, not the missing field.
        # Extract the missing field name from the message instead.
        m = _REQUIRED_RE.search(error.message)
        missing = m.group(1) if m else "unknown"
        parent = ".".join(str(p) for p in parts)
        return f"{parent}.{missing}" if parent else missing

    if not parts:
        return "manifest"

    result = ""
    for part in parts:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += f".{part}" if result else str(part)
    return result


def _schema_error_message(error) -> str:
    """Produce a concise, LLM-consumable message from a jsonschema ValidationError."""
    path = _jsonschema_path(error)
    validator = error.validator

    if validator == "enum":
        allowed = ", ".join(f"'{v}'" for v in error.validator_value)
        return f"'{path}' value {error.instance!r} is not allowed. Valid values are: {allowed}."
    if validator == "required":
        return f"'{path}' is required but is missing."
    if validator == "pattern":
        return (
            f"'{path}' value {error.instance!r} does not match the required pattern "
            f"{error.validator_value!r}. {error.schema.get('description', '')}"
        )
    if validator in ("minimum", "maximum"):
        op = ">=" if validator == "minimum" else "<="
        return f"'{path}' value {error.instance!r} is out of range. Must be {op} {error.validator_value}."
    if validator in ("minLength", "maxLength"):
        direction = "short" if validator == "minLength" else "long"
        op = "at least" if validator == "minLength" else "at most"
        return f"'{path}' is too {direction}. Must be {op} {error.validator_value} characters."
    if validator == "type":
        return (
            f"'{path}' must be of type {error.validator_value!r}, "
            f"got {type(error.instance).__name__!r}."
        )
    if validator == "format":
        return f"'{path}' value {error.instance!r} is not a valid {error.validator_value}."
    if validator == "additionalProperties":
        extras = set(error.instance.keys()) - set(error.schema.get("properties", {}).keys())
        return (
            f"Unknown field(s) in '{path}': {', '.join(repr(k) for k in sorted(extras))}. "
            "Remove unrecognised fields."
        )
    return error.message


def validate(manifest_path: Path) -> ValidationResult:
    # Load and parse
    load_result = loader.load(manifest_path)
    if load_result.error:
        return ValidationResult(
            valid=False,
            errors=[FieldError(field="manifest", message=load_result.error, type="fixable")],
        )

    manifest = load_result.data

    # Import here to avoid circular imports with classify importing FieldError from this module
    from causeway.classify import ALL_CHECKS

    # Pass 1: policy checks (denied errors)
    denied_fields: set[str] = set()
    denied_errors: list[FieldError] = []
    for check in ALL_CHECKS:
        for err in check(manifest):
            denied_errors.append(err)
            denied_fields.add(err.field)

    # Pass 2: schema validation (fixable errors)
    # Skip fixable errors for fields that already have a denied error — denied wins
    validator = schema_mod.get_validator()
    fixable_errors: list[FieldError] = []
    for schema_error in validator.iter_errors(manifest):
        field_path = _jsonschema_path(schema_error)
        if field_path in denied_fields:
            continue
        fixable_errors.append(FieldError(
            field=field_path,
            message=_schema_error_message(schema_error),
            type="fixable",
        ))

    all_errors = denied_errors + fixable_errors
    return ValidationResult(valid=not all_errors, errors=all_errors)
