#!/usr/bin/env python3
"""Validate the selected, inactive Prototype Maturity Git identity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "security/prototype-maturity-identity.yaml"
SCHEMA = ROOT / "security/schemas/prototype-maturity-identity.schema.json"


def validate_definition(path: Path) -> dict:
    source = path.read_bytes()
    definition = yaml.safe_load(source)
    schema = json.loads(SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(definition),
        key=lambda error: str(error.path),
    )
    if errors:
        paths = ["/" + "/".join(map(str, error.path)) for error in errors]
        raise ValueError(
            "identity definition violates selected source contract at "
            + ", ".join(paths)
        )
    return {
        "schema_version": 1,
        "identity_id": definition["identity"]["id"],
        "definition_digest": "sha256:" + hashlib.sha256(source).hexdigest(),
        "state": definition["selection"]["state"],
        "identity_projection_enabled": False,
        "workflow_runtime_enabled": False,
        "provider_verified": False,
        "secret_values_embedded": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["validate"])
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args()
    try:
        result = validate_definition(args.contract)
    except (OSError, ValueError, yaml.YAMLError):
        print(
            json.dumps(
                {
                    "valid": False,
                    "error": "invalid-identity-definition",
                    "identity_projection_enabled": False,
                    "workflow_runtime_enabled": False,
                }
            )
        )
        return 1
    print(json.dumps({"valid": True, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
