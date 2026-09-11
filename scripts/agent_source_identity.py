#!/usr/bin/env python3
"""Commission and project the bounded Agent source identity."""

from __future__ import annotations

import argparse
import fcntl
from contextlib import contextmanager
from dataclasses import dataclass
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
from typing import Any, Iterator

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


@dataclass(frozen=True)
class Repository:
    full_name: str
    provider_repository_id: int


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
    repositories: tuple[Repository, ...]
    required_permissions: dict[str, str]
    maximum_token_lifetime_seconds: int
    rotate_before_expiry_seconds: int
    canonical_branch: str
    allowed_branch_pattern: str
    git_author_name: str
    git_author_email: str
    human_reviewer_id: str
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
        repositories=repositories,
        required_permissions=dict(identity["required_permissions"]),
        maximum_token_lifetime_seconds=identity["maximum_token_lifetime_seconds"],
        rotate_before_expiry_seconds=identity["rotate_before_expiry_seconds"],
        canonical_branch=source_boundary["canonical_branch"],
        allowed_branch_pattern=source_boundary["allowed_branch_pattern"],
        git_author_name=source_boundary["git_author"]["name"],
        git_author_email=source_boundary["git_author"]["email"],
        human_reviewer_id=source_boundary["human_reviewer_id"],
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
    verify_installation(
        installation,
        app_id=contract.app_id,
        installation_id=contract.installation_id,
        required_permissions=contract.required_permissions,
    )
    account = installation.get("account") or {}
    if (
        str(account.get("login") or "").casefold() != contract.account_login.casefold()
        or account.get("id") != contract.account_id
        or account.get("type") != contract.account_type
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
    if owner.casefold() != contract.account_login.casefold():
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
    os.chmod(path.parent, 0o700)
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
    print(f"Agent source identity contract valid: {contract.identity_id}")
    return 0


def command_commission(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
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
    contract = load_contract(args.contract)
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
        if current is not None:
            immutable = {
                "repository": repository.full_name,
                "repository_id": repository.provider_repository_id,
                "landing_unit_id": args.landing_unit_id,
                "branch": args.branch,
                "fetched_base": args.fetched_base,
                "human_reviewer_id": args.human_reviewer_id,
            }
            if any(current.get(key) != value for key, value in immutable.items()):
                raise IdentityError("existing runtime credential is bound to different session truth")
        with private_key_file(
            contract,
            vault_command=args.vault_command,
            sandbox=args.sandbox,
            sandbox_private_key=args.private_key_file,
        ) as key_path:
            client = provider_client(contract, args)
            app_jwt = verify_provider_identity(contract, client, key_path)
            if current is not None:
                safe_revoke(client, current["token"])
                (directory / contract.credential_filename).unlink()
            token, _ = issue_repository_token(contract, client, app_jwt, repository)
        credential = {
            "schema_version": 1,
            "identity_id": contract.identity_id,
            "logical_agent_id": contract.logical_agent_id,
            "provider_principal": contract.provider_principal,
            "app_id": contract.app_id,
            "installation_id": contract.installation_id,
            "repository": repository.full_name,
            "repository_id": repository.provider_repository_id,
            "landing_unit_id": args.landing_unit_id,
            "branch": args.branch,
            "fetched_base": args.fetched_base,
            "human_reviewer_id": args.human_reviewer_id,
            "token": token.token,
            "token_expires_at": token.expires_at,
        }
        try:
            write_json_atomic(directory / contract.credential_filename, credential)
        except OSError:
            safe_revoke(client, token.token)
            raise
    write_receipt(
        args.receipt,
        receipt(
            contract,
            action="deliver",
            outcome="rotated" if current is not None else "delivered",
            repository=repository,
            landing_unit_id=args.landing_unit_id,
            branch=args.branch,
            fetched_base=args.fetched_base,
            token_expires_at=token.expires_at,
        ),
    )
    print(
        f"Agent source credential delivered; landing_unit={args.landing_unit_id} "
        f"repository={repository.full_name} receipt={args.receipt}"
    )
    return 0


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
    write_receipt(
        args.receipt,
        receipt(
            contract,
            action="revoke",
            outcome=outcome,
            repository=repository,
            landing_unit_id=args.landing_unit_id,
            branch=credential.get("branch") if credential else None,
            fetched_base=credential.get("fetched_base") if credential else None,
            token_expires_at=credential.get("token_expires_at") if credential else None,
        ),
    )
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
    if private_key:
        parser.add_argument("--private-key-file", type=Path)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    commands = root.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate the Agent source identity definition")
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
