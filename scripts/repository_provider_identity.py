#!/usr/bin/env python3
"""Commission and deliver a bounded GitHub App installation identity."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib import error, parse, request

import yaml


DEFAULT_CONTRACT = Path(__file__).resolve().parents[1] / "security/repository-provider-identity.yaml"
GITHUB_API_VERSION = "2022-11-28"
MIN_REMAINING_TOKEN_SECONDS = 300


class IdentityError(RuntimeError):
    pass


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise IdentityError("provider redirect denied")


@dataclass(frozen=True)
class Contract:
    identity_id: str
    contract_digest: str
    api_base_url: str
    maximum_repository_count: int
    maximum_token_lifetime_seconds: int
    runtime_secret_name: str
    runtime_secret_key: str
    required_permissions: dict[str, str]
    allowed_dev_integration_profiles: tuple[str, ...]


@dataclass(frozen=True)
class IssuedToken:
    token: str
    expires_at: str
    repositories: tuple[dict[str, Any], ...]
    permissions: dict[str, str]


@dataclass(frozen=True)
class ProviderRepository:
    full_name: str
    provider_repository_id: int


@dataclass(frozen=True)
class DevIntegrationTarget:
    profile_id: str
    session_id: str
    namespace: str
    cluster_server: str


def load_contract(path: Path) -> Contract:
    source = path.read_bytes()
    payload = yaml.safe_load(source)
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise IdentityError("identity contract must use schema_version 1")
    identity = payload.get("identity") or {}
    custody = payload.get("secret_custody") or {}
    projection = custody.get("runtime_projection") or {}
    consumer = payload.get("consumer") or {}
    permissions = identity.get("required_permissions")
    if permissions != {"metadata": "read"}:
        raise IdentityError("identity contract must require only Metadata: read")
    if identity.get("provider") != "github":
        raise IdentityError("identity contract provider must be github")
    if identity.get("credential_kind") != "github-app-installation":
        raise IdentityError("identity contract must use a GitHub App installation")
    if identity.get("repository_scope") != "explicit-per-token":
        raise IdentityError("identity contract must require explicit per-token repository scope")
    if identity.get("allowed_runtime_lane") != "dev-integration":
        raise IdentityError("identity contract must remain limited to dev-integration")
    api_base_url = str(identity.get("api_base_url") or "").rstrip("/")
    if api_base_url != "https://api.github.com":
        raise IdentityError("normal provider destination must be pinned to https://api.github.com")
    if projection.get("value_in_source_allowed") is not False:
        raise IdentityError("runtime token values must be denied in source")
    if projection.get("value_in_receipts_allowed") is not False:
        raise IdentityError("runtime token values must be denied in receipts")
    activation = payload.get("activation") or {}
    if activation.get("normal_runtime_enabled") is not False:
        raise IdentityError("normal runtime activation must remain disabled until all gates close")
    allowed_profiles = consumer.get("allowed_dev_integration_profiles")
    if allowed_profiles != ["accepted-idea-delivery"]:
        raise IdentityError(
            "repository provider identity must target only accepted-idea-delivery"
        )
    return Contract(
        identity_id=str(identity["id"]),
        contract_digest=f"sha256:{hashlib.sha256(source).hexdigest()}",
        api_base_url=api_base_url,
        maximum_repository_count=int(identity["maximum_repository_count"]),
        maximum_token_lifetime_seconds=int(identity["maximum_token_lifetime_seconds"]),
        runtime_secret_name=str(projection["name"]),
        runtime_secret_key=str(projection["key"]),
        required_permissions=dict(permissions),
        allowed_dev_integration_profiles=tuple(allowed_profiles),
    )


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _private_key(path: Path) -> bytes:
    if path.is_symlink():
        raise IdentityError("private key path must not be a symlink")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise IdentityError("private key path must be a regular file")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise IdentityError("private key file permissions must be 0600 or stricter")
    value = path.read_bytes()
    if b"PRIVATE KEY" not in value:
        raise IdentityError("private key file does not contain a PEM private key")
    return value


def create_app_jwt(app_id: int, private_key_path: Path, now: int | None = None) -> str:
    _private_key(private_key_path)
    issued_at = int(now or time.time()) - 60
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = _b64url(
        json.dumps(
            {"iat": issued_at, "exp": issued_at + 540, "iss": str(app_id)},
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{claims}".encode("ascii")
    result = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", str(private_key_path)],
        input=signing_input,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise IdentityError("failed to sign GitHub App JWT")
    return f"{header}.{claims}.{_b64url(result.stdout)}"


class ProviderClient:
    def __init__(self, api_base_url: str, *, sandbox: bool = False) -> None:
        normalized = api_base_url.rstrip("/")
        parsed = parse.urlparse(normalized)
        if sandbox:
            if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
                raise IdentityError("sandbox provider destination must be loopback HTTP")
        elif normalized != "https://api.github.com":
            raise IdentityError("provider destination must be pinned to https://api.github.com")
        self.api_base_url = normalized
        self.opener = request.build_opener(NoRedirect())

    def call(
        self,
        method: str,
        path: str,
        *,
        bearer: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        encoded = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        req = request.Request(
            f"{self.api_base_url}{path}",
            data=encoded,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {bearer}",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
                "Content-Type": "application/json",
                "User-Agent": "platform-repository-provider-identity/1",
            },
        )
        try:
            with self.opener.open(req, timeout=15) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise IdentityError("provider response exceeded 2 MB")
                if not raw:
                    return None
                return json.loads(raw)
        except IdentityError:
            raise
        except error.HTTPError as exc:
            raise IdentityError(f"provider request failed with HTTP {exc.code}") from None
        except (error.URLError, TimeoutError, json.JSONDecodeError):
            raise IdentityError("provider request failed or returned invalid JSON") from None

    def installation(self, installation_id: int, app_jwt: str) -> dict[str, Any]:
        value = self.call("GET", f"/app/installations/{installation_id}", bearer=app_jwt)
        if not isinstance(value, dict):
            raise IdentityError("provider installation readback is invalid")
        return value

    def issue_token(
        self,
        installation_id: int,
        app_jwt: str,
        repositories: list[str],
        permissions: dict[str, str],
    ) -> IssuedToken:
        value = self.call(
            "POST",
            f"/app/installations/{installation_id}/access_tokens",
            bearer=app_jwt,
            body={"repositories": repositories, "permissions": permissions},
        )
        if not isinstance(value, dict) or not isinstance(value.get("token"), str):
            raise IdentityError("provider token response is invalid")
        return IssuedToken(
            token=value["token"],
            expires_at=str(value.get("expires_at") or ""),
            repositories=tuple(value.get("repositories") or ()),
            permissions=dict(value.get("permissions") or {}),
        )

    def accessible_repositories(self, installation_token: str) -> tuple[dict[str, Any], ...]:
        value = self.call(
            "GET",
            "/installation/repositories?per_page=100",
            bearer=installation_token,
        )
        if not isinstance(value, dict) or not isinstance(value.get("repositories"), list):
            raise IdentityError("provider repository-scope readback is invalid")
        if value.get("total_count") != len(value["repositories"]):
            raise IdentityError("provider repository-scope readback is incomplete")
        return tuple(value["repositories"])

    def revoke_token(self, installation_token: str) -> None:
        self.call("DELETE", "/installation/token", bearer=installation_token)


def parse_repository(value: str) -> tuple[str, str]:
    parts = value.strip().split("/")
    if len(parts) != 2 or not all(parts):
        raise IdentityError(f"repository must use owner/name: {value!r}")
    return parts[0], parts[1]


def validate_repositories(values: list[str], maximum: int) -> list[str]:
    normalized = sorted({f"{owner}/{name}" for owner, name in map(parse_repository, values)})
    if not normalized:
        raise IdentityError("at least one repository is required")
    if len(normalized) != len(values):
        raise IdentityError("repository scope contains duplicates")
    if len(normalized) > maximum:
        raise IdentityError(f"repository scope exceeds maximum of {maximum}")
    owners = {value.split("/", 1)[0].casefold() for value in normalized}
    if len(owners) != 1:
        raise IdentityError("one installation-token request must target repositories under one owner")
    return normalized


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", value.lower())
    return re.sub(r"-{2,}", "-", normalized).strip("-") or "devint"


def load_yaml_object(path: Path, description: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        raise IdentityError(f"{description} is unavailable or invalid") from None
    if not isinstance(value, dict):
        raise IdentityError(f"{description} must be an object")
    return value


def owner_file(root: Path, relative: str, description: str) -> Path:
    configured = Path(relative)
    if configured.is_absolute():
        raise IdentityError(f"{description} must be owner-relative")
    try:
        resolved = (root / configured).resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError):
        raise IdentityError(f"{description} is unavailable or escapes its owner repo") from None
    if not resolved.is_file():
        raise IdentityError(f"{description} must be a file")
    return resolved


def load_dev_integration_target(
    session_manifest: Path,
    workspace_root: Path,
    contract: Contract,
    *,
    require_running: bool,
) -> DevIntegrationTarget:
    if session_manifest.is_symlink():
        raise IdentityError("dev-integration session manifest must not be a symlink")
    try:
        info = session_manifest.stat()
    except OSError:
        raise IdentityError("dev-integration session manifest is unavailable") from None
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise IdentityError("dev-integration session manifest must be an operator-owned file")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise IdentityError("dev-integration session manifest permissions must be 0600 or stricter")

    manifest = load_yaml_object(session_manifest, "dev-integration session manifest")
    profile_id = manifest.get("profile_id")
    operator = manifest.get("operator")
    session_id = manifest.get("session_id")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("lane") != "dev-integration"
        or manifest.get("profile_lifecycle") != "active"
        or manifest.get("runtime_owner") != "platform-engineering"
        or not isinstance(profile_id, str)
        or profile_id not in contract.allowed_dev_integration_profiles
        or not isinstance(operator, str)
        or not operator
        or not isinstance(session_id, str)
        or not session_id
    ):
        raise IdentityError("dev-integration session manifest is not an allowed active target")
    if require_running and manifest.get("action") in {"down", "reset"}:
        raise IdentityError("dev-integration session is not running")

    expected_manifest = (
        workspace_root
        / ".dev-integration"
        / slugify(profile_id)
        / slugify(operator)
        / "current-session.yaml"
    )
    if session_manifest.resolve() != expected_manifest.resolve():
        raise IdentityError("dev-integration session manifest is not the runner-owned current session")

    governance_root = workspace_root / "workspace-governance"
    registry = load_yaml_object(
        governance_root / "contracts/developer-integration-profiles.yaml",
        "dev-integration profile registry",
    )
    entry = (registry.get("profiles") or {}).get(profile_id)
    if (
        not isinstance(entry, dict)
        or entry.get("lifecycle") != "active"
        or entry.get("owner_repo") != "operator-orchestration-service"
        or entry.get("runtime_owner") != "platform-engineering"
    ):
        raise IdentityError("dev-integration profile registry does not authorize this target")
    owner_root = workspace_root / str(entry["owner_repo"])
    profile_path = owner_file(owner_root, str(entry.get("profile_path") or ""), "profile")
    profile = load_yaml_object(profile_path, "dev-integration profile")
    if profile.get("profile_id") != profile_id:
        raise IdentityError("dev-integration profile identity does not match the registry")
    namespace_pattern = (profile.get("runtime") or {}).get(
        "namespace_pattern",
        "devint-{profile}-{operator}",
    )
    if not isinstance(namespace_pattern, str):
        raise IdentityError("dev-integration namespace pattern is invalid")
    try:
        expected_namespace = slugify(
            namespace_pattern.format(profile=profile_id, operator=operator)
        )[:63]
    except (KeyError, ValueError):
        raise IdentityError("dev-integration namespace pattern is invalid") from None
    namespace = manifest.get("namespace")
    if namespace != expected_namespace or not expected_namespace.startswith("devint-"):
        raise IdentityError("dev-integration session namespace does not match the active profile")
    return DevIntegrationTarget(
        profile_id=profile_id,
        session_id=session_id,
        namespace=namespace,
        cluster_server="",
    )


def parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise IdentityError("provider token expiry is invalid") from None
    if parsed.tzinfo is None:
        raise IdentityError("provider token expiry must include a timezone")
    return parsed.astimezone(timezone.utc)


def verify_installation(
    installation: dict[str, Any],
    *,
    app_id: int,
    installation_id: int,
    required_permissions: dict[str, str],
) -> None:
    if installation.get("id") != installation_id or installation.get("app_id") != app_id:
        raise IdentityError("provider installation identity does not match requested app and installation")
    if installation.get("suspended_at") is not None:
        raise IdentityError("provider installation is suspended")
    if installation.get("repository_selection") != "selected":
        raise IdentityError("provider installation must use selected repositories")
    if installation.get("permissions") != required_permissions:
        raise IdentityError("provider installation permissions must be exactly Metadata: read")
    if installation.get("events") not in (None, []):
        raise IdentityError("provider installation must not subscribe to events")


def verify_token(
    token: IssuedToken,
    accessible: tuple[dict[str, Any], ...],
    repositories: list[str],
    contract: Contract,
) -> tuple[ProviderRepository, ...]:
    if token.permissions != contract.required_permissions:
        raise IdentityError("issued token permissions exceed the contract")
    expires_at = parse_timestamp(token.expires_at)
    remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
    if remaining < MIN_REMAINING_TOKEN_SECONDS:
        raise IdentityError("issued token is expired or too close to expiry")
    if remaining > contract.maximum_token_lifetime_seconds + 60:
        raise IdentityError("issued token lifetime exceeds the contract")
    observed = sorted(str(item.get("full_name") or "") for item in accessible)
    if observed != repositories:
        raise IdentityError("issued token repository scope does not match the request")
    if any(not isinstance(item.get("id"), int) or item["id"] <= 0 for item in accessible):
        raise IdentityError("provider repository readback is missing immutable numeric identity")
    return tuple(
        ProviderRepository(
            full_name=str(item["full_name"]),
            provider_repository_id=int(item["id"]),
        )
        for item in sorted(accessible, key=lambda item: str(item["full_name"]))
    )


def binding_digest(
    contract: Contract,
    app_id: int,
    installation_id: int,
    repositories: tuple[ProviderRepository, ...],
) -> str:
    value = {
        "app_id": app_id,
        "identity_id": contract.identity_id,
        "contract_digest": contract.contract_digest,
        "installation_id": installation_id,
        "permissions": contract.required_permissions,
        "provider_api_base_url": contract.api_base_url,
        "repositories": [
            {
                "full_name": repository.full_name,
                "provider_repository_id": repository.provider_repository_id,
            }
            for repository in repositories
        ],
    }
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def provider_repository_payload(
    repositories: tuple[ProviderRepository, ...],
) -> list[dict[str, str | int]]:
    return [
        {
            "full_name": repository.full_name,
            "provider_repository_id": repository.provider_repository_id,
        }
        for repository in repositories
    ]


def parse_provider_repositories(value: str) -> tuple[ProviderRepository, ...]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        raise IdentityError("runtime repository identity annotation is invalid") from None
    if not isinstance(payload, list) or not payload:
        raise IdentityError("runtime repository identity annotation must be a non-empty list")
    repositories: list[ProviderRepository] = []
    for item in payload:
        if not isinstance(item, dict):
            raise IdentityError("runtime repository identity annotation is invalid")
        full_name = item.get("full_name")
        provider_repository_id = item.get("provider_repository_id")
        if not isinstance(full_name, str):
            raise IdentityError("runtime repository identity annotation is missing a repository name")
        parse_repository(full_name)
        if not isinstance(provider_repository_id, int) or provider_repository_id <= 0:
            raise IdentityError("runtime repository identity annotation is missing an immutable id")
        repositories.append(ProviderRepository(full_name, provider_repository_id))
    ordered = tuple(sorted(repositories, key=lambda repository: repository.full_name))
    if len({repository.full_name for repository in ordered}) != len(ordered):
        raise IdentityError("runtime repository identity annotation contains duplicates")
    return ordered


def receipt(
    contract: Contract,
    *,
    action: str,
    app_id: int,
    installation_id: int,
    repositories: tuple[ProviderRepository, ...],
    outcome: str,
    expires_at: str | None = None,
    target: DevIntegrationTarget | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "artifact_type": "repository-provider-identity-receipt",
        "identity_id": contract.identity_id,
        "contract_digest": contract.contract_digest,
        "action": action,
        "outcome": outcome,
        "provider": "github",
        "provider_api_base_url": contract.api_base_url,
        "app_id": app_id,
        "installation_id": installation_id,
        "repositories": [repository.full_name for repository in repositories],
        "provider_repositories": provider_repository_payload(repositories),
        "permissions": contract.required_permissions,
        "credential_binding_digest": binding_digest(
            contract, app_id, installation_id, repositories
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
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def validated_token(
    args: argparse.Namespace,
    contract: Contract,
) -> tuple[ProviderClient, IssuedToken, tuple[ProviderRepository, ...]]:
    if args.app_id <= 0 or args.installation_id <= 0:
        raise IdentityError("app id and installation id must be positive integers")
    repositories = validate_repositories(args.repository, contract.maximum_repository_count)
    client = ProviderClient(args.provider_api_base_url or contract.api_base_url, sandbox=args.sandbox)
    app_jwt = create_app_jwt(args.app_id, args.private_key_file)
    installation = client.installation(args.installation_id, app_jwt)
    verify_installation(
        installation,
        app_id=args.app_id,
        installation_id=args.installation_id,
        required_permissions=contract.required_permissions,
    )
    names = [value.split("/", 1)[1] for value in repositories]
    token = client.issue_token(
        args.installation_id,
        app_jwt,
        names,
        contract.required_permissions,
    )
    try:
        accessible = client.accessible_repositories(token.token)
        provider_repositories = verify_token(token, accessible, repositories, contract)
    except Exception:
        try:
            client.revoke_token(token.token)
        except IdentityError:
            pass
        raise
    return client, token, provider_repositories


def run_kubectl(kubectl: str, arguments: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    executable = shlex.split(kubectl)
    if not executable:
        raise IdentityError("kubectl command is empty")
    result = subprocess.run(
        [*executable, *arguments],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise IdentityError("Kubernetes credential projection failed")
    return result


def verify_kubectl_command(kubectl: str, *, sandbox: bool) -> None:
    if not sandbox and shlex.split(kubectl) != ["k3s", "kubectl"]:
        raise IdentityError("normal delivery requires the platform-owned k3s kubectl command")


def verify_dev_integration_cluster(
    kubectl: str,
    target: DevIntegrationTarget,
) -> DevIntegrationTarget:
    config_result = run_kubectl(
        kubectl,
        ["config", "view", "--minify", "-o", "json"],
    )
    try:
        config = json.loads(config_result.stdout)
        clusters = config["clusters"]
        server = clusters[0]["cluster"]["server"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise IdentityError("Kubernetes target configuration is invalid") from None
    parsed_server = parse.urlparse(server)
    if (
        len(clusters) != 1
        or parsed_server.scheme != "https"
        or parsed_server.hostname not in {"127.0.0.1", "localhost", "::1"}
    ):
        raise IdentityError("repository provider delivery requires the local dev-integration cluster")
    namespace_result = run_kubectl(
        kubectl,
        ["get", "namespace", target.namespace, "-o", "json"],
    )
    try:
        namespace = json.loads(namespace_result.stdout)
        namespace_name = namespace["metadata"]["name"]
        phase = namespace["status"]["phase"]
    except (KeyError, TypeError, json.JSONDecodeError):
        raise IdentityError("dev-integration namespace readback is invalid") from None
    if namespace_name != target.namespace or phase != "Active":
        raise IdentityError("dev-integration namespace is not active")
    return DevIntegrationTarget(
        profile_id=target.profile_id,
        session_id=target.session_id,
        namespace=target.namespace,
        cluster_server=server,
    )


def secret_manifest(
    contract: Contract,
    token: IssuedToken,
    repositories: tuple[ProviderRepository, ...],
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
                "app.kubernetes.io/component": "repository-provider-identity",
                "app.kubernetes.io/managed-by": "platform-engineering",
            },
            "annotations": {
                "workspace-governance/credential-binding-digest": digest,
                "workspace-governance/provider-repositories": json.dumps(
                    provider_repository_payload(repositories),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
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
    print(f"repository provider identity contract valid: {contract.identity_id}")
    return 0


def command_commission(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    client, token, repositories = validated_token(args, contract)
    client.revoke_token(token.token)
    payload = receipt(
        contract,
        action="commission",
        app_id=args.app_id,
        installation_id=args.installation_id,
        repositories=repositories,
        outcome="verified-and-proof-token-revoked",
        expires_at=token.expires_at,
    )
    write_receipt(args.receipt, payload)
    print(f"provider identity verified; receipt={args.receipt}")
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
    client, token, repositories = validated_token(args, contract)
    digest = binding_digest(contract, args.app_id, args.installation_id, repositories)
    projected = False
    try:
        run_kubectl(
            args.kubectl,
            ["apply", "-f", "-"],
            input_text=secret_manifest(
                contract,
                token,
                repositories,
                digest,
                target,
            ),
        )
        projected = True
        payload = receipt(
            contract,
            action="deliver",
            app_id=args.app_id,
            installation_id=args.installation_id,
            repositories=repositories,
            outcome="delivered",
            expires_at=token.expires_at,
            target=target,
        )
        write_receipt(args.receipt, payload)
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
        f"provider identity delivered; namespace={target.namespace} "
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
        [
            "-n",
            target.namespace,
            "get",
            "secret",
            contract.runtime_secret_name,
            "-o",
            "json",
        ],
    )
    try:
        projected_secret = json.loads(secret_result.stdout)
        token_value = projected_secret["data"][contract.runtime_secret_key]
        annotations = projected_secret["metadata"]["annotations"]
        installation_token = base64.b64decode(token_value, validate=True).decode("utf-8")
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise IdentityError("runtime credential projection is invalid") from None
    if not installation_token:
        raise IdentityError("runtime credential projection is empty")
    try:
        repositories = parse_provider_repositories(
            annotations["workspace-governance/provider-repositories"]
        )
        projected_digest = annotations["workspace-governance/credential-binding-digest"]
        projected_profile = annotations["workspace-governance/dev-integration-profile"]
        projected_session = annotations["workspace-governance/dev-integration-session"]
    except (KeyError, TypeError):
        raise IdentityError("runtime credential binding annotations are missing") from None
    requested_repositories = validate_repositories(
        args.repository,
        contract.maximum_repository_count,
    )
    if [repository.full_name for repository in repositories] != requested_repositories:
        raise IdentityError("runtime repository identities do not match the revocation request")
    if projected_profile != target.profile_id or projected_session != target.session_id:
        raise IdentityError("runtime credential projection does not match the dev-integration session")
    expected_digest = binding_digest(
        contract,
        args.app_id,
        args.installation_id,
        repositories,
    )
    if projected_digest != expected_digest:
        raise IdentityError("runtime credential binding digest does not match")
    client = ProviderClient(args.provider_api_base_url or contract.api_base_url, sandbox=args.sandbox)
    provider_outcome = "revoked"
    try:
        client.revoke_token(installation_token)
    except IdentityError as exc:
        if "HTTP 401" not in str(exc) and "HTTP 404" not in str(exc):
            raise
        provider_outcome = "already-revoked"
    run_kubectl(
        args.kubectl,
        ["-n", target.namespace, "delete", "secret", contract.runtime_secret_name, "--ignore-not-found"],
    )
    payload = receipt(
        contract,
        action="revoke",
        app_id=args.app_id,
        installation_id=args.installation_id,
        repositories=repositories,
        outcome=provider_outcome,
        target=target,
    )
    write_receipt(args.receipt, payload)
    print(f"provider identity revoked; receipt={args.receipt}")
    return 0


def add_identity_arguments(parser: argparse.ArgumentParser, *, private_key: bool = True) -> None:
    parser.add_argument("--app-id", type=int, required=True)
    parser.add_argument("--installation-id", type=int, required=True)
    parser.add_argument("--repository", action="append", required=True)
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
        print(f"repository provider identity failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
