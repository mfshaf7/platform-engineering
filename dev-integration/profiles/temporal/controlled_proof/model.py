from __future__ import annotations

import errno
import hashlib
import json
import os
import pwd
import re
import shutil
import stat
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

MAX_ARTIFACT_BYTES = 1_048_576
TERMINAL_CLEANUP_START_RESERVE_SECONDS = 120
CONTROLLED_EXECUTABLE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REVISION_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,255}$")
SAFE_INTEGER_MAX = 9_007_199_254_740_991

SCENARIO_ORDER = (
    "nominal-completion",
    "workflow-worker-restart",
    "temporal-runtime-restart",
    "deterministic-replay",
    "duplicate-suppression",
    "cancellation",
    "unavailable-dependency",
    "identity-denial",
    "payload-boundary",
    "backup-restore",
    "exact-baseline-restore",
)
PROOF_OWNERS = (
    "platform-engineering",
    "operator-orchestration-service",
    "workspace-governance-control-fabric",
)
OOS_SCENARIOS = SCENARIO_ORDER[:-1]
REQUIRED_SCENARIO_OWNERS = {
    scenario_id: PROOF_OWNERS for scenario_id in OOS_SCENARIOS
} | {"exact-baseline-restore": ("platform-engineering",)}
PERMITTED_ACTIONS = (
    "install-scoped-runtime",
    "start-validation-readiness-run",
    "restart-oos-workflow-worker",
    "restart-wgcf-activity-worker",
    "restart-temporal-runtime",
    "cancel-validation-readiness-run",
    "simulate-unavailable-dependency",
    "verify-identity-denial",
    "capture-backup",
    "restore-exact-baseline",
    "remove-scoped-runtime",
)
REQUIRED_STOP_CONDITIONS = (
    "authorization-expired",
    "source-revision-drift",
    "runtime-artifact-drift",
    "runtime-image-drift",
    "target-scope-mismatch",
    "identity-or-queue-denial-failed",
    "baseline-unavailable",
    "unexpected-side-effect",
    "evidence-custody-failed",
    "restore-failed",
)


