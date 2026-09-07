#!/usr/bin/env python3
"""Commission and project the bounded Prototype Landing runtime identity."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any
from urllib import parse

from jsonschema import Draft202012Validator
import yaml

from repository_provider_identity import (
    DevIntegrationTarget,
    IdentityError,
    IssuedToken,
    ProviderClient,
    ProviderRepository,
    load_dev_integration_target,
    run_kubectl,
    verify_dev_integration_cluster,
    verify_kubectl_command,
)
from workspace_intake_identity import (
    Contract as ExactRepositoryContract,
    binding_digest as exact_repository_binding_digest,
    parse_source_revisions,
    validated_token as validated_exact_repository_token,
    write_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "security/prototype-landing-identity.yaml"
SCHEMA = ROOT / "security/schemas/prototype-landing-identity.schema.json"
SOURCE_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Contract(ExactRepositoryContract):
    broker_deployment: str
    runtime_profile: str
    wgcf_secret_key: str
    state_root_env: str
    state_mount_path: str
    authority_root_env: str
    authority_mount_path: str
    python_env: str
    python_command: str
    runtime_profile_env: str
    wgcf_base_url_env: str
    wgcf_caller_id_env: str
    wgcf_caller_id: str
    wgcf_caller_secret_env: str
    wgcf_implementation_ref_env: str
    wgcf_implementation_ref: str
    wgcf_service_identity_ref_env: str
    wgcf_service_identity_ref: str
    source_authority_minimum_revision: str
    workflow_runtime_enabled: bool


@dataclass(frozen=True)
class RuntimeInputs:
    authority_root: Path
    state_root: Path
    wgcf_base_url: str
    wgcf_caller_secret: str


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
            "Prototype Landing identity definition violates its source contract at "
            + ", ".join(paths)
        )
    return source, definition


def load_contract(path: Path) -> Contract:
    source, definition = _load_definition(path)
    identity = definition["identity"]
    repository = identity["repository"]
    projection = definition["secret_custody"]["runtime_projection"]
    consumer = definition["consumer"]
    activation = definition["activation"]
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
        runtime_secret_key=projection["token_key"],
        runtime_directory=projection["directory"],
        runtime_filename=projection["token_filename"],
        token_file_env=consumer["token_file_env"],
        repository_owner_env=consumer["repository_owner_env"],
        repository_id_env=consumer["repository_id_env"],
        allowed_dev_integration_profiles=tuple(consumer["allowed_profiles"]),
        security_gate=activation["security_gate"],
        broker_deployment=consumer["broker_deployment"],
        runtime_profile=consumer["runtime_profile"],
        wgcf_secret_key=projection["wgcf_caller_secret_key"],
        state_root_env=consumer["state_root_env"],
        state_mount_path=consumer["state_mount_path"],
        authority_root_env=consumer["authority_root_env"],
        authority_mount_path=consumer["authority_mount_path"],
        python_env=consumer["python_env"],
        python_command=consumer["python_command"],
        runtime_profile_env=consumer["runtime_profile_env"],
        wgcf_base_url_env=consumer["wgcf_base_url_env"],
        wgcf_caller_id_env=consumer["wgcf_caller_id_env"],
        wgcf_caller_id=consumer["wgcf_caller_id"],
        wgcf_caller_secret_env=consumer["wgcf_caller_secret_env"],
        wgcf_implementation_ref_env=consumer["wgcf_implementation_ref_env"],
        wgcf_implementation_ref=consumer["wgcf_implementation_ref"],
        wgcf_service_identity_ref_env=consumer["wgcf_service_identity_ref_env"],
        wgcf_service_identity_ref=consumer["wgcf_service_identity_ref"],
        source_authority_minimum_revision=activation[
            "source_authority_minimum_revision"
        ],
        workflow_runtime_enabled=activation["workflow_runtime_enabled"],
    )


def validate_definition(path: Path) -> dict[str, Any]:
    contract = load_contract(path)
    return {
        "schema_version": 1,
        "identity_id": contract.identity_id,
        "definition_digest": contract.contract_digest,
        "state": "selected-not-active",
        "identity_projection_enabled": False,
        "workflow_runtime_enabled": contract.workflow_runtime_enabled,
        "provider_verified": False,
        "secret_values_embedded": False,
    }


def _read_secret(path: Path, label: str) -> str:
    if path.is_symlink():
        raise IdentityError(f"{label} path must not be a symlink")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
        raise IdentityError(f"{label} file permissions must be 0600 or stricter")
    value = path.read_text().strip()
    if not value or "\n" in value or "\r" in value:
        raise IdentityError(f"{label} is invalid")
    return value


def _git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise IdentityError("Prototype Studio source authority is unavailable")
    return result.stdout.strip()


def _runtime_inputs(args: argparse.Namespace, contract: Contract) -> RuntimeInputs:
    authority_root = (args.workspace_root / "workspace-prototype-studio").resolve()
    expected_root = args.workspace_root.resolve()
    if authority_root.parent != expected_root or not (authority_root / ".git").exists():
        raise IdentityError("Prototype Studio authority root is invalid")
    remote_main = _git(authority_root, "rev-parse", "refs/remotes/origin/main")
    if not SOURCE_REVISION_PATTERN.fullmatch(remote_main):
        raise IdentityError("Prototype Studio origin/main revision is invalid")
    _git(
        authority_root,
        "merge-base",
        "--is-ancestor",
        contract.source_authority_minimum_revision,
        remote_main,
    )

    state_root = (args.session_manifest.parent / "prototype-landing" / "state").resolve()
    session_root = args.session_manifest.parent.resolve()
    if state_root.parent.parent != session_root:
        raise IdentityError("Prototype Landing state root escapes the profile session")
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_root.chmod(0o700)

    endpoint = parse.urlparse(args.wgcf_base_url)
    allowed_cluster_host = (
        endpoint.hostname is not None
        and endpoint.hostname.startswith("workspace-governance-control-fabric-api.")
        and endpoint.hostname.endswith(".svc.cluster.local")
    )
    allowed_sandbox_host = args.sandbox and endpoint.hostname in {
        "127.0.0.1",
        "localhost",
        "::1",
    }
    if endpoint.scheme != "http" or endpoint.query or endpoint.fragment or not (
        allowed_cluster_host or allowed_sandbox_host
    ):
        raise IdentityError("WGCF Prototype Landing destination is not admitted")

    return RuntimeInputs(
        authority_root=authority_root,
        state_root=state_root,
        wgcf_base_url=args.wgcf_base_url.rstrip("/"),
        wgcf_caller_secret=_read_secret(
            args.wgcf_caller_secret_file, "WGCF caller secret"
        ),
    )


def runtime_binding_digest(
    contract: Contract, target: DevIntegrationTarget, runtime: RuntimeInputs
) -> str:
    value = {
        "contract_digest": contract.contract_digest,
        "profile_id": target.profile_id,
        "session_id": target.session_id,
        "namespace": target.namespace,
        "authority_revision": _git(
            runtime.authority_root, "rev-parse", "refs/remotes/origin/main"
        ),
        "wgcf_base_url": runtime.wgcf_base_url,
        "wgcf_implementation_ref": contract.wgcf_implementation_ref,
        "wgcf_service_identity_ref": contract.wgcf_service_identity_ref,
    }
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


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
    runtime_binding: str | None = None,
    rollback_receipt_ref: str | None = None,
    workflow_runtime_enabled: bool = False,
) -> dict[str, Any]:
    recorded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "prototype-landing-identity-receipt",
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
        "credential_binding_digest": exact_repository_binding_digest(
            contract, app_id, installation_id, repository
        ),
        "runtime_binding_digest": runtime_binding,
        "issued_at": recorded_at if expires_at is not None else None,
        "expires_at": expires_at,
        "recorded_at": recorded_at,
        "workflow_runtime_enabled": workflow_runtime_enabled,
        "secret_values_embedded": False,
    }
    if target is not None:
        payload.update(
            {
                "profile_id": target.profile_id,
                "session_ref": target.session_id,
                "execution_ref": (
                    f"kubernetes://{target.namespace}/{contract.broker_deployment}"
                ),
            }
        )
    return payload


def secret_manifest(
    contract: Contract,
    token: IssuedToken,
    repository: ProviderRepository,
    credential_digest: str,
    runtime_digest: str,
    target: DevIntegrationTarget,
    wgcf_caller_secret: str,
) -> str:
    value = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": contract.runtime_secret_name,
            "namespace": target.namespace,
            "labels": {
                "app.kubernetes.io/component": "prototype-landing-identity",
                "app.kubernetes.io/managed-by": "platform-engineering",
            },
            "annotations": {
                "workspace-governance/credential-binding-digest": credential_digest,
                "workspace-governance/runtime-binding-digest": runtime_digest,
                "workspace-governance/provider-repository": repository.full_name,
                "workspace-governance/dev-integration-profile": target.profile_id,
                "workspace-governance/dev-integration-session": target.session_id,
                "workspace-governance/token-expires-at": token.expires_at,
            },
        },
        "type": "Opaque",
        "stringData": {
            contract.runtime_secret_key: token.token,
            contract.wgcf_secret_key: wgcf_caller_secret,
        },
    }
    return yaml.safe_dump(value, sort_keys=False)


def _env(name: str, value: str) -> dict[str, str]:
    return {"name": name, "value": value}


def deployment_patch(contract: Contract, runtime: RuntimeInputs) -> str:
    credential_volume = "prototype-landing-identity"
    state_volume = "prototype-landing-state"
    authority_volume = "prototype-landing-authority"
    env: list[dict[str, Any]] = [
        _env(
            "OOS_PROTOTYPE_LANDING_ENABLED",
            str(contract.workflow_runtime_enabled).lower(),
        ),
        _env(contract.runtime_profile_env, contract.runtime_profile),
        _env(
            contract.token_file_env,
            f"{contract.runtime_directory}/{contract.runtime_filename}",
        ),
        _env(contract.repository_owner_env, contract.repository_owner),
        _env(contract.repository_id_env, str(contract.repository_id)),
        _env(contract.state_root_env, contract.state_mount_path),
        _env(contract.authority_root_env, contract.authority_mount_path),
        _env(contract.python_env, contract.python_command),
        _env(contract.wgcf_base_url_env, runtime.wgcf_base_url),
        _env(contract.wgcf_caller_id_env, contract.wgcf_caller_id),
        {
            "name": contract.wgcf_caller_secret_env,
            "valueFrom": {
                "secretKeyRef": {
                    "name": contract.runtime_secret_name,
                    "key": contract.wgcf_secret_key,
                }
            },
        },
        _env(
            contract.wgcf_implementation_ref_env, contract.wgcf_implementation_ref
        ),
        _env(
            contract.wgcf_service_identity_ref_env,
            contract.wgcf_service_identity_ref,
        ),
    ]
    value = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": contract.broker_deployment,
                            "env": env,
                            "volumeMounts": [
                                {
                                    "name": credential_volume,
                                    "mountPath": contract.runtime_directory,
                                    "readOnly": True,
                                },
                                {
                                    "name": state_volume,
                                    "mountPath": contract.state_mount_path,
                                },
                                {
                                    "name": authority_volume,
                                    "mountPath": contract.authority_mount_path,
                                    "readOnly": True,
                                },
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": credential_volume,
                            "secret": {
                                "secretName": contract.runtime_secret_name,
                                "items": [
                                    {
                                        "key": contract.runtime_secret_key,
                                        "path": contract.runtime_filename,
                                    }
                                ],
                            },
                        },
                        {
                            "name": state_volume,
                            "hostPath": {
                                "path": str(runtime.state_root),
                                "type": "Directory",
                            },
                        },
                        {
                            "name": authority_volume,
                            "hostPath": {
                                "path": str(runtime.authority_root),
                                "type": "Directory",
                            },
                        },
                    ],
                }
            }
        }
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def deployment_revoke_patch(contract: Contract) -> str:
    env_names = [
        "OOS_PROTOTYPE_LANDING_ENABLED",
        contract.runtime_profile_env,
        contract.token_file_env,
        contract.repository_owner_env,
        contract.repository_id_env,
        contract.state_root_env,
        contract.authority_root_env,
        contract.python_env,
        contract.wgcf_base_url_env,
        contract.wgcf_caller_id_env,
        contract.wgcf_caller_secret_env,
        contract.wgcf_implementation_ref_env,
        contract.wgcf_service_identity_ref_env,
    ]
    volume_names = [
        "prototype-landing-identity",
        "prototype-landing-state",
        "prototype-landing-authority",
    ]
    volume_mounts = [
        ("prototype-landing-identity", contract.runtime_directory),
        ("prototype-landing-state", contract.state_mount_path),
        ("prototype-landing-authority", contract.authority_mount_path),
    ]
    value = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": contract.broker_deployment,
                            "env": [
                                {"name": name, "$patch": "delete"}
                                for name in env_names
                            ],
                            "volumeMounts": [
                                {
                                    "name": name,
                                    "mountPath": mount_path,
                                    "$patch": "delete",
                                }
                                for name, mount_path in volume_mounts
                            ],
                        }
                    ],
                    "volumes": [
                        {"name": name, "$patch": "delete"}
                        for name in volume_names
                    ],
                }
            }
        }
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def deployment_suspend_patch(contract: Contract) -> str:
    value = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": contract.broker_deployment,
                            "env": [
                                _env("OOS_PROTOTYPE_LANDING_ENABLED", "false")
                            ],
                        }
                    ]
                }
            }
        }
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def projected_runtime_token(
    kubectl: str,
    contract: Contract,
    target: DevIntegrationTarget,
    *,
    app_id: int,
    installation_id: int,
    allow_missing: bool,
    allow_prior_session: bool = False,
) -> str | None:
    result = run_kubectl(
        kubectl,
        [
            "-n",
            target.namespace,
            "get",
            "secret",
            contract.runtime_secret_name,
            "--ignore-not-found",
            "-o",
            "json",
        ],
    )
    if not result.stdout.strip() and allow_missing:
        return None
    try:
        secret = json.loads(result.stdout)
        token = base64.b64decode(
            secret["data"][contract.runtime_secret_key], validate=True
        ).decode()
        annotations = secret["metadata"]["annotations"]
        projected_digest = annotations[
            "workspace-governance/credential-binding-digest"
        ]
        projected_profile = annotations[
            "workspace-governance/dev-integration-profile"
        ]
        projected_session = annotations[
            "workspace-governance/dev-integration-session"
        ]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise IdentityError(
            "runtime Prototype Landing credential projection is invalid"
        ) from None
    repository = ProviderRepository(contract.repository, contract.repository_id)
    expected_digest = exact_repository_binding_digest(
        contract, app_id, installation_id, repository
    )
    if (
        not token
        or projected_digest != expected_digest
        or projected_profile != target.profile_id
        or (
            projected_session != target.session_id
            and not allow_prior_session
        )
    ):
        raise IdentityError("runtime Prototype Landing credential binding does not match")
    return token


def remove_runtime_projection(
    kubectl: str, contract: Contract, target: DevIntegrationTarget
) -> None:
    run_kubectl(
        kubectl,
        [
            "-n",
            target.namespace,
            "patch",
            "deployment",
            contract.broker_deployment,
            "--type=strategic",
            "-p",
            deployment_revoke_patch(contract),
        ],
    )
    run_kubectl(
        kubectl,
        [
            "-n",
            target.namespace,
            "rollout",
            "status",
            f"deployment/{contract.broker_deployment}",
            "--timeout=180s",
        ],
    )
    run_kubectl(
        kubectl,
        [
            "-n",
            target.namespace,
            "delete",
            "secret",
            contract.runtime_secret_name,
            "--ignore-not-found",
        ],
    )


def command_validate(args: argparse.Namespace) -> int:
    print(json.dumps({"valid": True, **validate_definition(args.contract)}, sort_keys=True))
    return 0


def command_commission(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    source_revisions = parse_source_revisions(args.source_revision)
    client, token, repository = validated_exact_repository_token(args, contract)
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
    print(f"Prototype Landing identity verified; receipt={args.receipt}")
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
    runtime = _runtime_inputs(args, contract)
    previous_token = projected_runtime_token(
        args.kubectl,
        contract,
        target,
        app_id=args.app_id,
        installation_id=args.installation_id,
        allow_missing=True,
        allow_prior_session=True,
    )
    client, token, repository = validated_exact_repository_token(args, contract)
    if previous_token == token.token:
        client.revoke_token(token.token)
        raise IdentityError("provider returned the currently projected token during rotation")
    credential_digest = exact_repository_binding_digest(
        contract, args.app_id, args.installation_id, repository
    )
    runtime_digest = runtime_binding_digest(contract, target, runtime)
    projected = False
    try:
        run_kubectl(
            args.kubectl,
            [
                "apply",
                "--server-side",
                "--field-manager=platform-prototype-landing",
                "-f",
                "-",
            ],
            input_text=secret_manifest(
                contract,
                token,
                repository,
                credential_digest,
                runtime_digest,
                target,
                runtime.wgcf_caller_secret,
            ),
        )
        projected = True
        run_kubectl(
            args.kubectl,
            [
                "-n",
                target.namespace,
                "patch",
                "deployment",
                contract.broker_deployment,
                "--type=strategic",
                "-p",
                deployment_patch(contract, runtime),
            ],
        )
        run_kubectl(
            args.kubectl,
            [
                "-n",
                target.namespace,
                "rollout",
                "status",
                f"deployment/{contract.broker_deployment}",
                "--timeout=180s",
            ],
        )
        if previous_token is not None:
            try:
                client.revoke_token(previous_token)
            except IdentityError as exc:
                if "HTTP 401" not in str(exc) and "HTTP 404" not in str(exc):
                    raise
        write_receipt(
            args.receipt,
            receipt(
                contract,
                action="deliver",
                app_id=args.app_id,
                installation_id=args.installation_id,
                repository=repository,
                outcome="identity-projected-workflow-enabled",
                source_revisions=source_revisions,
                caller_id=args.caller_id,
                expires_at=token.expires_at,
                target=target,
                runtime_binding=runtime_digest,
                workflow_runtime_enabled=contract.workflow_runtime_enabled,
            ),
        )
    except Exception:
        try:
            client.revoke_token(token.token)
        finally:
            if previous_token is not None and previous_token != token.token:
                try:
                    client.revoke_token(previous_token)
                except IdentityError:
                    pass
            if projected:
                try:
                    remove_runtime_projection(args.kubectl, contract, target)
                except IdentityError:
                    pass
        raise
    print(
        f"Prototype Landing identity projected; namespace={target.namespace} "
        f"workflow=enabled receipt={args.receipt}"
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
    token = projected_runtime_token(
        args.kubectl,
        contract,
        target,
        app_id=args.app_id,
        installation_id=args.installation_id,
        allow_missing=False,
    )
    assert token is not None
    repository = ProviderRepository(contract.repository, contract.repository_id)
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
    remove_runtime_projection(args.kubectl, contract, target)
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
    print(f"Prototype Landing identity revoked; receipt={args.receipt}")
    return 0


def command_suspend(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    source_revisions = parse_source_revisions(args.source_revision)
    verify_kubectl_command(args.kubectl, sandbox=args.sandbox)
    target = verify_dev_integration_cluster(
        args.kubectl,
        load_dev_integration_target(
            args.session_manifest, args.workspace_root, contract, require_running=True
        ),
    )
    token = projected_runtime_token(
        args.kubectl,
        contract,
        target,
        app_id=args.app_id,
        installation_id=args.installation_id,
        allow_missing=False,
    )
    assert token is not None
    run_kubectl(
        args.kubectl,
        [
            "-n",
            target.namespace,
            "patch",
            "deployment",
            contract.broker_deployment,
            "--type=strategic",
            "-p",
            deployment_suspend_patch(contract),
        ],
    )
    run_kubectl(
        args.kubectl,
        [
            "-n",
            target.namespace,
            "rollout",
            "status",
            f"deployment/{contract.broker_deployment}",
            "--timeout=180s",
        ],
    )
    repository = ProviderRepository(contract.repository, contract.repository_id)
    write_receipt(
        args.receipt,
        receipt(
            contract,
            action="suspend",
            app_id=args.app_id,
            installation_id=args.installation_id,
            repository=repository,
            outcome="new-requests-suspended",
            source_revisions=source_revisions,
            caller_id=args.caller_id,
            target=target,
        ),
    )
    print(f"Prototype Landing workflow suspended; receipt={args.receipt}")
    return 0


def add_identity_arguments(
    command: argparse.ArgumentParser, *, private_key: bool = True
) -> None:
    command.add_argument("--app-id", type=int, required=True)
    command.add_argument("--installation-id", type=int, required=True)
    if private_key:
        command.add_argument("--private-key-file", type=Path, required=True)
    command.add_argument("--provider-api-base-url")
    command.add_argument("--sandbox", action="store_true")
    command.add_argument("--receipt", type=Path, required=True)
    command.add_argument("--caller-id", required=True, type=lambda value: value.strip())
    command.add_argument(
        "--source-revision",
        action="append",
        default=[],
        metavar="REPOSITORY=SHA",
        help="reviewed source revision; repeat for each source repository",
    )


def add_runtime_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--session-manifest", type=Path, required=True)
    command.add_argument("--workspace-root", type=Path, required=True)
    command.add_argument("--kubectl", default="k3s kubectl")


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
        "deliver", help="project one short-lived identity into the admitted OOS runtime"
    )
    add_identity_arguments(deliver)
    add_runtime_arguments(deliver)
    deliver.add_argument("--wgcf-base-url", required=True)
    deliver.add_argument("--wgcf-caller-secret-file", type=Path, required=True)
    deliver.set_defaults(handler=command_deliver)
    suspend = commands.add_parser(
        "suspend", help="stop new Prototype Landing requests while retaining runtime state"
    )
    add_identity_arguments(suspend, private_key=False)
    add_runtime_arguments(suspend)
    suspend.set_defaults(handler=command_suspend)
    revoke = commands.add_parser(
        "revoke", help="revoke the token and remove its runtime projection"
    )
    add_identity_arguments(revoke, private_key=False)
    add_runtime_arguments(revoke)
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
        print(f"Prototype Landing identity failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
