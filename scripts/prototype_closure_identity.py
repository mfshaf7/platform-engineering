#!/usr/bin/env python3
"""Validate the inactive Prototype Closure identity before Security admission."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFINITION = ROOT / "security/prototype-closure-identity.yaml"
SCHEMA = ROOT / "security/schemas/prototype-closure-identity.schema.json"

ENFORCEMENT = {
    "restrict-main-updates-to-human-actors",
    "prototype-closure-app-has-no-bypass",
    "require-exact-head-review",
    "dismiss-stale-approvals",
    "require-trusted-owner-validation",
    "deny-force-push-and-deletion",
}
DENIED_ACTIONS = {
    "merge", "direct-main-write", "force-push", "repository-create",
    "repository-delete", "repository-administration", "unrelated-repository-access",
    "wildcard-repository-selection", "prototype-landing-write",
    "prototype-maturity-write", "durable-owner-repository-write",
    "prototype-source-delete", "personal-token", "ambient-gh-credentials",
}
ACTIVATION_EVIDENCE = {
    "exact-definition-digest-and-source-heads",
    "exact-app-installation-and-repository-ids",
    "provider-enforced-main-and-merge-denial",
    "exact-permissions-and-no-bypass",
    "authenticated-profile-and-session-binding",
    "short-lived-token-delivery-and-rotation",
    "landing-and-maturity-identity-separation",
    "exact-active-resource-revocation-or-absence-proof",
    "secret-free-owner-receipt",
}
AUDIT_FIELDS = {
    "definition_digest", "source_revisions", "app_id", "installation_id",
    "repository_id", "caller_id", "profile_id", "session_ref", "action",
    "outcome", "issued_at", "expires_at", "security_receipt_ref",
    "rollback_receipt_ref",
}


def validate_definition(definition: dict, schema: dict) -> list[str]:
    Draft202012Validator.check_schema(schema)
    errors = [
        "/" + "/".join(map(str, error.path)) + ": " + error.message
        for error in Draft202012Validator(schema).iter_errors(definition)
    ]
    if errors:
        return sorted(errors)

    boundary = definition["source_boundary"]
    if set(boundary["provider_enforcement_required"]) != ENFORCEMENT:
        errors.append("source_boundary.provider_enforcement_required must match the exact provider controls")
    if set(boundary["denied_actions"]) != DENIED_ACTIONS:
        errors.append("source_boundary.denied_actions must preserve every denial")
    if set(definition["activation"]["required_evidence"]) != ACTIVATION_EVIDENCE:
        errors.append("activation.required_evidence must preserve every activation gate")
    if set(definition["audit"]["receipt_fields"]) != AUDIT_FIELDS:
        errors.append("audit.receipt_fields must preserve every receipt binding")
    return errors


def main() -> int:
    definition = yaml.safe_load(DEFINITION.read_text())
    schema = json.loads(SCHEMA.read_text())
    errors = validate_definition(definition, schema)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print("Prototype Closure identity definition valid and inactive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
