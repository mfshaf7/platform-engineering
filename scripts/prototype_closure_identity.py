#!/usr/bin/env python3
"""Validate and verify the dedicated Prototype Closure identity."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from jsonschema import Draft202012Validator
import yaml

from repository_provider_identity import IdentityError
from workspace_intake_identity import parse_source_revisions, validated_token, write_receipt


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


@dataclass(frozen=True)
class ClosureProviderContract:
    identity_id: str
    contract_digest: str
    api_base_url: str
    repository: str
    repository_id: int
    repository_owner: str
    repository_owner_id: int
    repository_owner_type: str
    maximum_repository_count: int
    maximum_token_lifetime_seconds: int
    required_permissions: dict[str, str]


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


def closure_contract(source: bytes, definition: dict) -> ClosureProviderContract:
    identity = definition["identity"]
    repository = identity["repository"]
    owner, _ = repository["full_name"].split("/", 1)
    return ClosureProviderContract(
        identity_id=identity["id"],
        contract_digest="sha256:" + hashlib.sha256(source).hexdigest(),
        api_base_url="https://api.github.com",
        repository=repository["full_name"],
        repository_id=repository["id"],
        repository_owner=owner,
        repository_owner_id=repository["owner_id"],
        repository_owner_type=repository["owner_type"],
        maximum_repository_count=identity["maximum_repository_count"],
        maximum_token_lifetime_seconds=identity["maximum_token_lifetime_seconds"],
        required_permissions=dict(identity["required_permissions"]),
    )


def remote_head(workspace_root: Path, repository: str) -> str:
    root = workspace_root.resolve()
    repo = (root / repository).resolve()
    if repo.parent != root or not (repo / ".git").exists():
        raise IdentityError(f"{repository} source repository is unavailable")
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-remote", "--exit-code", "origin", "refs/heads/main"],
        text=True, capture_output=True, check=False, timeout=30,
    )
    if result.returncode != 0:
        raise IdentityError(f"{repository} remote main is unavailable")
    return result.stdout.split()[0]


def commission(args: argparse.Namespace, source: bytes, definition: dict) -> None:
    if not args.security_receipt_ref or not args.security_receipt_ref.strip():
        raise IdentityError("exact Security approval receipt is required")
    revisions = parse_source_revisions(args.source_revision)
    required = {
        "workspace-governance-control-fabric",
        "operator-orchestration-service",
        "platform-engineering",
        "security-architecture",
    }
    if set(revisions) != required:
        raise IdentityError("commissioning requires exact WGCF, OOS, Platform, and Security revisions")
    for repository, revision in revisions.items():
        if remote_head(args.workspace_root, repository) != revision:
            raise IdentityError(f"{repository} source revision is not current remote main")
    contract = closure_contract(source, definition)
    client, token, repository = validated_token(args, contract)
    client.revoke_token(token.token)
    recorded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write_receipt(args.receipt, {
        "schema_version": 1,
        "artifact_type": "prototype-closure-identity-commission-receipt",
        "identity_id": contract.identity_id,
        "definition_digest": contract.contract_digest,
        "source_revisions": revisions,
        "security_receipt_ref": args.security_receipt_ref,
        "caller_id": args.caller_id,
        "action": "commission",
        "app_id": args.app_id,
        "installation_id": args.installation_id,
        "repository_id": repository.provider_repository_id,
        "permissions": contract.required_permissions,
        "issued_at": recorded_at,
        "expires_at": token.expires_at,
        "recorded_at": recorded_at,
        "outcome": "exact-installation-verified-proof-token-revoked",
        "runtime_enabled": False,
        "secret_values_embedded": False,
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("validate", "commission"), default="validate")
    parser.add_argument("--app-id", type=int)
    parser.add_argument("--installation-id", type=int)
    parser.add_argument("--private-key-file", type=Path)
    parser.add_argument("--provider-api-base-url")
    parser.add_argument("--sandbox", action="store_true")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--caller-id")
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--security-receipt-ref")
    parser.add_argument("--source-revision", action="append", default=[])
    args = parser.parse_args(argv)
    source = DEFINITION.read_bytes()
    definition = yaml.safe_load(source)
    schema = json.loads(SCHEMA.read_text())
    errors = validate_definition(definition, schema)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    if args.command == "commission":
        if not all((args.app_id, args.installation_id, args.private_key_file, args.receipt, args.caller_id, args.workspace_root)):
            parser.error("commission requires --app-id, --installation-id, --private-key-file, --caller-id, --workspace-root, and --receipt")
        try:
            commission(args, source, definition)
        except (IdentityError, ValueError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Prototype Closure installation verified; receipt={args.receipt}")
        return 0
    print("Prototype Closure identity definition valid and inactive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
