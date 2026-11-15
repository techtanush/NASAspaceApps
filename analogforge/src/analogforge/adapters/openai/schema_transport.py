"""Wire-only schema adaptation; the exact original schema remains the acceptance gate."""

from copy import deepcopy
from typing import Any

import jsonschema

from analogforge.agents.runtime.provider import ProviderError


def invalid_output() -> ProviderError:
    return ProviderError("MODEL_OUTPUT_INVALID", "Provider output failed the original strict schema")


def validate_original(value: Any, schema: dict[str, Any]) -> None:
    try:
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(value)
    except (jsonschema.ValidationError, jsonschema.SchemaError) as exc:
        raise invalid_output() from exc


def wire_schema(original: dict[str, Any], provider: str) -> dict[str, Any]:
    """Drop documented unsupported wire constraints, never edit canonical input.

    Anthropic's official SDK follows this structural-schema/local-validation split.
    Gemini explicitly ignores several constraints. Retain those checks locally.
    SambaNova/NVIDIA receive the complete JSON schema and may reject unsupported
    features; no freeform or unstructured fallback is attempted.
    """
    schema = deepcopy(original)
    removed = {
        "anthropic": {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
                      "minLength", "maxLength", "maxItems", "uniqueItems", "contains", "minContains", "maxContains"},
        "gemini": {"minLength", "maxLength", "minProperties", "maxProperties", "uniqueItems",
                   "contains", "minContains", "maxContains"},
    }.get(provider, set())

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                visit(child)
        elif isinstance(node, dict):
            constraints = {key: node.pop(key) for key in removed if key in node}
            if provider == "anthropic" and node.get("minItems", 0) not in {0, 1}:
                constraints["minItems"] = node.pop("minItems")
            if constraints:
                node["description"] = node.get("description", "") + " Required locally: " + str(constraints)
            # Property/definition names are not schema keywords, even when named minimum or maxLength.
            for key, child in node.items():
                if key in {"properties", "$defs", "definitions", "patternProperties"} and isinstance(child, dict):
                    for value in child.values():
                        visit(value)
                elif key not in {"enum", "const", "default", "examples"}:
                    visit(child)

    visit(schema)
    return schema


def tool_envelope(tools: list[dict[str, Any]], choice: Any) -> dict[str, Any]:
    """Exactly one named tool and its original argument schema; lift local $defs safely."""
    selected = tools
    if isinstance(choice, dict) and choice.get("type") == "function":
        selected = [tool for tool in tools if tool["name"] == choice["name"]]
    elif choice != "required":
        raise invalid_output()
    if not selected:
        raise invalid_output()
    definitions: dict[str, Any] = {}
    branches = []
    for index, tool in enumerate(selected):
        if tool.get("type") != "function" or tool.get("strict") is not True:
            raise invalid_output()
        schema = deepcopy(tool["parameters"])
        own_defs = schema.pop("$defs", {})
        names = {name: f"T{index}_{name}" for name in own_defs}

        def relocate(node: Any, names: dict[str, str] = names) -> None:
            if isinstance(node, dict):
                if "$ref" in node:
                    old = node["$ref"]
                    if not old.startswith("#/$defs/") or old[8:] not in names:
                        raise invalid_output()
                    node["$ref"] = "#/$defs/" + names[old[8:]]
                for child in node.values():
                    relocate(child)
            elif isinstance(node, list):
                for child in node:
                    relocate(child)

        relocate(schema)
        relocate(own_defs)
        definitions.update({names[name]: value for name, value in own_defs.items()})
        branches.append({"type": "object", "properties": {
            "name": {"type": "string", "enum": [tool["name"]]}, "arguments": schema,
        }, "required": ["name", "arguments"], "additionalProperties": False})
    return {"type": "object", "properties": {"call": {"anyOf": branches}},
            "required": ["call"], "additionalProperties": False, **({"$defs": definitions} if definitions else {})}
