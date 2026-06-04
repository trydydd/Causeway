from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

import jsonschema
from jsonschema import Draft202012Validator


@lru_cache(maxsize=1)
def get_validator() -> Draft202012Validator:
    schema_text = (
        files("causeway.data").joinpath("causeway-manifest.schema.json").read_text(encoding="utf-8")
    )
    schema = json.loads(schema_text)
    return Draft202012Validator(schema)
