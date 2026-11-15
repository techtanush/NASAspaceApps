"""Versioned, additive display-only contracts; the 43-operation frozen core remains unchanged."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from analogforge.api.contracts import specification

SCHEMA_NAMES = {
    "VizCapabilitiesV1": "capabilities",
    "VizCoverageV1": "coverage",
    "VizSiteDetailV1": "site-detail",
    "VizSiteBenchmarksV1": "site-benchmarks",
    "VizImageryCatalogV1": "imagery-catalog",
}
# Each enabled runtime route is documented here and checked against its actual registration.
OPERATIONS = (
    ("/visualization/capabilities", "getVisualizationCapabilities", "VizCapabilitiesV1"),
    ("/visualization/openapi.json", "getVisualizationOpenApi", None),
    ("/visualization/coverage", "getVisualizationCoverage", "VizCoverageV1"),
    ("/runs/{run_id}/visualization/target", "getVisualizationTarget", "VizSiteDetailV1"),
    ("/runs/{run_id}/visualization/candidates/{candidate_id}", "getVisualizationCandidate", "VizSiteDetailV1"),
    (
        "/runs/{run_id}/visualization/candidates/{candidate_id}/benchmarks",
        "getVisualizationBenchmarks",
        "VizSiteBenchmarksV1",
    ),
)


@lru_cache(maxsize=1)
def _schemas() -> dict[str, Any]:
    directory = Path(__file__).with_name("visualization_schemas")
    result = {}
    for model, filename in SCHEMA_NAMES.items():
        schema = json.loads((directory / f"{filename}.v1.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        result[model] = schema
    return result


def response_schema(name: str) -> dict[str, Any]:
    return deepcopy(_schemas()[name])


def _parameter(name: str, location: str, schema: dict[str, Any], *, required: bool = True) -> dict[str, Any]:
    return {"name": name, "in": location, "required": required, "schema": schema}


@lru_cache(maxsize=1)
def _combined() -> dict[str, Any]:
    result = deepcopy(specification())
    result["components"]["schemas"].update(deepcopy(_schemas()))
    result["x-analogforge-visualization-version"] = "1.0"
    error = {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}}}
    for path, operation, model in OPERATIONS:
        parameters = [
            _parameter(name, "path", {"type": "string", "format": "uuid"})
            for name in ("run_id", "candidate_id")
            if "{" + name + "}" in path
        ]
        if operation == "getVisualizationCoverage":
            parameters += [
                _parameter("body", "query", {"type": "string", "enum": ["EARTH", "MARS", "MOON"]}),
                _parameter(
                    "bbox",
                    "query",
                    {"type": "string", "maxLength": 256, "description": "west,south,east,north in NEG180_180 degrees"},
                ),
                _parameter("scenario_config_id", "query", {"type": "string", "minLength": 1, "maxLength": 128}),
                _parameter("dataset_lock_id", "query", {"type": "string", "maxLength": 128}, required=False),
            ]
        success = {"$ref": "#/components/schemas/" + model} if model else {"type": "object"}
        result["paths"][path] = {
            "get": {
                "operationId": operation,
                "tags": ["Visualization v1"],
                "parameters": parameters,
                "description": (
                    "Optional read-only display projection. Does not acquire data or change scientific results."
                ),
                "responses": {
                    "200": {
                        "description": "Versioned display projection",
                        "content": {"application/json": {"schema": success}},
                    },
                    **{
                        code: {"description": description, **deepcopy(error)}
                        for code, description in [
                            ("401", "Authentication required"),
                            ("403", "Access denied"),
                            ("404", "Not found"),
                            ("422", "Invalid request"),
                            ("500", "Projection unavailable"),
                            ("503", "Dependency unavailable"),
                        ]
                    },
                },
            }
        }
    return result


def effective_specification() -> dict[str, Any]:
    """A copy so caller metadata cannot mutate core or extension authority."""
    return deepcopy(_combined())


@cache
def _validator(name: str) -> Draft202012Validator:
    document = {**_combined(), **_schemas()[name]}
    return Draft202012Validator(document, format_checker=FormatChecker())


def validate_response(value: dict[str, Any], name: str) -> None:
    _validator(name).validate(value)
