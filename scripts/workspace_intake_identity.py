#!/usr/bin/env python3
"""Validate, commission, deliver, and revoke the Workspace Intake Git identity."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from repository_provider_identity import (
    DevIntegrationTarget,
    IdentityError,
    IssuedToken,
    ProviderClient,
    ProviderRepository,
    create_app_jwt,
    load_dev_integration_target,
    run_kubectl,
    validate_repositories,
    verify_dev_integration_cluster,
    verify_kubectl_command,
    verify_token,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "security/workspace-intake-identity.yaml"
SCHEMA = ROOT / "security/schemas/workspace-intake-identity.schema.json"
BROKER_DEPLOYMENT = "operator-orchestration-service"
SOURCE_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Contract:
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
    runtime_secret_name: str
    runtime_secret_key: str
    runtime_directory: str
    runtime_filename: str
    token_file_env: str
    repository_owner_env: str
    repository_id_env: str
    allowed_dev_integration_profiles: tuple[str, ...]
    security_gate: str


def _load_definition(path: Path) -> tuple[bytes, dict[str, Any]]:
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
            "identity definition violates selected source contract at " + ", ".join(paths)
        )
    return source, definition


def load_contract(path: Path) -> Contract:
    source, definition = _load_definition(path)
    identity = definition["identity"]
    repository = identity["repository"]
    projection = definition["secret_custody"]["runtime_projection"]
    consumer = definition["consumer"]
    return Contract(
        identity_id=identity["id"],
        contract_digest="sha256:" + hashlib.sha256(source).hexdigest(),
        api_base_url=identity["api_base_url"].rstrip("/"),
        repository=repository["full_name"],
        repository_id=repository["id"],
        repository_owner=repository["full_name"].split("/", 1)[0],
        repository_owner_id=repository["owner_id"],
        repository_owner_type=repository["owner_type"],
        maximum_repository_count=identity["maximum_repository_count"],
        maximum_token_lifetime_seconds=identity["maximum_token_lifetime_seconds"],
        required_permissions=dict(identity["required_permissions"]),
        runtime_secret_name=projection["name"],
        runtime_secret_key=projection["key"],
        runtime_directory=projection["directory"],
        runtime_filename=projection["filename"],
        token_file_env=consumer["token_file_env"],
        repository_owner_env=consumer["repository_owner_env"],
        repository_id_env=consumer["repository_id_env"],
        allowed_dev_integration_profiles=tuple(consumer["allowed_profiles"]),
        security_gate=definition["activation"]["security_gate"],
    )


def validate_definition(path: Path) -> dict[str, Any]:
    contract = load_contract(path)
    return {
        "schema_version": 1,
        "identity_id": contract.identity_id,
        "definition_digest": contract.contract_digest,
        "state": "selected-not-active",
        "runtime_enabled": False,
        "provider_verified": False,
        "secret_values_embedded": False,
    }


def verify_app(app: dict[str, Any], contract: Contract, app_id: int) -> None:
    owner = app.get("owner") or {}
    if app.get("id") != app_id:
        raise IdentityError("provider app identity does not match the requested app")
    if (
        owner.get("type") != contract.repository_owner_type
        or owner.get("id") != contract.repository_owner_id
        or str(owner.get("login") or "").casefold()
        != contract.repository_owner.casefold()
    ):
        raise IdentityError("provider app owner does not match the identity contract")


def verify_installation(
    installation: dict[str, Any],
    contract: Contract,
    app_id: int,
    installation_id: int,
) -> None:
    account = installation.get("account") or {}
    if installation.get("id") != installation_id or installation.get("app_id") != app_id:
        raise IdentityError("provider installation identity does not match")
    if installation.get("suspended_at") is not None:
        raise IdentityError("provider installation is suspended")
    if installation.get("repository_selection") != "selected":
        raise IdentityError("provider installation must select repositories explicitly")
    if installation.get("permissions") != contract.required_permissions:
        raise IdentityError("provider installation permissions do not match the contract")
    if installation.get("events") not in (None, []):
        raise IdentityError("provider installation must not subscribe to events")
    if (
        account.get("type") != contract.repository_owner_type
        or account.get("id") != contract.repository_owner_id
        or str(account.get("login") or "").casefold()
        != contract.repository_owner.casefold()
    ):
        raise IdentityError("provider installation owner does not match the contract")


def validated_token(
    args: argparse.Namespace, contract: Contract
) -> tuple[ProviderClient, IssuedToken, ProviderRepository]:
    if args.app_id <= 0 or args.installation_id <= 0:
        raise IdentityError("app id and installation id must be positive integers")
    client = ProviderClient(
        args.provider_api_base_url or contract.api_base_url,
        sandbox=args.sandbox,
    )
    app_jwt = create_app_jwt(args.app_id, args.private_key_file)
    verify_app(client.authenticated_app(app_jwt), contract, args.app_id)
    verify_installation(
        client.installation(args.installation_id, app_jwt),
        contract,
        args.app_id,
        args.installation_id,
    )
    repository_name = contract.repository.split("/", 1)[1]
    token = client.issue_token(
        args.installation_id,
        app_jwt,
        [repository_name],
        contract.required_permissions,
    )
    try:
        repositories = verify_token(
            token,
            client.accessible_repositories(token.token),
            validate_repositories([contract.repository], contract.maximum_repository_count),
            contract,
        )
        repository = repositories[0]
        if repository.provider_repository_id != contract.repository_id:
            raise IdentityError("provider repository id does not match the contract")
    except Exception:
        try:
            client.revoke_token(token.token)
        except IdentityError:
            pass
        raise
    return client, token, repository


def binding_digest(
    contract: Contract,
    app_id: int,
    installation_id: int,
    repository: ProviderRepository,
) -> str:
    value = {
        "app_id": app_id,
        "contract_digest": contract.contract_digest,
        "identity_id": contract.identity_id,
        "installation_id": installation_id,
        "permissions": contract.required_permissions,
        "repository": {
            "full_name": repository.full_name,
            "provider_repository_id": repository.provider_repository_id,
        },
        "security_gate": contract.security_gate,
    }
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def parse_source_revisions(values: list[str]) -> dict[str, str]:
    revisions: dict[str, str] = {}
    for value in values:
        repository, separator, revision = value.partition("=")
        if (
            not separator
            or not repository
            or repository in revisions
            or not SOURCE_REVISION_PATTERN.fullmatch(revision)
        ):
            raise IdentityError(
                "source revisions must be unique repository=40-character-sha entries"
            )
        revisions[repository] = revision
    if not revisions:
        raise IdentityError("at least one reviewed source revision is required")
    return dict(sorted(revisions.items()))


def receipt(
    contract: Contract,
    *,
    action: str,
    app_id: int,
    installation_id: int,
    repository: ProviderRepository,
    outcome: str,
    source_revisions: dict[str, str],
    caller_id: str,
    expires_at: str | None = None,
    target: DevIntegrationTarget | None = None,
    rollback_receipt_ref: str | None = None,
) -> dict[str, Any]:
    recorded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "workspace-intake-identity-receipt",
        "identity_id": contract.identity_id,
        "definition_digest": contract.contract_digest,
        "source_revisions": source_revisions,
        "security_receipt_ref": contract.security_gate,
        "rollback_receipt_ref": rollback_receipt_ref,
        "caller_id": caller_id,
        "action": action,
        "outcome": outcome,
        "provider": "github",
        "app_id": app_id,
        "installation_id": installation_id,
        "repository_id": repository.provider_repository_id,
        "repository_owner_id": contract.repository_owner_id,
        "permissions": contract.required_permissions,
        "credential_binding_digest": binding_digest(
            contract, app_id, installation_id, repository
        ),
        "issued_at": recorded_at if expires_at is not None else None,
        "expires_at": expires_at,
        "recorded_at": recorded_at,
        "secret_values_embedded": False,
    }
    if target is not None:
        payload.update(
            {
                "profile_id": target.profile_id,
                "session_ref": target.session_id,
                "execution_ref": f"kubernetes://{target.namespace}/{BROKER_DEPLOYMENT}",
            }
        )
    return payload


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(payload, handle, sort_keys=True, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.chmod(0o600)
    temporary.replace(path)


def secret_manifest(
    contract: Contract,
    token: IssuedToken,
    digest: str,
    target: DevIntegrationTarget,
) -> str:
    value = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": contract.runtime_secret_name,
            "namespace": target.namespace,
            "labels": {
                "app.kubernetes.io/component": "workspace-intake-identity",
                "app.kubernetes.io/managed-by": "platform-engineering",
            },
            "annotations": {
                "workspace-governance/credential-binding-digest": digest,
                "workspace-governance/dev-integration-profile": target.profile_id,
                "workspace-governance/dev-integration-session": target.session_id,
                "workspace-governance/token-expires-at": token.expires_at,
            },
        },
        "type": "Opaque",
        "stringData": {contract.runtime_secret_key: token.token},
    }
    return yaml.safe_dump(value, sort_keys=False)


def deployment_patch(contract: Contract) -> str:
    value = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": BROKER_DEPLOYMENT,
                            "env": [
                                {
                                    "name": contract.token_file_env,
                                    "value": f"{contract.runtime_directory}/{contract.runtime_filename}",
                                },
                                {
                                    "name": contract.repository_owner_env,
                                    "value": contract.repository_owner,
                                },
                                {
                                    "name": contract.repository_id_env,
                                    "value": str(contract.repository_id),
                                },
                            ],
                            "volumeMounts": [
                                {
                                    "name": "workspace-intake-identity",
                                    "mountPath": contract.runtime_directory,
                                    "readOnly": True,
                                }
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "workspace-intake-identity",
                            "secret": {
                                "secretName": contract.runtime_secret_name,
                                "items": [
                                    {
                                        "key": contract.runtime_secret_key,
                                        "path": contract.runtime_filename,
                                    }
                                ],
                            },
                        }
                    ],
                }
            }
        }
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def deployment_revoke_patch(contract: Contract) -> str:
    value = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": BROKER_DEPLOYMENT,
                            "env": [
                                {"name": contract.token_file_env, "$patch": "delete"},
                                {"name": contract.repository_owner_env, "$patch": "delete"},
                                {"name": contract.repository_id_env, "$patch": "delete"},
                            ],
                            "volumeMounts": [
                                {"name": "workspace-intake-identity", "$patch": "delete"}
                            ],
                        }
                    ],
                    "volumes": [
                        {"name": "workspace-intake-identity", "$patch": "delete"}
                    ],
                }
            }
        }
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def command_validate(args: argparse.Namespace) -> int:
    print(json.dumps({"valid": True, **validate_definition(args.contract)}, sort_keys=True))
    return 0


def command_commission(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    source_revisions = parse_source_revisions(args.source_revision)
    client, token, repository = validated_token(args, contract)
    client.revoke_token(token.token)
    write_receipt(
        args.receipt,
        receipt(
            contract,
            action="commission",
            app_id=args.app_id,
            installation_id=args.installation_id,
            repository=repository,
            outcome="verified-and-proof-token-revoked",
            source_revisions=source_revisions,
            caller_id=args.caller_id,
            expires_at=token.expires_at,
        ),
    )
    print(f"workspace intake identity verified; receipt={args.receipt}")
    return 0


def command_deliver(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    source_revisions = parse_source_revisions(args.source_revision)
    verify_kubectl_command(args.kubectl, sandbox=args.sandbox)
    target = verify_dev_integration_cluster(
        args.kubectl,
        load_dev_integration_target(
            args.session_manifest, args.workspace_root, contract, require_running=True
        ),
    )
    client, token, repository = validated_token(args, contract)
    digest = binding_digest(contract, args.app_id, args.installation_id, repository)
    projected = False
    try:
        run_kubectl(
            args.kubectl,
            ["apply", "-f", "-"],
            input_text=secret_manifest(contract, token, digest, target),
        )
        projected = True
        run_kubectl(
            args.kubectl,
            [
                "-n",
                target.namespace,
                "patch",
                "deployment",
                BROKER_DEPLOYMENT,
                "--type=strategic",
                "-p",
                deployment_patch(contract),
            ],
        )
        run_kubectl(
            args.kubectl,
            [
                "-n",
                target.namespace,
                "rollout",
                "status",
                f"deployment/{BROKER_DEPLOYMENT}",
                "--timeout=180s",
            ],
        )
        write_receipt(
            args.receipt,
            receipt(
                contract,
                action="deliver",
                app_id=args.app_id,
                installation_id=args.installation_id,
                repository=repository,
                outcome="delivered",
                source_revisions=source_revisions,
                caller_id=args.caller_id,
                expires_at=token.expires_at,
                target=target,
            ),
        )
    except Exception:
        try:
            client.revoke_token(token.token)
        finally:
            if projected:
                try:
                    run_kubectl(
                        args.kubectl,
                        [
                            "-n",
                            target.namespace,
                            "delete",
                            "secret",
                            contract.runtime_secret_name,
                            "--ignore-not-found",
                        ],
                    )
                except IdentityError:
                    pass
        raise
    print(
        f"workspace intake identity delivered; namespace={target.namespace} "
        f"receipt={args.receipt}"
    )
    return 0


def command_revoke(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    source_revisions = parse_source_revisions(args.source_revision)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", args.rollback_receipt_ref):
        raise IdentityError("rollback receipt reference must be a sha256 digest")
    verify_kubectl_command(args.kubectl, sandbox=args.sandbox)
    target = verify_dev_integration_cluster(
        args.kubectl,
        load_dev_integration_target(
            args.session_manifest, args.workspace_root, contract, require_running=False
        ),
    )
    result = run_kubectl(
        args.kubectl,
        ["-n", target.namespace, "get", "secret", contract.runtime_secret_name, "-o", "json"],
    )
    try:
        secret = json.loads(result.stdout)
        token = base64.b64decode(
            secret["data"][contract.runtime_secret_key], validate=True
        ).decode()
        annotations = secret["metadata"]["annotations"]
        projected_digest = annotations["workspace-governance/credential-binding-digest"]
        projected_profile = annotations["workspace-governance/dev-integration-profile"]
        projected_session = annotations["workspace-governance/dev-integration-session"]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise IdentityError("runtime Workspace Intake credential projection is invalid") from None
    repository = ProviderRepository(contract.repository, contract.repository_id)
    expected_digest = binding_digest(contract, args.app_id, args.installation_id, repository)
    if (
        not token
        or projected_digest != expected_digest
        or projected_profile != target.profile_id
        or projected_session != target.session_id
    ):
        raise IdentityError("runtime Workspace Intake credential binding does not match")
    client = ProviderClient(
        args.provider_api_base_url or contract.api_base_url,
        sandbox=args.sandbox,
    )
    outcome = "revoked"
    try:
        client.revoke_token(token)
    except IdentityError as exc:
        if "HTTP 401" not in str(exc) and "HTTP 404" not in str(exc):
            raise
        outcome = "already-revoked"
    run_kubectl(
        args.kubectl,
        [
            "-n",
            target.namespace,
            "patch",
            "deployment",
            BROKER_DEPLOYMENT,
            "--type=strategic",
            "-p",
            deployment_revoke_patch(contract),
        ],
    )
    run_kubectl(
        args.kubectl,
        [
            "-n",
            target.namespace,
            "rollout",
            "status",
            f"deployment/{BROKER_DEPLOYMENT}",
            "--timeout=180s",
        ],
    )
    run_kubectl(
        args.kubectl,
        [
            "-n",
            target.namespace,
            "delete",
            "secret",
            contract.runtime_secret_name,
            "--ignore-not-found",
        ],
    )
    write_receipt(
        args.receipt,
        receipt(
            contract,
            action="revoke",
            app_id=args.app_id,
            installation_id=args.installation_id,
            repository=repository,
            outcome=outcome,
            source_revisions=source_revisions,
            caller_id=args.caller_id,
            target=target,
            rollback_receipt_ref=args.rollback_receipt_ref,
        ),
    )
    print(f"workspace intake identity revoked; receipt={args.receipt}")
    return 0


def add_identity_arguments(parser: argparse.ArgumentParser, *, private_key: bool = True) -> None:
    parser.add_argument("--app-id", type=int, required=True)
    parser.add_argument("--installation-id", type=int, required=True)
    if private_key:
        parser.add_argument("--private-key-file", type=Path, required=True)
    parser.add_argument("--provider-api-base-url")
    parser.add_argument("--sandbox", action="store_true")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--caller-id", required=True, type=lambda value: value.strip())
    parser.add_argument(
        "--source-revision",
        action="append",
        default=[],
        metavar="REPOSITORY=SHA",
        help="reviewed source revision; repeat for each source repository",
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    commands = root.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate the stable source definition")
    validate.set_defaults(handler=command_validate)
    commission = commands.add_parser(
        "commission", help="verify the exact installation and revoke its proof token"
    )
    add_identity_arguments(commission)
    commission.set_defaults(handler=command_commission)
    deliver = commands.add_parser(
        "deliver", help="deliver one short-lived token to the admitted OOS runtime"
    )
    add_identity_arguments(deliver)
    deliver.add_argument("--session-manifest", type=Path, required=True)
    deliver.add_argument("--workspace-root", type=Path, required=True)
    deliver.add_argument("--kubectl", default="k3s kubectl")
    deliver.set_defaults(handler=command_deliver)
    revoke = commands.add_parser(
        "revoke", help="revoke the token and remove its runtime projection"
    )
    add_identity_arguments(revoke, private_key=False)
    revoke.add_argument("--session-manifest", type=Path, required=True)
    revoke.add_argument("--workspace-root", type=Path, required=True)
    revoke.add_argument("--kubectl", default="k3s kubectl")
    revoke.add_argument("--rollback-receipt-ref", required=True)
    revoke.set_defaults(handler=command_revoke)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.handler(args)
    except (
        IdentityError,
        FileNotFoundError,
        KeyError,
        OSError,
        ValueError,
        yaml.YAMLError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"workspace intake identity failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
