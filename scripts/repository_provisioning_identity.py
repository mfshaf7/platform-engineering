#!/usr/bin/env python3
"""Commission and deliver the bounded repository-provisioning GitHub App identity."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

import yaml

from repository_provider_identity import (
    DevIntegrationTarget,
    IdentityError,
    IssuedToken,
    ProviderClient,
    create_app_jwt,
    load_dev_integration_target,
    parse_timestamp,
    run_kubectl,
    verify_dev_integration_cluster,
    verify_kubectl_command,
)


DEFAULT_CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "security/repository-provisioning-identity.yaml"
)
MIN_REMAINING_TOKEN_SECONDS = 300


@dataclass(frozen=True)
class Contract:
    identity_id: str
    contract_digest: str
    api_base_url: str
    maximum_token_lifetime_seconds: int
    runtime_secret_name: str
    runtime_secret_key: str
    required_permissions: dict[str, str]
    allowed_dev_integration_profiles: tuple[str, ...]


def load_contract(path: Path) -> Contract:
    source = path.read_bytes()
    payload = yaml.safe_load(source)
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise IdentityError("provisioning identity contract must use schema_version 1")
    identity = payload.get("identity") or {}
    projection = ((payload.get("secret_custody") or {}).get("runtime_projection") or {})
    consumer = payload.get("consumer") or {}
    permissions = identity.get("required_permissions")
    if permissions != {
        "administration": "write",
        "contents": "read",
        "metadata": "read",
    }:
        raise IdentityError(
            "provisioning identity must require exactly Administration: write, "
            "Contents: read, and implicit Metadata: read"
        )
    if identity.get("provider") != "github":
        raise IdentityError("provisioning identity provider must be github")
    if identity.get("credential_kind") != "github-app-installation":
        raise IdentityError("provisioning identity must use a GitHub App installation")
    if identity.get("owner_scope") != "exact-organization-per-delivery":
        raise IdentityError("provisioning identity must bind one exact organization per delivery")
    if identity.get("allowed_runtime_lane") != "dev-integration":
        raise IdentityError("provisioning identity must remain limited to dev-integration")
    api_base_url = str(identity.get("api_base_url") or "").rstrip("/")
    if api_base_url != "https://api.github.com":
        raise IdentityError("normal provider destination must be pinned to https://api.github.com")
    if projection.get("value_in_source_allowed") is not False:
        raise IdentityError("runtime token values must be denied in source")
    if projection.get("value_in_receipts_allowed") is not False:
        raise IdentityError("runtime token values must be denied in receipts")
    activation = payload.get("activation") or {}
    if activation.get("bounded_evidence_enabled") is not True:
        raise IdentityError("bounded provisioning evidence must be enabled")
    if activation.get("normal_runtime_enabled") is not False:
        raise IdentityError("normal runtime activation must remain disabled until Console proof")
    allowed_profiles = consumer.get("allowed_dev_integration_profiles")
    if allowed_profiles != ["accepted-idea-delivery"]:
        raise IdentityError("provisioning identity must target only accepted-idea-delivery")
    return Contract(
        identity_id=str(identity["id"]),
        contract_digest=f"sha256:{hashlib.sha256(source).hexdigest()}",
        api_base_url=api_base_url,
        maximum_token_lifetime_seconds=int(identity["maximum_token_lifetime_seconds"]),
        runtime_secret_name=str(projection["name"]),
        runtime_secret_key=str(projection["key"]),
        required_permissions=dict(permissions),
        allowed_dev_integration_profiles=tuple(allowed_profiles),
    )


def verify_installation(
    installation: dict[str, Any],
    *,
    app_id: int,
    installation_id: int,
    organization: str,
    required_permissions: dict[str, str],
) -> None:
    account = installation.get("account") or {}
    if installation.get("id") != installation_id or installation.get("app_id") != app_id:
        raise IdentityError("provider installation identity does not match requested app and installation")
    if installation.get("suspended_at") is not None:
        raise IdentityError("provider installation is suspended")
    if account.get("type") != "Organization" or str(account.get("login") or "").casefold() != organization.casefold():
        raise IdentityError("provider installation is not bound to the requested organization")
    if installation.get("permissions") != required_permissions:
        raise IdentityError("provider installation permissions exceed the provisioning contract")
    if installation.get("events") not in (None, []):
        raise IdentityError("provider installation must not subscribe to events")


def verify_token(token: IssuedToken, contract: Contract) -> None:
    if token.permissions != contract.required_permissions:
        raise IdentityError("issued token permissions exceed the provisioning contract")
    remaining = (parse_timestamp(token.expires_at) - datetime.now(timezone.utc)).total_seconds()
    if remaining < MIN_REMAINING_TOKEN_SECONDS:
        raise IdentityError("issued token is expired or too close to expiry")
    if remaining > contract.maximum_token_lifetime_seconds + 60:
        raise IdentityError("issued token lifetime exceeds the contract")


def binding_digest(
    contract: Contract,
    app_id: int,
    installation_id: int,
    organization: str,
) -> str:
    value = {
        "app_id": app_id,
        "identity_id": contract.identity_id,
        "contract_digest": contract.contract_digest,
        "installation_id": installation_id,
        "organization": organization.casefold(),
        "permissions": contract.required_permissions,
        "provider_api_base_url": contract.api_base_url,
    }
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def validated_token(
    args: argparse.Namespace,
    contract: Contract,
) -> tuple[ProviderClient, IssuedToken]:
    if args.app_id <= 0 or args.installation_id <= 0:
        raise IdentityError("app id and installation id must be positive integers")
    if not args.organization.strip() or "/" in args.organization:
        raise IdentityError("organization must be one GitHub organization login")
    client = ProviderClient(args.provider_api_base_url or contract.api_base_url, sandbox=args.sandbox)
    app_jwt = create_app_jwt(args.app_id, args.private_key_file)
    installation = client.installation(args.installation_id, app_jwt)
    verify_installation(
        installation,
        app_id=args.app_id,
        installation_id=args.installation_id,
        organization=args.organization,
        required_permissions=contract.required_permissions,
    )
    token = client.issue_token(
        args.installation_id,
        app_jwt,
        None,
        contract.required_permissions,
    )
    try:
        verify_token(token, contract)
    except Exception:
        try:
            client.revoke_token(token.token)
        except IdentityError:
            pass
        raise
    return client, token


def receipt(
    contract: Contract,
    *,
    action: str,
    app_id: int,
    installation_id: int,
    organization: str,
    outcome: str,
    expires_at: str | None = None,
    target: DevIntegrationTarget | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "repository-provisioning-identity-receipt",
        "identity_id": contract.identity_id,
        "contract_digest": contract.contract_digest,
        "action": action,
        "outcome": outcome,
        "provider": "github",
        "provider_api_base_url": contract.api_base_url,
        "app_id": app_id,
        "installation_id": installation_id,
        "organization": organization,
        "permissions": contract.required_permissions,
        "credential_binding_digest": binding_digest(
            contract, app_id, installation_id, organization
        ),
        "token_expires_at": expires_at,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "secret_values_embedded": False,
    }
    if target is not None:
        payload["runtime_target"] = {
            "lane": "dev-integration",
            "profile_id": target.profile_id,
            "session_id": target.session_id,
            "namespace": target.namespace,
            "cluster_server": target.cluster_server,
        }
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
    organization: str,
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
                "app.kubernetes.io/component": "repository-provisioning-identity",
                "app.kubernetes.io/managed-by": "platform-engineering",
            },
            "annotations": {
                "workspace-governance/credential-binding-digest": digest,
                "workspace-governance/provider-organization": organization,
                "workspace-governance/dev-integration-profile": target.profile_id,
                "workspace-governance/dev-integration-session": target.session_id,
                "workspace-governance/token-expires-at": token.expires_at,
            },
        },
        "type": "Opaque",
        "stringData": {contract.runtime_secret_key: token.token},
    }
    return yaml.safe_dump(value, sort_keys=False)


def command_validate(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    print(f"repository provisioning identity contract valid: {contract.identity_id}")
    return 0


def command_commission(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    client, token = validated_token(args, contract)
    client.revoke_token(token.token)
    write_receipt(
        args.receipt,
        receipt(
            contract,
            action="commission",
            app_id=args.app_id,
            installation_id=args.installation_id,
            organization=args.organization,
            outcome="verified-and-proof-token-revoked",
            expires_at=token.expires_at,
        ),
    )
    print(f"provisioning identity verified; receipt={args.receipt}")
    return 0


def command_deliver(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    verify_kubectl_command(args.kubectl, sandbox=args.sandbox)
    target = verify_dev_integration_cluster(
        args.kubectl,
        load_dev_integration_target(
            args.session_manifest,
            args.workspace_root,
            contract,
            require_running=True,
        ),
    )
    client, token = validated_token(args, contract)
    digest = binding_digest(contract, args.app_id, args.installation_id, args.organization)
    projected = False
    try:
        run_kubectl(
            args.kubectl,
            ["apply", "-f", "-"],
            input_text=secret_manifest(
                contract, token, args.organization, digest, target
            ),
        )
        projected = True
        write_receipt(
            args.receipt,
            receipt(
                contract,
                action="deliver",
                app_id=args.app_id,
                installation_id=args.installation_id,
                organization=args.organization,
                outcome="delivered",
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
        f"provisioning identity delivered; namespace={target.namespace} "
        f"secret={contract.runtime_secret_name} receipt={args.receipt}"
    )
    return 0


def command_revoke(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    verify_kubectl_command(args.kubectl, sandbox=args.sandbox)
    target = verify_dev_integration_cluster(
        args.kubectl,
        load_dev_integration_target(
            args.session_manifest,
            args.workspace_root,
            contract,
            require_running=False,
        ),
    )
    secret_result = run_kubectl(
        args.kubectl,
        ["-n", target.namespace, "get", "secret", contract.runtime_secret_name, "-o", "json"],
    )
    try:
        secret = json.loads(secret_result.stdout)
        token = base64.b64decode(
            secret["data"][contract.runtime_secret_key], validate=True
        ).decode("utf-8")
        annotations = secret["metadata"]["annotations"]
        projected_organization = annotations["workspace-governance/provider-organization"]
        projected_digest = annotations["workspace-governance/credential-binding-digest"]
        projected_profile = annotations["workspace-governance/dev-integration-profile"]
        projected_session = annotations["workspace-governance/dev-integration-session"]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise IdentityError("runtime provisioning credential projection is invalid") from None
    expected_digest = binding_digest(
        contract, args.app_id, args.installation_id, args.organization
    )
    if (
        not token
        or projected_organization.casefold() != args.organization.casefold()
        or projected_digest != expected_digest
        or projected_profile != target.profile_id
        or projected_session != target.session_id
    ):
        raise IdentityError("runtime provisioning credential binding does not match")
    client = ProviderClient(args.provider_api_base_url or contract.api_base_url, sandbox=args.sandbox)
    outcome = "revoked"
    try:
        client.revoke_token(token)
    except IdentityError as exc:
        if "HTTP 401" not in str(exc) and "HTTP 404" not in str(exc):
            raise
        outcome = "already-revoked"
    run_kubectl(
        args.kubectl,
        ["-n", target.namespace, "delete", "secret", contract.runtime_secret_name, "--ignore-not-found"],
    )
    write_receipt(
        args.receipt,
        receipt(
            contract,
            action="revoke",
            app_id=args.app_id,
            installation_id=args.installation_id,
            organization=args.organization,
            outcome=outcome,
            target=target,
        ),
    )
    print(f"provisioning identity revoked; receipt={args.receipt}")
    return 0


def add_identity_arguments(parser: argparse.ArgumentParser, *, private_key: bool = True) -> None:
    parser.add_argument("--app-id", type=int, required=True)
    parser.add_argument("--installation-id", type=int, required=True)
    parser.add_argument("--organization", required=True)
    if private_key:
        parser.add_argument("--private-key-file", type=Path, required=True)
    parser.add_argument("--provider-api-base-url")
    parser.add_argument("--sandbox", action="store_true")
    parser.add_argument("--receipt", type=Path, required=True)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    commands = root.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate the source contract")
    validate.set_defaults(handler=command_validate)
    commission = commands.add_parser("commission", help="verify identity and revoke the proof token")
    add_identity_arguments(commission)
    commission.set_defaults(handler=command_commission)
    deliver = commands.add_parser("deliver", help="deliver an exact short-lived token to Kubernetes")
    add_identity_arguments(deliver)
    deliver.add_argument("--session-manifest", type=Path, required=True)
    deliver.add_argument("--workspace-root", type=Path, required=True)
    deliver.add_argument("--kubectl", default="k3s kubectl")
    deliver.set_defaults(handler=command_deliver)
    revoke = commands.add_parser("revoke", help="revoke the token and remove its projection")
    add_identity_arguments(revoke, private_key=False)
    revoke.add_argument("--session-manifest", type=Path, required=True)
    revoke.add_argument("--workspace-root", type=Path, required=True)
    revoke.add_argument("--kubectl", default="k3s kubectl")
    revoke.set_defaults(handler=command_revoke)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.handler(args)
    except (IdentityError, FileNotFoundError, KeyError, subprocess.SubprocessError) as exc:
        print(f"repository provisioning identity failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
