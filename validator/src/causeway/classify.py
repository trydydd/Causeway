from __future__ import annotations

import re
from typing import Iterator

from causeway.validate import FieldError

# Patterns that strongly indicate a secret value embedded in a string field.
# Ordered from most specific to least to reduce false positives.
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"-----BEGIN\s+\w+\s+PRIVATE KEY-----"),   # PEM private keys
    re.compile(r"sk-[A-Za-z0-9]{20,}"),                   # OpenAI-style API keys
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),         # Slack tokens
    re.compile(r"ghp_[A-Za-z0-9]{36}"),                   # GitHub personal access tokens
    re.compile(r"(?i)password\s*=\s*\S+"),                 # password=value
    re.compile(r"(?i)://[^:@/\s]+:[^:@/\s]+@"),           # user:password@ in URLs
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]{20,}"),  # Bearer tokens
    re.compile(r"(?i)api[_-]?key\s*=\s*\S+"),             # api_key=value
]


def _walk_strings(obj: object, path: str = "") -> Iterator[tuple[str, str]]:
    """Yield (json-path, value) for every string leaf in obj."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, f"{path}[{i}]")


def check_no_hardcoded_secrets(manifest: dict) -> list[FieldError]:
    errors: list[FieldError] = []
    for field_path, value in _walk_strings(manifest):
        for pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                errors.append(FieldError(
                    field=field_path,
                    message=(
                        f"Field '{field_path}' appears to contain a hardcoded secret or credential. "
                        "Declare the variable name in envVars instead and let the platform inject the "
                        "value at runtime. Hardcoded secrets are a policy violation and cannot be "
                        "auto-corrected — report this to the user."
                    ),
                    type="denied",
                ))
                break  # one error per field
    return errors


def check_tier_not_load_bearing(manifest: dict) -> list[FieldError]:
    if manifest.get("tier") == "load-bearing":
        return [FieldError(
            field="tier",
            message=(
                "tier 'load-bearing' is not a valid manifest value. The platform accepts "
                "'personal-team' and 'business-process'. Load-bearing status is determined by "
                "platform telemetry, not declared in the manifest. Set tier to 'personal-team' "
                "or 'business-process'."
            ),
            type="denied",
        )]
    return []


def check_data_sources_not_omitted(manifest: dict) -> list[FieldError]:
    if "dataSources" not in manifest:
        return [FieldError(
            field="dataSources",
            message=(
                "'dataSources' must be present in the manifest. If the application accesses no "
                "external data, set it to an empty array []. Omitting 'dataSources' is a policy "
                "violation — the human reviewer must be able to see the full data scope. "
                "This cannot be auto-corrected."
            ),
            type="denied",
        )]
    return []


def check_env_var_names_not_values(manifest: dict) -> list[FieldError]:
    errors: list[FieldError] = []
    for i, var in enumerate(manifest.get("envVars", []) or []):
        if not isinstance(var, dict):
            continue
        name = var.get("name", "")
        if not isinstance(name, str):
            continue
        if "=" in name:
            errors.append(FieldError(
                field=f"envVars[{i}].name",
                message=(
                    f"envVars[{i}].name contains '=' which suggests a value was included "
                    f"(e.g. 'DATABASE_URL=postgres://...'). The 'name' field must contain only "
                    "the variable name in UPPERCASE — never a value. Values are injected by the "
                    "platform at runtime. This is a policy violation."
                ),
                type="denied",
            ))
    return errors


def check_owner_at_business_process(manifest: dict) -> list[FieldError]:
    if manifest.get("tier") == "business-process" and "owner" not in manifest:
        return [FieldError(
            field="owner",
            message=(
                "tier 'business-process' requires an 'owner' declaration. The named owner is "
                "required for forced-decision events (graduate / contain / sunset) and correctness "
                "attestation. This is a policy requirement — add an owner block with name, email, "
                "decommissionCriteria, and graduationPath."
            ),
            type="denied",
        )]
    return []


ALL_CHECKS = [
    check_no_hardcoded_secrets,
    check_tier_not_load_bearing,
    check_data_sources_not_omitted,
    check_env_var_names_not_values,
    check_owner_at_business_process,
]
