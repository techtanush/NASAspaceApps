"""Validation against the immutable public contract, including its local references."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


@lru_cache(maxsize=1)
def specification() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[3] / "contracts/openapi.bundled.json"
    return dict(json.loads(path.read_text()))


def validate(value: Any, schema: dict[str, Any]) -> None:
    document = {"$schema": "https://json-schema.org/draft/2020-12/schema", **specification(), **schema}
    Draft202012Validator(document, format_checker=FormatChecker()).validate(value)


def public_document(document: dict[str, Any], model: str) -> dict[str, Any]:
    """Remove internal runtime data without inventing absent public values."""
    schema = specification()["components"]["schemas"][model]
    while "$ref" in schema:
        schema = specification()["components"]["schemas"][schema["$ref"].split("/")[-1]]
    return {key: document[key] for key in schema.get("properties", {}) if key in document}
