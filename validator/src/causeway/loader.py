from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError

_YAML_LS_HEADER = re.compile(r"^#\s*yaml-language-server:.*$", re.MULTILINE)


@dataclass
class LoadResult:
    data: dict | None
    error: str | None  # set when parsing failed


def load(path: Path) -> LoadResult:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return LoadResult(data=None, error=f"Cannot read file: {exc}")

    # Strip yaml-language-server header — it is not valid YAML and some parsers choke on it
    cleaned = _YAML_LS_HEADER.sub("", raw).strip()

    yaml = YAML(typ="safe")
    try:
        data = yaml.load(cleaned)
    except DuplicateKeyError as exc:
        return LoadResult(data=None, error=f"YAML parse error: duplicate key — {exc}")
    except Exception as exc:
        return LoadResult(data=None, error=f"YAML parse error: {exc}")

    if not isinstance(data, dict):
        return LoadResult(data=None, error="Manifest must be a YAML mapping at the top level")

    return LoadResult(data=data, error=None)
