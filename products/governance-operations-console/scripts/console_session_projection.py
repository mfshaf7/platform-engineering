#!/usr/bin/env python3
"""Publish a bounded Console identity projection from Platform session truth."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import tempfile
from typing import Any

import yaml
from jsonschema import Draft202012Validator


PRODUCT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = PRODUCT_ROOT / "session-projection-policy.yaml"
DEFAULT_POLICY_SCHEMA = PRODUCT_ROOT / "schemas/session-projection-policy.schema.json"
MAX_FILE_BYTES = 65536
SESSION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,126}[a-z0-9]$")
REFERENCE = re.compile(r"^[a-z][a-z0-9+.-]*:(?://)?[A-Za-z0-9][A-Za-z0-9._:/-]*$")


class ProjectionError(ValueError):
    pass


@dataclass(frozen=True)
class Principal:
    operator: str
    kind: str
    reference: str
    display_name: str
    roles: tuple[str, ...]
    authorities: tuple[str, ...]


@dataclass(frozen=True)
class Policy:
    digest: str
    schema_version: str
    source_authority: str
    source_mode: str
    session_mode: str
    environment: str
    maximum_lifetime_seconds: int
    lane: str
    profile_lifecycle: str
    profiles: tuple[str, ...]
    principals: dict[str, Principal]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProjectionError(f"{label} must be non-empty text")
    return value.strip()


def _text_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ProjectionError(f"{label} must be a non-empty list")
    items = tuple(_text(item, label) for item in value)
    if len(set(items)) != len(items):
        raise ProjectionError(f"{label} contains duplicates")
    return items


def _timestamp(value: Any, label: str) -> datetime:
    text = _text(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ProjectionError(f"{label} must be an ISO-8601 timestamp") from None
    if parsed.tzinfo is None:
        raise ProjectionError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _render_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_bounded_yaml(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink():
            raise ProjectionError(f"{label} must not be a symlink")
        info = path.stat()
    except OSError:
        raise ProjectionError(f"{label} is unavailable") from None
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
        raise ProjectionError(f"{label} must be a bounded regular file")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        raise ProjectionError(f"{label} is invalid") from None
    if not isinstance(value, dict):
        raise ProjectionError(f"{label} must contain an object")
    return value


def _load_private(path: Path, label: str) -> dict[str, Any]:
    value = _load_bounded_yaml(path, label)
    info = path.stat()
    if info.st_uid != os.geteuid():
        raise ProjectionError(f"{label} must be owned by the invoking operator")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise ProjectionError(f"{label} permissions must be 0600 or stricter")
    return value


def load_policy(
    path: Path = DEFAULT_POLICY,
    schema_path: Path = DEFAULT_POLICY_SCHEMA,
) -> Policy:
    value = _load_bounded_yaml(path, "session projection policy")
    schema = _load_bounded_yaml(schema_path, "session projection policy schema")
    Draft202012Validator.check_schema(schema)
    findings = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda finding: list(finding.absolute_path),
    )
    if findings:
        finding = findings[0]
        location = ".".join(str(part) for part in finding.absolute_path) or "<root>"
        raise ProjectionError(f"session projection policy is invalid at {location}: {finding.message}")
    if value.get("schema_version") != 1:
        raise ProjectionError("session projection policy must use schema_version 1")
    projection = value.get("projection")
    admission = value.get("admission")
    principals_value = value.get("principals")
    activation = value.get("activation")
    if not all(isinstance(item, dict) for item in (projection, admission, principals_value, activation)):
        raise ProjectionError("session projection policy sections are incomplete")
    if projection.get("secret_values_allowed") is not False:
        raise ProjectionError("session projection policy must deny secret values")
    if activation.get("security_approval_required") is not True:
        raise ProjectionError("session projection policy must require Security approval")
    if activation.get("definition_is_security_approval") is not False:
        raise ProjectionError("session projection definition must not approve itself")
    lifetime = projection.get("maximum_lifetime_seconds")
    if not isinstance(lifetime, int) or not 300 <= lifetime <= 28800:
        raise ProjectionError("maximum session lifetime must be between 300 and 28800 seconds")

    principals: dict[str, Principal] = {}
    for operator, candidate in principals_value.items():
        operator_name = _text(operator, "principal operator")
        if not isinstance(candidate, dict):
            raise ProjectionError("principal mapping must be an object")
        reference = _text(candidate.get("reference"), "principal reference")
        if not REFERENCE.fullmatch(reference):
            raise ProjectionError("principal reference is invalid")
        principals[operator_name] = Principal(
            operator=operator_name,
            kind=_text(candidate.get("kind"), "principal kind"),
            reference=reference,
            display_name=_text(candidate.get("display_name"), "principal display name"),
            roles=_text_list(candidate.get("roles"), "principal roles"),
            authorities=_text_list(candidate.get("authorities"), "principal authorities"),
        )
    if not principals:
        raise ProjectionError("session projection policy must admit at least one principal")

    return Policy(
        digest=digest(value),
        schema_version=_text(projection.get("schema_version"), "projection schema version"),
        source_authority=_text(projection.get("source_authority"), "source authority"),
        source_mode=_text(projection.get("source_mode"), "source mode"),
        session_mode=_text(projection.get("session_mode"), "session mode"),
        environment=_text(projection.get("environment"), "environment"),
        maximum_lifetime_seconds=lifetime,
        lane=_text(admission.get("lane"), "admission lane"),
        profile_lifecycle=_text(admission.get("profile_lifecycle"), "profile lifecycle"),
        profiles=_text_list(admission.get("profiles"), "admitted profiles"),
        principals=principals,
    )


def load_session_manifest(path: Path, policy: Policy) -> dict[str, Any]:
    manifest = _load_private(path, "dev-integration session manifest")
    if manifest.get("schema_version") != 1:
        raise ProjectionError("dev-integration session manifest schema is unsupported")
    if manifest.get("lane") != policy.lane:
        raise ProjectionError("session manifest lane is not admitted")
    if manifest.get("profile_lifecycle") != policy.profile_lifecycle:
        raise ProjectionError("session manifest profile lifecycle is not active")
    if manifest.get("profile_id") not in policy.profiles:
        raise ProjectionError("session manifest profile is not admitted")
    operator = _text(manifest.get("operator"), "session operator")
    if operator not in policy.principals:
        raise ProjectionError("session operator is not admitted")
    if operator != pwd.getpwuid(os.geteuid()).pw_name:
        raise ProjectionError("session operator does not match the invoking operating-system account")
    session_id = _text(manifest.get("session_id"), "session id")
    if not SESSION_ID.fullmatch(session_id):
        raise ProjectionError("session id is invalid")
    _timestamp(manifest.get("session_started_at"), "session start")
    if manifest.get("action") in {"down", "reset"}:
        raise ProjectionError("stopped dev-integration session cannot issue identity")
    return manifest


def build_projection(
    policy: Policy,
    manifest: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    started = _timestamp(manifest["session_started_at"], "session start")
    if started > current + timedelta(seconds=30):
        raise ProjectionError("session start is in the future")
    expires = started + timedelta(seconds=policy.maximum_lifetime_seconds)
    if current >= expires:
        raise ProjectionError("dev-integration session has expired")
    operator = manifest["operator"]
    principal = policy.principals[operator]
    binding = hashlib.sha256(
        canonical_bytes(
            {
                "policy_digest": policy.digest,
                "profile_id": manifest["profile_id"],
                "operator": operator,
                "session_id": manifest["session_id"],
                "session_started_at": _render_timestamp(started),
            }
        )
    ).hexdigest()
    return {
        "access": {
            "authorities": list(principal.authorities),
            "environment": policy.environment,
            "roles": list(principal.roles),
        },
        "principal": {
            "displayName": principal.display_name,
            "kind": principal.kind,
            "reference": principal.reference,
        },
        "schemaVersion": policy.schema_version,
        "session": {
            "authenticatedAt": _render_timestamp(started),
            "authenticationState": "authenticated",
            "expiresAt": _render_timestamp(expires),
            "mode": policy.session_mode,
            "reference": f"platform-session://{binding}",
        },
        "source": {
            "authority": policy.source_authority,
            "freshness": "current",
            "mode": policy.source_mode,
            "observedAt": _render_timestamp(started),
            "reference": f"platform-session-source://{binding}",
        },
    }


def validate_projection(value: dict[str, Any]) -> None:
    if set(value) != {"access", "principal", "schemaVersion", "session", "source"}:
        raise ProjectionError("identity projection fields are invalid")
    if value.get("schemaVersion") != "console-operator-identity/v1":
        raise ProjectionError("identity projection schema is unsupported")
    access = value.get("access")
    principal = value.get("principal")
    session = value.get("session")
    source = value.get("source")
    if not all(isinstance(item, dict) for item in (access, principal, session, source)):
        raise ProjectionError("identity projection sections are invalid")
    _text(access.get("environment"), "projection environment")
    if not isinstance(access.get("roles"), list) or not isinstance(access.get("authorities"), list):
        raise ProjectionError("projection access lists are invalid")
    _text(principal.get("displayName"), "projection display name")
    if principal.get("kind") != "human":
        raise ProjectionError("projection principal kind must be human")
    if not REFERENCE.fullmatch(_text(principal.get("reference"), "projection principal reference")):
        raise ProjectionError("projection principal reference is invalid")
    state = session.get("authenticationState")
    mode = source.get("mode")
    freshness = source.get("freshness")
    if state == "authenticated":
        if mode != "live" or freshness != "current":
            raise ProjectionError("authenticated projection source must be live and current")
        _timestamp(session.get("authenticatedAt"), "projection authenticated time")
        _timestamp(session.get("expiresAt"), "projection expiry")
        _timestamp(source.get("observedAt"), "projection observation time")
        if not REFERENCE.fullmatch(_text(session.get("reference"), "projection session reference")):
            raise ProjectionError("projection session reference is invalid")
    elif state == "unavailable":
        if mode != "unavailable" or freshness != "unavailable":
            raise ProjectionError("unavailable projection source is inconsistent")
        if session.get("reference") is not None:
            raise ProjectionError("unavailable projection must not retain a session reference")
        _timestamp(source.get("observedAt"), "projection observation time")
    else:
        raise ProjectionError("identity projection authentication state is unsupported")
    _text(session.get("mode"), "projection session mode")
    _text(source.get("authority"), "projection source authority")
    if not REFERENCE.fullmatch(_text(source.get("reference"), "projection source reference")):
        raise ProjectionError("projection source reference is invalid")


def validate_current_projection(
    value: dict[str, Any],
    *,
    now: datetime | None = None,
) -> None:
    validate_projection(value)
    if value["session"]["authenticationState"] != "authenticated":
        raise ProjectionError("identity projection is unavailable")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expires = _timestamp(value["session"]["expiresAt"], "projection expiry")
    if current >= expires:
        raise ProjectionError("identity projection has expired")


def _prepare_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink():
        raise ProjectionError("projection parent must not be a symlink")
    info = path.parent.stat()
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ProjectionError("projection parent must be operator-owned and private")


def _write_private(path: Path, value: dict[str, Any]) -> None:
    _prepare_parent(path)
    payload = json.dumps(value, sort_keys=True, indent=2) + "\n"
    if len(payload.encode()) > MAX_FILE_BYTES:
        raise ProjectionError("projection output exceeds its size limit")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _existing_projection(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = _load_private(path, "identity projection")
    validate_projection(value)
    return value


def _receipt(
    policy: Policy,
    projection: dict[str, Any],
    *,
    action: str,
    profile_id: str | None,
    session_id: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_type": "console-session-projection-receipt",
        "action": action,
        "outcome": "succeeded",
        "policy_digest": policy.digest,
        "projection_digest": digest(projection),
        "principal_reference": projection["principal"]["reference"],
        "session_reference": projection["session"]["reference"],
        "profile_id": profile_id,
        "session_id": session_id,
        "source_authority": projection["source"]["authority"],
        "recorded_at": projection["source"]["observedAt"],
        "secret_values_embedded": False,
    }


def issue(
    policy: Policy,
    session_manifest: Path,
    projection_path: Path,
    receipt_path: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    manifest = load_session_manifest(session_manifest, policy)
    candidate = build_projection(policy, manifest, now=now)
    validate_projection(candidate)
    _prepare_parent(projection_path)
    lock_path = projection_path.with_suffix(projection_path.suffix + ".lock")
    lock_descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        os.fchmod(lock_descriptor, 0o600)
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
        existing = _existing_projection(projection_path)
        if existing is not None and existing != candidate:
            if existing["session"]["authenticationState"] == "authenticated":
                raise ProjectionError("another active session projection must be revoked first")
        _write_private(projection_path, candidate)
        result = _receipt(
            policy,
            candidate,
            action="issue",
            profile_id=manifest["profile_id"],
            session_id=manifest["session_id"],
        )
        _write_private(receipt_path, result)
        return result
    finally:
        os.close(lock_descriptor)


def revoke(
    policy: Policy,
    projection_path: Path,
    receipt_path: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    _prepare_parent(projection_path)
    lock_path = projection_path.with_suffix(projection_path.suffix + ".lock")
    lock_descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        os.fchmod(lock_descriptor, 0o600)
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
        existing = _existing_projection(projection_path)
        if existing is None:
            raise ProjectionError("identity projection is unavailable")
        if existing["session"]["authenticationState"] == "unavailable":
            revoked = existing
        else:
            binding = hashlib.sha256(canonical_bytes(existing)).hexdigest()
            observed = _render_timestamp(current)
            revoked = {
                "access": {
                    "authorities": [],
                    "environment": existing["access"]["environment"],
                    "roles": [],
                },
                "principal": existing["principal"],
                "schemaVersion": existing["schemaVersion"],
                "session": {
                    "authenticatedAt": None,
                    "authenticationState": "unavailable",
                    "expiresAt": None,
                    "mode": "Unavailable",
                    "reference": None,
                },
                "source": {
                    "authority": policy.source_authority,
                    "freshness": "unavailable",
                    "mode": "unavailable",
                    "observedAt": observed,
                    "reference": f"platform-session-revocation://{binding}",
                },
            }
            validate_projection(revoked)
            _write_private(projection_path, revoked)
        result = _receipt(
            policy,
            revoked,
            action="revoke",
            profile_id=None,
            session_id=None,
        )
        _write_private(receipt_path, result)
        return result
    finally:
        os.close(lock_descriptor)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    issue_command = commands.add_parser("issue")
    issue_command.add_argument("--session-manifest", type=Path, required=True)
    issue_command.add_argument("--projection", type=Path, required=True)
    issue_command.add_argument("--receipt", type=Path, required=True)
    inspect_command = commands.add_parser("inspect")
    inspect_command.add_argument("--projection", type=Path, required=True)
    revoke_command = commands.add_parser("revoke")
    revoke_command.add_argument("--projection", type=Path, required=True)
    revoke_command.add_argument("--receipt", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        policy = load_policy(args.policy)
        if args.command == "validate":
            result = {"outcome": "valid", "policy_digest": policy.digest}
        elif args.command == "issue":
            result = issue(policy, args.session_manifest, args.projection, args.receipt)
        elif args.command == "revoke":
            result = revoke(policy, args.projection, args.receipt)
        else:
            projection = _load_private(args.projection, "identity projection")
            validate_current_projection(projection)
            result = {
                "outcome": "valid",
                "projection_digest": digest(projection),
                "principal_reference": projection["principal"]["reference"],
                "session_reference": projection["session"]["reference"],
                "authentication_state": projection["session"]["authenticationState"],
                "expires_at": projection["session"]["expiresAt"],
                "source_authority": projection["source"]["authority"],
            }
    except ProjectionError as exc:
        raise SystemExit(f"console-session-projection: {exc}") from exc
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
