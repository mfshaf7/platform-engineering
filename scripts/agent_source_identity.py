#!/usr/bin/env python3
"""Commission and project the bounded Agent source identity."""

from __future__ import annotations

import argparse
import fcntl
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable, Iterator

from jsonschema import Draft202012Validator
import yaml

from repository_provider_identity import (
    IdentityError,
    IssuedToken,
    ProviderClient,
    ProviderRepository,
    create_app_jwt,
    verify_installation,
    verify_token,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "security/agent-source-identity.yaml"
SCHEMA = ROOT / "security/schemas/agent-source-identity.schema.json"
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
LANDING_UNIT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,127}$")
WORKFLOW_PURPOSE = "workflow-maintenance"


def delivery_purpose(args: argparse.Namespace) -> dict[str, str]:
    purpose = getattr(args, "purpose", "ordinary-source")
    approval = getattr(args, "approval_ref", None)
    if purpose == "ordinary-source" and approval is None:
        return {}
    if purpose != WORKFLOW_PURPOSE or not isinstance(approval, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:/._#-]{2,255}", approval):
        raise IdentityError("workflow maintenance requires its explicit operator approval reference")
    return {"purpose": purpose, "approval_ref": approval}


def purpose_contract(contract: Contract, purpose: dict[str, str]) -> Contract:
    if not purpose:
        return contract
    return replace(contract, required_permissions={**contract.required_permissions, "workflows": "write"})


@dataclass(frozen=True)
class Repository:
    full_name: str
    provider_repository_id: int


@dataclass(frozen=True)
class InstallationAccount:
    login: str
    account_id: int
    account_type: str
    installation_id: int


@dataclass(frozen=True)
class RepositoryInventorySnapshot:
    """Immutable Git content returned by a trusted Platform record reader.

    This is an internal owner interface, never an HTTP input or CLI override.
    The caller owns freshness/ancestry/provider checks; this issuer validates
    the canonical schemas and admission/provider binding before minting.
    """

    inventory: bytes
    inventory_schema: dict[str, Any]
    intake: bytes
    intake_schema: dict[str, Any]
    revision: str
    reviewed_revision: str


@dataclass(frozen=True)
class Contract:
    identity_id: str
    display_name: str
    logical_agent_id: str
    provider_principal: str
    contract_digest: str
    api_base_url: str
    account_login: str
    account_id: int
    account_type: str
    app_slug: str
    app_id: int
    installation_id: int
    installation_accounts: tuple[InstallationAccount, ...]
    installation_account: InstallationAccount
    repositories: tuple[Repository, ...]
    required_permissions: dict[str, str]
    maximum_token_lifetime_seconds: int
    rotate_before_expiry_seconds: int
    canonical_branch: str
    allowed_branch_pattern: str
    git_author_name: str
    git_author_email: str
    human_reviewer_id: str
    repository_inventory_ref: dict[str, Any]
    workspace_contract_ref: dict[str, str]
    security_review_ref: dict[str, str]
    vault_path: str
    vault_property: str
    runtime_root_env: str
    runtime_relative_directory: str
    credential_filename: str
    suspension_filename: str
    lock_filename: str


def _load_definition(path: Path) -> tuple[bytes, dict[str, Any]]:
    source = path.read_bytes()
    definition = yaml.safe_load(source)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(definition),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        detail = "; ".join(
            f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise IdentityError(f"agent source identity definition is invalid: {detail}")
    return source, definition


def load_contract(path: Path) -> Contract:
    source, definition = _load_definition(path)
    identity = definition["identity"]
    source_boundary = definition["source_boundary"]
    authority = definition["authority"]
    custody = definition["secret_custody"]
    private_key = custody["private_key_source"]
    projection = custody["runtime_projection"]
    activation = definition["activation"]
    if activation["normal_runtime_enabled"] is not False:
        raise IdentityError("normal Agent source runtime must remain disabled until work item 1137")
    repositories = tuple(
        Repository(item["full_name"], item["id"])
        for item in identity["repositories"]
    )
    if len({item.full_name for item in repositories}) != len(repositories):
        raise IdentityError("Agent source repositories must be unique")
    return Contract(
        identity_id=identity["id"],
        display_name=identity["display_name"],
        logical_agent_id=identity["logical_agent_id"],
        provider_principal=identity["provider_principal"],
        contract_digest=f"sha256:{hashlib.sha256(source).hexdigest()}",
        api_base_url=identity["api_base_url"],
        account_login=identity["account"]["login"],
        account_id=identity["account"]["id"],
        account_type=identity["account"]["type"],
        app_slug=identity["app"]["slug"],
        app_id=identity["app"]["id"],
        installation_id=identity["app"]["installation_id"],
        installation_accounts=tuple(InstallationAccount(
            item["login"], item["id"], item["type"], item["installation_id"],
        ) for item in identity["installation_accounts"]),
        installation_account=InstallationAccount(
            identity["account"]["login"], identity["account"]["id"],
            identity["account"]["type"], identity["app"]["installation_id"],
        ),
        repositories=repositories,
        required_permissions=dict(identity["required_permissions"]),
        maximum_token_lifetime_seconds=identity["maximum_token_lifetime_seconds"],
        rotate_before_expiry_seconds=identity["rotate_before_expiry_seconds"],
        canonical_branch=source_boundary["canonical_branch"],
        allowed_branch_pattern=source_boundary["allowed_branch_pattern"],
        git_author_name=source_boundary["git_author"]["name"],
        git_author_email=source_boundary["git_author"]["email"],
        human_reviewer_id=source_boundary["human_reviewer_id"],
        repository_inventory_ref=dict(authority["repository_inventory"]),
        workspace_contract_ref=dict(authority["workspace_contract"]),
        security_review_ref=dict(authority["security_review"]),
        vault_path=private_key["path"],
        vault_property=private_key["property"],
        runtime_root_env=projection["root_env"],
        runtime_relative_directory=projection["relative_directory"],
        credential_filename=projection["credential_filename"],
        suspension_filename=projection["suspension_filename"],
        lock_filename=projection["lock_filename"],
    )


def verify_workspace_repository_inventory(contract: Contract, inventory_path: Path) -> None:
    source = inventory_path.read_bytes()
    expected_digest = contract.repository_inventory_ref["digest"]
    observed_digest = f"sha256:{hashlib.sha256(source).hexdigest()}"
    if observed_digest != expected_digest:
        raise IdentityError("Workspace repository inventory digest does not match the Agent source contract")
    inventory = yaml.safe_load(source)
    repositories = inventory.get("repos") if isinstance(inventory, dict) else None
    if not isinstance(repositories, dict):
        raise IdentityError("Workspace repository inventory is invalid")
    lifecycle = contract.repository_inventory_ref["lifecycle"]
    posture = contract.repository_inventory_ref["posture"]
    expected = tuple(
        f"{contract.account_login}/{name}"
        for name, entry in repositories.items()
        if isinstance(entry, dict)
        and entry.get("lifecycle") == lifecycle
        and entry.get("posture") == posture
    )
    observed = tuple(repository.full_name for repository in contract.repositories)
    if observed != expected:
        raise IdentityError("Agent source repository set does not match active Workspace Governance owners")


def workspace_repository_inventory_path(args: argparse.Namespace) -> Path | None:
    configured = getattr(args, "workspace_repo_inventory", None)
    if configured is not None:
        return configured
    workspace_root = os.environ.get("WORKSPACE_ROOT")
    candidates = []
    if workspace_root:
        candidates.append(Path(workspace_root) / "workspace-governance" / "contracts" / "repos.yaml")
    candidates.append(ROOT.parent / "workspace-governance" / "contracts" / "repos.yaml")
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def contract_from_record_snapshot(contract: Contract, snapshot: RepositoryInventorySnapshot) -> Contract:
    if not REVISION_PATTERN.fullmatch(snapshot.revision) or not REVISION_PATTERN.fullmatch(snapshot.reviewed_revision):
        raise IdentityError("canonical inventory source revisions are invalid")
    documents = []
    for source, schema in ((snapshot.inventory, snapshot.inventory_schema), (snapshot.intake, snapshot.intake_schema)):
        if len(source) > 4 * 1024 * 1024:
            raise IdentityError("canonical inventory content exceeds its bound")
        value = yaml.safe_load(source)
        Draft202012Validator.check_schema(schema)
        if not isinstance(value, dict) or not Draft202012Validator(schema).is_valid(value):
            raise IdentityError("canonical inventory or Intake does not match its reviewed schema")
        documents.append(value)
    inventory, intake = documents
    legacy = {item.full_name.split("/", 1)[1]: item for item in contract.repositories}
    repositories = []
    physical_ids: set[int] = set()
    coordinates: set[str] = set()
    for section in ("repos", "retired_repos"):
        for name, entry in inventory.get(section, {}).items():
            binding = entry.get("provider_repository")
            fallback = legacy.get(name)
            if binding is None:
                if fallback is None:
                    continue  # Unbound legacy records are not credential authority.
                repository = fallback
            else:
                if (set(binding) != {"provider", "provider_repository_id", "full_name"}
                    or binding["provider"] != "github"
                    or not re.fullmatch(r"[1-9][0-9]*", str(binding["provider_repository_id"]))
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+", str(binding["full_name"]))):
                    raise IdentityError("canonical repository provider binding is invalid")
                repository = Repository(binding["full_name"], int(binding["provider_repository_id"]))
                if fallback and repository.provider_repository_id != fallback.provider_repository_id:
                    raise IdentityError("canonical repository cannot replace a legacy provider identity")
            folded = repository.full_name.casefold()
            if repository.provider_repository_id in physical_ids or folded in coordinates:
                raise IdentityError("canonical repository provider identity is reused")
            physical_ids.add(repository.provider_repository_id)
            coordinates.add(folded)
            if section != "repos" or entry.get("lifecycle") != "active" or entry.get("posture") != "active":
                continue
            if fallback is None:
                lineage = entry.get("record", {}).get("lineage", {})
                admitted = intake.get("repos", {}).get(name, {})
                if (binding is None or admitted.get("status") != "admitted"
                    or admitted.get("provider_repository") != binding
                    or lineage.get("source") != "workspace-intake"
                    or lineage.get("source_ref") != admitted.get("record", {}).get("id")
                    or type(lineage.get("intake_entry_version")) is not int
                    or type(admitted.get("record", {}).get("version")) is not int
                    or admitted["record"]["version"] < lineage["intake_entry_version"]):
                    raise IdentityError("ordinary source requires the exact admitted Intake and active Inventory binding")
            repositories.append(repository)
    return replace(contract, repositories=tuple(repositories), repository_inventory_ref={
        **contract.repository_inventory_ref, "revision": snapshot.revision,
        "reviewed_revision": snapshot.reviewed_revision,
        "digest": f"sha256:{hashlib.sha256(snapshot.inventory).hexdigest()}",
    })


def select_installation(contract: Contract, repository_name: str) -> Contract:
    owner = repository_name.split("/", 1)[0]
    matches = [item for item in contract.installation_accounts if item.login.casefold() == owner.casefold()]
    if len(matches) != 1:
        raise IdentityError("repository account has no approved source App installation")
    account = matches[0]
    return replace(contract, installation_id=account.installation_id, installation_account=account)


def load_operating_contract(
    args: argparse.Namespace, *, inventory_reader: Callable[[], RepositoryInventorySnapshot] | None = None,
) -> Contract:
    contract = load_contract(args.contract)
    if inventory_reader is not None:
        return contract_from_record_snapshot(contract, inventory_reader())
    inventory_path = workspace_repository_inventory_path(args)
    if inventory_path is None:
        if not getattr(args, "sandbox", False):
            raise IdentityError("Workspace repository inventory is required for Agent source issuance")
    else:
        verify_workspace_repository_inventory(contract, inventory_path)
    return contract


def _run(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise IdentityError(f"{Path(args[0]).name} command failed")
    return result


def _regular_private_file(path: Path) -> None:
    if path.is_symlink():
        raise IdentityError("private key path must not be a symlink")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
        raise IdentityError("private key file must be a regular file with mode 0600 or stricter")
    if b"PRIVATE KEY" not in path.read_bytes():
        raise IdentityError("private key file does not contain PEM private-key material")


def _verify_vault_command(command: str, *, sandbox: bool) -> str:
    parts = command.split()
    if len(parts) != 1:
        raise IdentityError("Vault command must be one executable")
    if not sandbox and parts[0] != "vault":
        raise IdentityError("normal custody requires the platform Vault command")
    return parts[0]


def import_private_key(
    contract: Contract,
    source: Path,
    *,
    vault_command: str,
    sandbox: bool,
) -> None:
    _regular_private_file(source)
    executable = _verify_vault_command(vault_command, sandbox=sandbox)
    _run(
        [
            executable,
            "kv",
            "put",
            "-mount=kv",
            contract.vault_path,
            f"{contract.vault_property}=@{source}",
        ]
    )


@contextmanager
def private_key_file(
    contract: Contract,
    *,
    vault_command: str,
    sandbox: bool,
    sandbox_private_key: Path | None,
) -> Iterator[Path]:
    if sandbox_private_key is not None:
        if not sandbox:
            raise IdentityError("direct private-key files are allowed only in sandbox tests")
        _regular_private_file(sandbox_private_key)
        yield sandbox_private_key
        return
    executable = _verify_vault_command(vault_command, sandbox=sandbox)
    result = _run(
        [
            executable,
            "kv",
            "get",
            "-mount=kv",
            f"-field={contract.vault_property}",
            contract.vault_path,
        ]
    )
    if "PRIVATE KEY" not in result.stdout:
        raise IdentityError("Vault did not return valid private-key material")
    with tempfile.TemporaryDirectory(prefix="agent-source-key-") as directory:
        key_path = Path(directory) / "private-key.pem"
        key_path.write_text(result.stdout, encoding="utf-8")
        os.chmod(key_path, 0o600)
        yield key_path


def provider_client(contract: Contract, args: argparse.Namespace) -> ProviderClient:
    return ProviderClient(args.provider_api_base_url or contract.api_base_url, sandbox=args.sandbox)


def verify_provider_identity(
    contract: Contract,
    client: ProviderClient,
    private_key: Path,
) -> str:
    app_jwt = create_app_jwt(contract.app_id, private_key)
    app = client.authenticated_app(app_jwt)
    owner = app.get("owner") or {}
    if (
        app.get("id") != contract.app_id
        or app.get("slug") != contract.app_slug
        or str(owner.get("login") or "").casefold() != contract.account_login.casefold()
        or owner.get("id") != contract.account_id
        or owner.get("type") != contract.account_type
    ):
        raise IdentityError("provider App identity does not match the Agent source contract")
    installation = client.installation(contract.installation_id, app_jwt)
    # An approved App-level workflow grant must not broaden ordinary tokens.
    # Only this source App may carry that one additional installation permission;
    # the shared read-only provider verifier remains strict and unchanged.
    observed_permissions = installation.get("permissions")
    ordinary_permissions = {key: value for key, value in contract.required_permissions.items() if key != "workflows"}
    if observed_permissions not in (ordinary_permissions, {**ordinary_permissions, "workflows": "write"}):
        raise IdentityError("provider installation permissions exceed the approved source App boundary")
    if "workflows" in contract.required_permissions and observed_permissions != contract.required_permissions:
        raise IdentityError("workflow maintenance permission has not been accepted by the installation")
    verify_installation(
        installation,
        app_id=contract.app_id,
        installation_id=contract.installation_id,
        required_permissions=observed_permissions,
    )
    account = installation.get("account") or {}
    if (
        str(account.get("login") or "").casefold() != contract.installation_account.login.casefold()
        or account.get("id") != contract.installation_account.account_id
        or account.get("type") != contract.installation_account.account_type
    ):
        raise IdentityError("provider installation account does not match the Agent source contract")
    return app_jwt


def expected_repository(contract: Contract, full_name: str) -> Repository:
    matches = [item for item in contract.repositories if item.full_name == full_name]
    if len(matches) != 1:
        raise IdentityError("repository is outside the approved Agent source installation set")
    return matches[0]


def issue_repository_token(
    contract: Contract,
    client: ProviderClient,
    app_jwt: str,
    repository: Repository,
) -> tuple[IssuedToken, ProviderRepository]:
    owner, name = repository.full_name.split("/", 1)
    if owner.casefold() != contract.installation_account.login.casefold():
        raise IdentityError("repository owner does not match the Agent source account")
    token = client.issue_token(
        contract.installation_id,
        app_jwt,
        [name],
        contract.required_permissions,
    )
    adapter = type(
        "TokenContract",
        (),
        {
            "required_permissions": contract.required_permissions,
            "maximum_token_lifetime_seconds": contract.maximum_token_lifetime_seconds,
        },
    )()
    try:
        accessible = client.accessible_repositories(token.token)
        observed = verify_token(token, accessible, [repository.full_name], adapter)
        if len(observed) != 1 or observed[0].provider_repository_id != repository.provider_repository_id:
            raise IdentityError("provider repository id does not match the Agent source contract")
    except Exception:
        try:
            client.revoke_token(token.token)
        except IdentityError:
            pass
        raise
    return token, observed[0]


def runtime_root(contract: Contract, args: argparse.Namespace) -> Path:
    if args.runtime_root is not None:
        if not args.sandbox:
            raise IdentityError("normal runtime projection cannot override its Platform root")
        root = args.runtime_root
    else:
        base = os.environ.get(contract.runtime_root_env)
        if not base or not Path(base).is_absolute():
            raise IdentityError(f"{contract.runtime_root_env} must name an absolute operator runtime directory")
        root = Path(base) / contract.runtime_relative_directory
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or not root.is_dir():
        raise IdentityError("Agent source runtime root must be a real directory")
    os.chmod(root, 0o700)
    return root


@contextmanager
def projection_lock(contract: Contract, root: Path) -> Iterator[None]:
    lock_path = root / contract.lock_filename
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def session_directory(root: Path, landing_unit_id: str) -> Path:
    if not LANDING_UNIT_PATTERN.fullmatch(landing_unit_id):
        raise IdentityError("landing unit id is invalid")
    digest = hashlib.sha256(landing_unit_id.encode("utf-8")).hexdigest()[:24]
    return root / "sessions" / digest


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        temporary.replace(path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_credential(contract: Contract, directory: Path) -> dict[str, Any] | None:
    path = directory / contract.credential_filename
    if not path.exists():
        return None
    if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise IdentityError("runtime credential projection has unsafe file metadata")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise IdentityError("runtime credential projection is invalid") from None
    required = {
        "schema_version",
        "identity_id",
        "logical_agent_id",
        "provider_principal",
        "app_id",
        "installation_id",
        "repository",
        "repository_id",
        "landing_unit_id",
        "branch",
        "fetched_base",
        "human_reviewer_id",
        "token",
        "token_expires_at",
    }
    if isinstance(payload, dict) and payload.get("purpose") == WORKFLOW_PURPOSE:
        required |= {"purpose", "approval_ref"}
        delivery_purpose(argparse.Namespace(purpose=payload.get("purpose"), approval_ref=payload.get("approval_ref")))
    if not isinstance(payload, dict) or set(payload) != required or not payload.get("token"):
        raise IdentityError("runtime credential projection has an invalid shape")
    return payload


def safe_revoke(client: ProviderClient, token: str, *, allow_missing: bool = True) -> str:
    try:
        client.revoke_token(token)
        return "revoked"
    except IdentityError as exc:
        if allow_missing and ("HTTP 401" in str(exc) or "HTTP 404" in str(exc)):
            return "already-expired-or-revoked"
        raise


def receipt(
    contract: Contract,
    *,
    action: str,
    outcome: str,
    repository: Repository | None = None,
    landing_unit_id: str | None = None,
    branch: str | None = None,
    fetched_base: str | None = None,
    token_expires_at: str | None = None,
    affected_sessions: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "agent-source-identity-receipt",
        "identity_id": contract.identity_id,
        "logical_agent_id": contract.logical_agent_id,
        "display_name": contract.display_name,
        "provider_principal": contract.provider_principal,
        "definition_digest": contract.contract_digest,
        "app_id": contract.app_id,
        "installation_id": contract.installation_id,
        "permissions": contract.required_permissions,
        "human_reviewer_id": contract.human_reviewer_id,
        "authority": {
            "repository_inventory": contract.repository_inventory_ref,
            "workspace_contract": contract.workspace_contract_ref,
            "security_review": contract.security_review_ref,
        },
        "action": action,
        "outcome": outcome,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "secret_values_embedded": False,
    }
    if repository is not None:
        payload.update(
            {
                "repository": repository.full_name,
                "repository_id": repository.provider_repository_id,
            }
        )
    if landing_unit_id is not None:
        payload.update(
            {
                "landing_unit_id": landing_unit_id,
                "branch": branch,
                "fetched_base": fetched_base,
                "token_expires_at": token_expires_at,
            }
        )
    if affected_sessions is not None:
        payload["affected_sessions"] = affected_sessions
    return payload


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    write_json_atomic(path, payload)


def command_validate(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    inventory_path = workspace_repository_inventory_path(args)
    if inventory_path is not None:
        verify_workspace_repository_inventory(contract, inventory_path)
    print(f"Agent source identity contract valid: {contract.identity_id}")
    return 0


def command_commission(args: argparse.Namespace) -> int:
    contract = load_operating_contract(args)
    if args.bootstrap_private_key_file is not None:
        if not args.sandbox and not args.retire_bootstrap_key:
            raise IdentityError("normal bootstrap import must retire the temporary key after commissioning")
        import_private_key(
            contract,
            args.bootstrap_private_key_file,
            vault_command=args.vault_command,
            sandbox=args.sandbox,
        )
    with private_key_file(
        contract,
        vault_command=args.vault_command,
        sandbox=args.sandbox,
        sandbox_private_key=args.private_key_file,
    ) as key_path:
        client = provider_client(contract, args)
        app_jwt = verify_provider_identity(contract, client, key_path)
        observed: list[Repository] = []
        for repository in contract.repositories:
            token, provider_repository = issue_repository_token(
                contract, client, app_jwt, repository
            )
            client.revoke_token(token.token)
            observed.append(
                Repository(
                    provider_repository.full_name,
                    provider_repository.provider_repository_id,
                )
            )
    if tuple(observed) != contract.repositories:
        raise IdentityError("provider repository set does not match the Agent source contract")
    root = runtime_root(contract, args)
    if args.resume_issuance:
        with projection_lock(contract, root):
            (root / contract.suspension_filename).unlink(missing_ok=True)
    if args.bootstrap_private_key_file is not None and args.retire_bootstrap_key:
        args.bootstrap_private_key_file.unlink()
    payload = receipt(contract, action="commission", outcome="commissioned-inactive")
    payload["repositories"] = [
        {"full_name": item.full_name, "repository_id": item.provider_repository_id}
        for item in observed
    ]
    payload["private_key_custody"] = {
        "backend": "vault",
        "path": contract.vault_path,
        "property": contract.vault_property,
    }
    write_receipt(args.receipt, payload)
    print(f"Agent source identity commissioned; receipt={args.receipt}")
    return 0


def _validate_session_inputs(
    contract: Contract,
    *,
    landing_unit_id: str,
    repository_name: str,
    branch: str,
    fetched_base: str,
    human_reviewer_id: str,
) -> Repository:
    repository = expected_repository(contract, repository_name)
    if not LANDING_UNIT_PATTERN.fullmatch(landing_unit_id):
        raise IdentityError("landing unit id is invalid")
    if branch == contract.canonical_branch or not re.fullmatch(contract.allowed_branch_pattern, branch):
        raise IdentityError("Agent source branch must be an allowed non-default branch")
    if not REVISION_PATTERN.fullmatch(fetched_base):
        raise IdentityError("fetched base must be an exact Git commit")
    if human_reviewer_id != contract.human_reviewer_id:
        raise IdentityError("human reviewer does not match the Agent source contract")
    return repository


def command_deliver(args: argparse.Namespace) -> int:
    purpose = delivery_purpose(args)
    contract = purpose_contract(load_operating_contract(args), purpose)
    repository = _validate_session_inputs(
        contract,
        landing_unit_id=args.landing_unit_id,
        repository_name=args.repository,
        branch=args.branch,
        fetched_base=args.fetched_base,
        human_reviewer_id=args.human_reviewer_id,
    )
    root = runtime_root(contract, args)
    directory = session_directory(root, args.landing_unit_id)
    with projection_lock(contract, root):
        if (root / contract.suspension_filename).exists():
            raise IdentityError("Agent source token issuance is suspended")
        current = read_credential(contract, directory)
        credential = deliver_locked(contract, args, repository, directory, current)
    result = receipt(
        contract, action="deliver", outcome="rotated" if current is not None else "delivered",
        repository=repository, landing_unit_id=args.landing_unit_id, branch=args.branch,
        fetched_base=args.fetched_base, token_expires_at=credential["token_expires_at"],
    )
    result.update(purpose)
    write_receipt(
        args.receipt,
        result,
    )
    print(
        f"Agent source credential delivered; landing_unit={args.landing_unit_id} "
        f"repository={repository.full_name} receipt={args.receipt}"
    )
    return 0


def deliver_locked(
    contract: Contract,
    args: argparse.Namespace,
    repository: Repository,
    directory: Path,
    current: dict[str, Any] | None,
    *,
    before_issue: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Existing issuer transaction; caller must hold the projection lock.

    Shared by engineering delivery and the authenticated source-intent provider.
    This is not an alternate key custody, provider, permission or minting path.
    """
    immutable = {
        "repository": repository.full_name,
        "repository_id": repository.provider_repository_id,
        "landing_unit_id": args.landing_unit_id,
        "branch": args.branch,
        "fetched_base": args.fetched_base,
        "human_reviewer_id": args.human_reviewer_id,
    }
    purpose = delivery_purpose(args)
    if current is not None and any(current.get(key) != purpose.get(key) for key in ("purpose", "approval_ref")):
        raise IdentityError("existing runtime credential has a different source purpose or approval")
    immutable.update(purpose)
    if current is not None and any(current.get(key) != value for key, value in immutable.items()):
        raise IdentityError("existing runtime credential is bound to different session truth")
    with private_key_file(
        contract, vault_command=args.vault_command, sandbox=args.sandbox,
        sandbox_private_key=args.private_key_file,
    ) as key_path:
        client = provider_client(contract, args)
        app_jwt = verify_provider_identity(contract, client, key_path)
        if current is not None:
            safe_revoke(client, current["token"])
            (directory / contract.credential_filename).unlink()
        if before_issue is not None:
            before_issue()
        token, _ = issue_repository_token(contract, client, app_jwt, repository)
    credential = {
        "schema_version": 1,
        "identity_id": contract.identity_id,
        "logical_agent_id": contract.logical_agent_id,
        "provider_principal": contract.provider_principal,
        "app_id": contract.app_id,
        "installation_id": contract.installation_id,
        **immutable,
        "token": token.token,
        "token_expires_at": token.expires_at,
    }
    try:
        write_json_atomic(directory / contract.credential_filename, credential)
    except OSError:
        safe_revoke(client, token.token)
        raise
    return credential


def _remove_session(directory: Path) -> None:
    if directory.exists():
        shutil.rmtree(directory)
    parent = directory.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()


def command_revoke(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    root = runtime_root(contract, args)
    directory = session_directory(root, args.landing_unit_id)
    client = provider_client(contract, args)
    with projection_lock(contract, root):
        credential = read_credential(contract, directory)
        if credential is None:
            outcome = "already-absent"
            repository = expected_repository(contract, args.repository)
        else:
            if credential["landing_unit_id"] != args.landing_unit_id or credential["repository"] != args.repository:
                raise IdentityError("revocation request does not match the projected credential")
            repository = expected_repository(contract, credential["repository"])
            outcome = safe_revoke(client, credential["token"])
            _remove_session(directory)
    result = receipt(
            contract,
            action="revoke",
            outcome=outcome,
            repository=repository,
            landing_unit_id=args.landing_unit_id,
            branch=credential.get("branch") if credential else None,
            fetched_base=credential.get("fetched_base") if credential else None,
            token_expires_at=credential.get("token_expires_at") if credential else None,
        )
    if credential and credential.get("purpose") == WORKFLOW_PURPOSE:
        result.update({"purpose": credential["purpose"], "approval_ref": credential["approval_ref"],
                       "permissions": {**contract.required_permissions, "workflows": "write"}})
    write_receipt(args.receipt, result)
    print(f"Agent source credential revoked; receipt={args.receipt}")
    return 0


def command_suspend(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    root = runtime_root(contract, args)
    client = provider_client(contract, args)
    affected = 0
    with projection_lock(contract, root):
        write_json_atomic(
            root / contract.suspension_filename,
            {
                "schema_version": 1,
                "identity_id": contract.identity_id,
                "suspended_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )
        sessions = root / "sessions"
        for directory in sorted(sessions.iterdir()) if sessions.exists() else []:
            credential = read_credential(contract, directory)
            if credential is None:
                continue
            safe_revoke(client, credential["token"])
            _remove_session(directory)
            affected += 1
    write_receipt(
        args.receipt,
        receipt(
            contract,
            action="suspend",
            outcome="new-issuance-suspended",
            affected_sessions=affected,
        ),
    )
    print(f"Agent source identity suspended; affected_sessions={affected} receipt={args.receipt}")
    return 0


def add_provider_arguments(parser: argparse.ArgumentParser, *, private_key: bool) -> None:
    parser.add_argument("--provider-api-base-url")
    parser.add_argument("--sandbox", action="store_true")
    parser.add_argument("--vault-command", default="vault")
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--workspace-repo-inventory", type=Path)
    if private_key:
        parser.add_argument("--private-key-file", type=Path)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    commands = root.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate the Agent source identity definition")
    validate.add_argument("--workspace-repo-inventory", type=Path)
    validate.set_defaults(handler=command_validate)

    commission = commands.add_parser("commission", help="place the private key in Platform custody and verify the provider boundary")
    add_provider_arguments(commission, private_key=True)
    commission.add_argument("--bootstrap-private-key-file", type=Path)
    commission.add_argument("--retire-bootstrap-key", action="store_true")
    commission.add_argument("--resume-issuance", action="store_true")
    commission.set_defaults(handler=command_commission)

    deliver = commands.add_parser("deliver", help="project one exact-repository credential for one Landing Unit")
    add_provider_arguments(deliver, private_key=True)
    deliver.add_argument("--landing-unit-id", required=True)
    deliver.add_argument("--repository", required=True)
    deliver.add_argument("--branch", required=True)
    deliver.add_argument("--fetched-base", required=True)
    deliver.add_argument("--human-reviewer-id", required=True)
    deliver.add_argument("--purpose", choices=("ordinary-source", WORKFLOW_PURPOSE), default="ordinary-source")
    deliver.add_argument("--approval-ref")
    deliver.set_defaults(handler=command_deliver)

    revoke = commands.add_parser("revoke", help="revoke one Landing Unit credential and remove its projection")
    add_provider_arguments(revoke, private_key=False)
    revoke.add_argument("--landing-unit-id", required=True)
    revoke.add_argument("--repository", required=True)
    revoke.set_defaults(handler=command_revoke)

    suspend = commands.add_parser("suspend", help="stop issuance and revoke every projected Agent source credential")
    add_provider_arguments(suspend, private_key=False)
    suspend.set_defaults(handler=command_suspend)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.handler(args)
    except (IdentityError, FileNotFoundError, KeyError, OSError, subprocess.SubprocessError) as exc:
        print(f"Agent source identity failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