class ControlledProofError(RuntimeError):
    """Raised when a controlled-proof boundary fails closed."""

    def __init__(
        self,
        message: str,
        *,
        evidence_refs: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.evidence_refs = list(evidence_refs or [])


def controlled_subprocess_environment(
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    environment = {
        "PATH": CONTROLLED_EXECUTABLE_PATH,
        "HOME": pwd.getpwuid(os.geteuid()).pw_dir,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
    }
    if overrides:
        environment.update(overrides)
    return environment


def resolve_controlled_command(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
) -> list[str]:
    if not command or not isinstance(command[0], str) or not command[0]:
        raise ControlledProofError("controlled subprocess command is empty")
    executable = shutil.which(command[0], path=environment.get("PATH"))
    if executable is None:
        raise ControlledProofError(
            f"controlled subprocess executable is unavailable: {command[0]}"
        )
    return [executable, *command[1:]]


def operator_scoped_dns_label(prefix: str, operator_id: str) -> str:
    """Render a collision-resistant DNS label for one operator-scoped resource."""
    if re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", prefix) is None:
        raise ControlledProofError("controlled resource prefix is not a DNS label")
    operator = require_identifier(operator_id, "operator_id")
    normalized_operator = operator.lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", normalized_operator)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        raise ControlledProofError("operator id does not produce a DNS label")

    candidate = f"{prefix}-{slug}"
    if len(candidate) <= 63 and slug == operator:
        return candidate

    suffix = hashlib.sha256(operator.encode("utf-8")).hexdigest()[:12]
    head_length = 63 - len(prefix) - len(suffix) - 2
    head = slug[:head_length].rstrip("-")
    if not head:
        raise ControlledProofError("operator id cannot fit a scoped DNS label")
    return f"{prefix}-{head}-{suffix}"


def operator_scope_id(operator_id: str) -> str:
    """Return one collision-resistant filesystem and label scope per operator."""

    return operator_scoped_dns_label("operator", operator_id)


def now_utc() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def parse_timestamp(value: str, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ControlledProofError(f"{label} must be an RFC 3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ControlledProofError(f"{label} is not a valid timestamp") from exc
    if parsed.tzinfo is None:
        raise ControlledProofError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def normalize_digest(value: str, label: str) -> str:
    if not isinstance(value, str) or DIGEST_RE.fullmatch(value) is None:
        raise ControlledProofError(f"{label} must be a sha256 digest")
    return value


def sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ControlledProofError(f"JSON artifact contains duplicate field: {key}")
        result[key] = value
    return result


def decode_bounded_json(raw: bytes, *, label: str) -> dict[str, Any]:
    if not raw or len(raw) > MAX_ARTIFACT_BYTES:
        raise ControlledProofError(f"{label} is empty or exceeds its size boundary")
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ControlledProofError(f"unsupported JSON number: {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControlledProofError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ControlledProofError(f"{label} must contain a JSON object")
    return payload


def read_bounded_json_with_digest(
    path: Path,
    *,
    expected_digest: str | None = None,
) -> tuple[dict[str, Any], str]:
    supplied_path = path.expanduser()
    try:
        descriptor = os.open(
            supplied_path,
            os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ControlledProofError(
                f"artifact must not be a symbolic link: {supplied_path}"
            ) from exc
        raise ControlledProofError(f"artifact is unavailable: {supplied_path}") from exc
    try:
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            raise ControlledProofError(
                f"artifact is not a regular file: {supplied_path}"
            )
        if file_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise ControlledProofError(
                f"artifact must not be group or world writable: {supplied_path}"
            )
        if file_stat.st_size <= 0 or file_stat.st_size > MAX_ARTIFACT_BYTES:
            raise ControlledProofError(
                f"artifact is empty or exceeds its size boundary: {supplied_path}"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            raw = handle.read(MAX_ARTIFACT_BYTES + 1)
        if len(raw) > MAX_ARTIFACT_BYTES:
            raise ControlledProofError(
                f"artifact exceeds its size boundary while reading: {supplied_path}"
            )
    finally:
        os.close(descriptor)
    actual_digest = sha256_bytes(raw)
    if expected_digest is not None and actual_digest != normalize_digest(
        expected_digest, "expected artifact digest"
    ):
        raise ControlledProofError(f"artifact digest does not match: {supplied_path}")
    return decode_bounded_json(raw, label=f"artifact {supplied_path}"), actual_digest


def read_bounded_json(path: Path, *, expected_digest: str | None = None) -> dict[str, Any]:
    payload, _ = read_bounded_json_with_digest(
        path,
        expected_digest=expected_digest,
    )
    return payload


def _validate_canonical_domain(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        if abs(value) > SAFE_INTEGER_MAX:
            raise ControlledProofError(f"{path} exceeds the RFC 8785 safe integer domain")
        return
    if isinstance(value, float):
        raise ControlledProofError(f"{path} contains an unsupported floating-point value")
    if isinstance(value, str):
        if any(ord(character) < 0x20 for character in value):
            raise ControlledProofError(f"{path} contains a control character")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_canonical_domain(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ControlledProofError(f"{path} contains a non-string object key")
            if not key.isascii():
                raise ControlledProofError(
                    f"{path} contains a non-ASCII key outside the reviewed canonical domain"
                )
            _validate_canonical_domain(item, f"{path}.{key}")
        return
    raise ControlledProofError(f"{path} contains unsupported JSON type {type(value).__name__}")


def canonical_json_bytes(payload: Mapping[str, Any] | Sequence[Any]) -> bytes:
    """Return RFC 8785 bytes for the schema-constrained proof artifact domain.

    Proof schemas use ASCII object keys, integers in the IEEE-754 exact range,
    and no floating-point fields. Rejecting values outside that reviewed subset
    avoids claiming generic JCS support where Python's encoder would be
    ambiguous.
    """

    _validate_canonical_domain(payload)
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_digest(payload: Mapping[str, Any] | Sequence[Any]) -> str:
    return sha256_bytes(canonical_json_bytes(payload))


def _private_artifact_destination(path: Path) -> Path:
    supplied_path = path.expanduser().absolute()
    if supplied_path.is_symlink():
        raise ControlledProofError(
            f"refusing symbolic-link artifact destination: {supplied_path}"
        )
    destination = supplied_path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    parent_stat = destination.parent.stat()
    if not stat.S_ISDIR(parent_stat.st_mode) or parent_stat.st_uid != os.geteuid():
        raise ControlledProofError(
            f"artifact parent must be an operator-owned directory: {destination.parent}"
        )
    if parent_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ControlledProofError(
            f"artifact parent must not be group or world writable: {destination.parent}"
        )
    return destination


def write_json_atomic(
    path: Path,
    payload: Mapping[str, Any],
) -> str:
    destination = _private_artifact_destination(path)
    if destination.exists():
        raise ControlledProofError(f"refusing to overwrite artifact: {destination}")
    rendered = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=destination.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, destination)
        except FileExistsError as exc:
            raise ControlledProofError(
                f"refusing to overwrite artifact: {destination}"
            ) from exc
        temporary_path.unlink()
        os.chmod(destination, 0o600)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary_path.unlink(missing_ok=True)
    return sha256_bytes(rendered)


def create_json_exclusive(
    path: Path,
    payload: Mapping[str, Any],
    *,
    conflict_message: str | None = None,
) -> str:
    destination = _private_artifact_destination(path)
    rendered = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=destination.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, destination)
        except FileExistsError as exc:
            raise ControlledProofError(
                conflict_message
                or (
                    "authorization was already consumed: "
                    f"{payload.get('authorization_id', 'unknown')}"
                )
            ) from exc
        temporary_path.unlink()
        os.chmod(destination, 0o600)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary_path.unlink(missing_ok=True)
    return sha256_bytes(rendered)


def load_schema(path: Path) -> dict[str, Any]:
    schema = read_bounded_json(path)
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # jsonschema exposes several schema error subclasses.
        raise ControlledProofError(f"invalid JSON schema: {path}") from exc
    return schema


def validate_schema(payload: Mapping[str, Any], schema: Mapping[str, Any], label: str) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.absolute_path))
    if not errors:
        return
    error = errors[0]
    location = ".".join(str(part) for part in error.absolute_path) or "<root>"
    raise ControlledProofError(f"{label} schema validation failed at {location}: {error.message}")


def require_exact_keys(payload: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if extra:
            details.append(f"unexpected {', '.join(extra)}")
        raise ControlledProofError(f"{label} fields are invalid: {'; '.join(details)}")


def require_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or IDENTIFIER_RE.fullmatch(value) is None:
        raise ControlledProofError(f"{label} is not a valid identifier")
    return value
