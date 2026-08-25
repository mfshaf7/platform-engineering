from __future__ import annotations

from typing import Any


class OutputSchemaError(ValueError):
    """Raised when a provider schema or provider output is outside the strict subset."""


_ANNOTATION_KEYS = {"$id", "$schema", "description", "title"}
_SUPPORTED_KEYS = {
    *_ANNOTATION_KEYS,
    "additionalProperties",
    "const",
    "enum",
    "items",
    "maxItems",
    "maxLength",
    "minItems",
    "minLength",
    "properties",
    "required",
    "type",
}


def _matches_type(value: Any, expected: str) -> bool:
    return {
        "array": isinstance(value, list),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "null": value is None,
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "object": isinstance(value, dict),
        "string": isinstance(value, str),
    }.get(expected, False)


def validate_supported_schema(schema: Any, path: str = "$") -> dict[str, Any]:
    if not isinstance(schema, dict):
        raise OutputSchemaError(f"{path} schema must be an object")
    unsupported = sorted(set(schema).difference(_SUPPORTED_KEYS))
    if unsupported:
        raise OutputSchemaError(
            f"{path} schema uses unsupported keywords: {','.join(unsupported)}"
        )
    expected_types = schema.get("type")
    if isinstance(expected_types, str):
        expected_types = [expected_types]
    if not isinstance(expected_types, list) or not expected_types or any(
        not isinstance(item, str) or not item for item in expected_types
    ):
        raise OutputSchemaError(f"{path}.type must name at least one JSON type")
    if "object" in expected_types:
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            raise OutputSchemaError(f"{path}.properties must be an object")
        if schema.get("additionalProperties") is not False:
            raise OutputSchemaError(f"{path}.additionalProperties must be false")
        required = schema.get("required", [])
        if not isinstance(required, list) or any(
            not isinstance(item, str) or item not in properties for item in required
        ):
            raise OutputSchemaError(f"{path}.required must reference known properties")
        for name, child in properties.items():
            validate_supported_schema(child, f"{path}.properties.{name}")
    if "array" in expected_types:
        validate_supported_schema(schema.get("items"), f"{path}.items")
    return schema


def validate_output(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    validate_supported_schema(schema)
    expected_types = schema["type"]
    if isinstance(expected_types, str):
        expected_types = [expected_types]
    if not any(_matches_type(value, expected) for expected in expected_types):
        raise OutputSchemaError(f"{path} does not match the required JSON type")
    if "const" in schema and value != schema["const"]:
        raise OutputSchemaError(f"{path} does not match the required constant")
    if "enum" in schema and value not in schema["enum"]:
        raise OutputSchemaError(f"{path} is not an allowed value")
    if isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            raise OutputSchemaError(f"{path} is shorter than allowed")
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            raise OutputSchemaError(f"{path} is longer than allowed")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        missing = sorted(set(schema.get("required", [])).difference(value))
        if missing:
            raise OutputSchemaError(f"{path} is missing required fields: {','.join(missing)}")
        unexpected = sorted(set(value).difference(properties))
        if unexpected and schema.get("additionalProperties") is False:
            raise OutputSchemaError(f"{path} has unexpected fields: {','.join(unexpected)}")
        for name, child in value.items():
            if name in properties:
                validate_output(child, properties[name], f"{path}.{name}")
    if isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            raise OutputSchemaError(f"{path} has fewer items than allowed")
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            raise OutputSchemaError(f"{path} has more items than allowed")
        for index, child in enumerate(value):
            validate_output(child, schema["items"], f"{path}[{index}]")
