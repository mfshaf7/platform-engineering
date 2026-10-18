#!/usr/bin/env python3
"""Serve the bounded Platform owner protocol for Console operations."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import fcntl
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
from typing import Any, Iterator
from urllib.parse import unquote, urlparse

import yaml

# Reuse the shared Platform issuer, not a Console-owned credential subsystem.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import agent_source_intent as source_credentials


PRODUCT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PRODUCT_ROOT.parents[1]
DEFAULT_POLICY = PRODUCT_ROOT / "complete-runtime-policy.yaml"
TERMINAL_STATES = {"succeeded", "failed", "cancelled"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,255}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
ALLOWED_ACTIONS = {
    "dev-integration.start",
    "dev-integration.status",
    "dev-integration.access",
    "dev-integration.smoke",
    "dev-integration.stop",
    "dev-integration.promote-check",
    *source_credentials.ACTION_SET,
}


class ProviderError(RuntimeError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def canonical_digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ProviderError(503, "platform_provider_policy_invalid", "Platform provider policy is invalid.")
    provider = value.get("platform_operation_provider")
    if not isinstance(provider, dict):
        raise ProviderError(503, "platform_provider_policy_invalid", "Platform provider policy is incomplete.")
    required = {
        "caller_id", "composition_id", "operator_id", "profile_id",
        "security_gate_id", "subject_ref",
    }
    if not required.issubset(provider):
        raise ProviderError(503, "platform_provider_policy_invalid", "Platform provider policy is incomplete.")
    if provider["subject_ref"] != f"profile:{provider['profile_id']}":
        raise ProviderError(503, "platform_provider_policy_invalid", "Platform provider subject binding is invalid.")
    security = value.get("security")
    if not isinstance(security, dict) or security.get("gate_id") != provider["security_gate_id"]:
        raise ProviderError(503, "platform_provider_policy_invalid", "Platform provider Security binding is invalid.")
    return value


def git_head(repo_root: Path = REPO_ROOT) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode or not re.fullmatch(r"[0-9a-f]{40}", result.stdout.strip()):
        raise ProviderError(503, "platform_provider_source_unavailable", "Platform source revision is unavailable.")
    return result.stdout.strip()


def git_tree(repo_root: Path = REPO_ROOT) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD^{tree}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode or not re.fullmatch(r"[0-9a-f]{40}", result.stdout.strip()):
        raise ProviderError(503, "platform_provider_source_unavailable", "Platform source tree is unavailable.")
    return result.stdout.strip()


def require_security_activation(policy: dict[str, Any], source_version: str) -> None:
    security = policy["security"]
    if security.get("status") != "accepted":
        raise ProviderError(503, "platform_provider_security_gate_required", "The exact Platform Security gate is not accepted.")
    if not re.fullmatch(r"[0-9a-f]{40}", str(security.get("platform_revision", ""))):
        raise ProviderError(503, "platform_provider_security_gate_invalid", "The Security-reviewed Platform revision is invalid.")
    if security.get("platform_tree") != git_tree():
        raise ProviderError(503, "platform_provider_security_gate_stale", "The Platform source tree is not the Security-accepted tree.")
    if not DIGEST.fullmatch(str(security.get("decision_digest", ""))):
        raise ProviderError(503, "platform_provider_security_gate_invalid", "The Platform Security decision digest is invalid.")
    if not str(security.get("decision_uri", "")).startswith("security-architecture://"):
        raise ProviderError(503, "platform_provider_security_gate_invalid", "The Platform Security decision URI is invalid.")


def capability_catalog(policy: dict[str, Any], source_version: str, *, activated: bool) -> dict[str, Any]:
    provider = policy["platform_operation_provider"]
    capabilities = []
    for action in sorted(ALLOWED_ACTIONS):
        source_action = action in source_credentials.ACTION_SET
        suffix = action.removeprefix("dev-integration.")
        available = activated or action in {"dev-integration.start", "dev-integration.status", "agent-source.revoke"}
        capabilities.append({
            "capability_id": action if source_action else f"dev-integration.{provider['profile_id']}.{suffix}",
            "action": action,
            "available": available,
            "unavailable_reason": None if available else "The complete Console runtime is not active.",
            "required_capability": f"platform.{action}" if source_action else f"platform.dev-integration.{suffix}",
            "approval_required": True,
            "destructive": action in {"dev-integration.stop", "agent-source.revoke"},
        })
    return {
        "schema_version": 1,
        "catalog_id": "platform-console-operations",
        "source_version": source_version,
        "observed_at": now(),
        "freshness": "current",
        "subjects": [{
            "kind": "dev-integration-profile",
            "ref": provider["subject_ref"],
            "source_version": source_version,
            "owner": "platform-engineering",
            "capabilities": capabilities,
        }],
    }


def command_intent(command: dict[str, Any]) -> dict[str, Any]:
    return {
        key: command[key]
        for key in (
            "schema_version", "command_id", "idempotency_key", "correlation_id",
            "causation_id", "actor_ref", "subject", "capability_id", "action",
            "input", "requested_at",
        )
    }


def validate_command(command: Any, policy: dict[str, Any], source_version: str) -> dict[str, Any]:
    if not isinstance(command, dict):
        raise ProviderError(400, "platform_provider_command_invalid", "Platform command must be an object.")
    exact = {
        "schema_version", "command_id", "idempotency_key", "correlation_id",
        "causation_id", "actor_ref", "subject", "capability_id", "action",
        "input", "requested_at", "intent_digest", "approval",
    }
    if set(command) != exact or command.get("schema_version") != 1:
        raise ProviderError(400, "platform_provider_command_invalid", "Platform command fields are invalid.")
    for field in ("command_id", "idempotency_key", "correlation_id", "actor_ref", "capability_id"):
        if not IDENTIFIER.fullmatch(str(command.get(field, ""))):
            raise ProviderError(400, "platform_provider_command_invalid", f"Platform command {field} is invalid.")
    provider = policy["platform_operation_provider"]
    subject = command.get("subject")
    if subject != {
        "kind": "dev-integration-profile",
        "ref": provider["subject_ref"],
        "expected_source_version": source_version,
    }:
        raise ProviderError(409, "platform_provider_source_stale", "Platform command source binding is stale or invalid.")
    action = command.get("action")
    source_action = isinstance(action, str) and action in source_credentials.ACTION_SET
    expected_capability = action if source_action else f"dev-integration.{provider['profile_id']}.{str(action).removeprefix('dev-integration.')}"
    if action not in ALLOWED_ACTIONS or command.get("capability_id") != expected_capability:
        raise ProviderError(403, "platform_provider_capability_forbidden", "Platform command is outside the finite capability set.")
    if source_action:
        try:
            source_credentials.validate_input(command.get("input"), caller_id=provider["caller_id"], operator_id=provider["operator_id"])
        except source_credentials.identity.IdentityError:
            raise ProviderError(400, "platform_source_intent_invalid", "Source credential intent binding is invalid.") from None
    elif command.get("input") != {}:
        raise ProviderError(400, "platform_provider_input_forbidden", "This Platform capability accepts no caller-selected input.")
    digest = canonical_digest(command_intent(command))
    approval = command.get("approval")
    if command.get("intent_digest") != digest or not isinstance(approval, dict):
        raise ProviderError(400, "platform_provider_approval_invalid", "Platform command approval is invalid.")
    if (
        approval.get("decision") != "approved"
        or approval.get("operator_id") != provider["operator_id"]
        or command.get("actor_ref") != provider["operator_id"]
        or approval.get("intent_digest") != digest
        or not IDENTIFIER.fullmatch(str(approval.get("decision_ref", "")))
    ):
        raise ProviderError(403, "platform_provider_approval_invalid", "Platform command lacks exact operator approval.")
    for field in ("requested_at",):
        try:
            datetime.fromisoformat(str(command[field]).replace("Z", "+00:00"))
        except ValueError:
            raise ProviderError(400, "platform_provider_command_invalid", f"Platform command {field} is invalid.") from None
    if set(approval) != {"decision", "operator_id", "decision_ref", "decided_at", "intent_digest"}:
        raise ProviderError(400, "platform_provider_approval_invalid", "Platform command approval fields are invalid.")
    try:
        datetime.fromisoformat(str(approval["decided_at"]).replace("Z", "+00:00"))
    except ValueError:
        raise ProviderError(400, "platform_provider_approval_invalid", "Platform command approval time is invalid.") from None
    return json.loads(json.dumps(command))


def process_identity(pid: int) -> dict[str, Any] | None:
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
        tail = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()
        start_ticks = int(tail[19])
    except (OSError, IndexError, ValueError):
        return None
    return {"pid": pid, "boot_id": boot_id, "start_ticks": start_ticks}


def worker_is_current(worker: Any) -> bool:
    if not isinstance(worker, dict) or set(worker) != {"pid", "boot_id", "start_ticks", "started_at"}:
        return False
    pid = worker.get("pid")
    if not isinstance(pid, int) or pid <= 1:
        return False
    observed = process_identity(pid)
    return observed is not None and all(observed[key] == worker.get(key) for key in observed)


class OperationStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.operations = root / "operations"
        self.logs = root / "logs"
        for path in (root, self.operations, self.logs):
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.chmod(0o700)

    def key(self, command_id: str) -> str:
        return hashlib.sha256(command_id.encode()).hexdigest()

    def path(self, command_id: str) -> Path:
        return self.operations / f"{self.key(command_id)}.json"

    def lock_path(self, command_id: str) -> Path:
        return self.operations / f"{self.key(command_id)}.lock"

    @contextmanager
    def lock(self, command_id: str) -> Iterator[None]:
        path = self.lock_path(command_id)
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def read(self, command_id: str) -> dict[str, Any] | None:
        path = self.path(command_id)
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("command", {}).get("command_id") != command_id:
            raise ProviderError(503, "platform_provider_state_invalid", "Platform operation state is invalid.")
        return value

    def write(self, record: dict[str, Any]) -> None:
        target = self.path(record["command"]["command_id"])
        descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(record, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def operation_id(command_id: str) -> str:
    return f"platform-owner-operation:{hashlib.sha256(command_id.encode()).hexdigest()[:24]}"


def event(record: dict[str, Any], state: str, summary: str) -> None:
    sequence = len(record["events"]) + 1
    record["events"].append({
        "event_id": f"event:{record['command']['command_id']}:{sequence}",
        "sequence": sequence,
        "state": state,
        "occurred_at": now(),
        "summary": summary,
    })
    record["state"] = state
    record["updated_at"] = record["events"][-1]["occurred_at"]


def projection(record: dict[str, Any]) -> dict[str, Any]:
    command = record["command"]
    return {
        "schema_version": 1,
        "operation_id": record["operation_id"],
        "command_id": command["command_id"],
        "correlation_id": command["correlation_id"],
        "state": record["state"],
        "attempt": record["attempt"],
        "subject_ref": command["subject"]["ref"],
        "capability_id": command["capability_id"],
        "action": command["action"],
        "retryable": record["retryable"],
        "cancel_available": record["cancel_available"],
        "blocker": record["blocker"],
        "failure": record["failure"],
        "receipt": record["receipt"],
        "safe_log_ref": record["safe_log_ref"],
        "updated_at": record["updated_at"],
        "events": record["events"],
    }


def runner_command(action: str, policy: dict[str, Any]) -> list[str]:
    provider = policy["platform_operation_provider"]
    script = REPO_ROOT / "scripts" / "dev_integration.py"
    workspace = str(Path(policy["workspace_root"]))
    profile = provider["profile_id"]
    composition = provider["composition_id"]
    common = [sys.executable, str(script)]
    if action == "dev-integration.start":
        # The existing coordinator restores the whole accepted Console boundary
        # through its retained profile unit, including canonical-data bindings.
        return [sys.executable, str(PRODUCT_ROOT / "scripts/console_complete_runtime.py"), "activate"]
    if action == "dev-integration.status":
        return [*common, "status", "--composition", composition, "--workspace-root", workspace]
    if action == "dev-integration.stop":
        return [*common, "down", "--composition", composition, "--workspace-root", workspace]
    if action == "dev-integration.smoke":
        return [*common, "smoke", "--profile", profile, "--composition-context", composition, "--workspace-root", workspace]
    mapped = action.removeprefix("dev-integration.").replace("-", "_")
    if mapped in {"access", "promote_check"}:
        cli_action = "promote-check" if mapped == "promote_check" else mapped
        return [*common, cli_action, "--profile", profile, "--workspace-root", workspace]
    raise ProviderError(403, "platform_provider_capability_forbidden", "Platform action is not executable.")


def new_record(command: dict[str, Any], source_version: str) -> dict[str, Any]:
    timestamp = now()
    record = {
        "operation_id": operation_id(command["command_id"]),
        "command": command,
        "command_digest": canonical_digest(command),
        "source_version": source_version,
        "state": "queued",
        "attempt": 1,
        "retryable": False,
        "cancel_available": command["action"] not in source_credentials.ACTION_SET,
        "blocker": None,
        "failure": None,
        "receipt": None,
        "safe_log_ref": f"platform-log://operations/{hashlib.sha256(command['command_id'].encode()).hexdigest()}",
        "worker": None,
        "events": [],
        "updated_at": timestamp,
    }
    event(record, "queued", "Platform accepted the exact command for bounded execution.")
    return record


def spawn_worker(store: OperationStore, record: dict[str, Any], policy_path: Path) -> None:
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--policy", str(policy_path),
            "--state-root", str(store.root),
            "worker", record["command"]["command_id"],
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    identity = process_identity(process.pid)
    if identity is None:
        raise ProviderError(503, "platform_provider_worker_unavailable", "Platform worker identity could not be established.")
    record["worker"] = {**identity, "started_at": now()}
    store.write(record)


def reconcile_worker(record: dict[str, Any]) -> bool:
    if record["state"] not in {"queued", "running"} or worker_is_current(record.get("worker")):
        return False
    record["worker"] = None
    record["cancel_available"] = False
    record["retryable"] = True
    record["blocker"] = {
        "code": "platform_owner_worker_lost",
        "owner": "platform-engineering",
        "reason": "The recorded worker is no longer the same live process after recovery.",
        "supported_dispositions": ["workaround", "defer"],
        "next_action": "retry-same-operation",
    }
    event(record, "blocked", "Platform blocked the operation after exact worker identity was lost.")
    return True


def execute_worker(store: OperationStore, policy: dict[str, Any], command_id: str) -> int:
    with store.lock(command_id):
        record = store.read(command_id)
        if record is None or record["state"] != "queued":
            return 0
        if record["command"]["action"] in source_credentials.ACTION_SET:
            try:
                current_source = git_head()
                require_security_activation(policy, current_source)
                if current_source != record["source_version"]:
                    raise ProviderError(409, "platform_provider_source_stale", "Queued source credential command requires its exact Platform source.")
                validate_command(record["command"], policy, current_source)
                if record["command"]["action"] != "agent-source.revoke" and not activation_is_current(policy, current_source):
                    raise ProviderError(409, "platform_source_runtime_inactive", "Credential issuance requires the current accepted Console runtime; exact revocation remains available.")
            except ProviderError as exc:
                record["cancel_available"] = False
                record["retryable"] = False
                record["failure"] = {"code": exc.code, "detail": str(exc), "owner": "platform-engineering"}
                record["receipt"] = terminal_receipt(record, "failed", "none")
                event(record, "failed", "Platform rejected stale or invalid credential authority before issuance.")
                store.write(record)
                return 1
        record["cancel_available"] = record["command"]["action"] not in source_credentials.ACTION_SET
        event(record, "running", "Platform started the bounded owner operation.")
        store.write(record)
    log_path = store.logs / f"{store.key(command_id)}-attempt-{record['attempt']}.log"
    credential_receipt = None
    credential_failure = None
    with log_path.open("w", encoding="utf-8") as log:
        log_path.chmod(0o600)
        if record["command"]["action"] in source_credentials.ACTION_SET:
            try:
                # All executable/custody paths are owner-selected, never HTTP input.
                # OOS must resolve canonical start/session truth before dispatch.
                args = argparse.Namespace(
                    contract=REPO_ROOT / "security/agent-source-identity.yaml", sandbox=False,
                    runtime_root=None, workspace_repo_inventory=Path(policy["workspace_root"]) / "workspace-governance/contracts/repos.yaml",
                    provider_api_base_url=None, vault_command="vault", private_key_file=None,
                )
                credential_receipt = source_credentials.operate(
                    args, state_root=store.root, action=record["command"]["action"], command_id=command_id,
                    input_value=record["command"]["input"],
                    caller_id=policy["platform_operation_provider"]["caller_id"],
                    operator_id=policy["platform_operation_provider"]["operator_id"],
                )
                returncode = 0
                log.write("Exact source-intent credential operation completed; secret-free receipt retained.\n")
            except source_credentials.SourceIntentError as exc:
                returncode = 1
                credential_failure = {"code": exc.code, "detail": str(exc), "owner": "platform-engineering"}
                if exc.retry_after is not None:
                    credential_failure["retry_after"] = exc.retry_after
                log.write(f"{exc.code}: {exc}\n")
            except Exception:
                # Provider/Vault errors may contain sensitive response details.
                # Never project those exceptions or subprocess output into logs.
                returncode = 1
                log.write("Source credential action failed safely; retain original command and recover or revoke its exact intent.\n")
        else:
            result = subprocess.run(
                runner_command(record["command"]["action"], policy),
                stdout=log, stderr=subprocess.STDOUT, text=True, check=False,
            )
            returncode = result.returncode
    with store.lock(command_id):
        current = store.read(command_id)
        if current is None or current["state"] in TERMINAL_STATES:
            return 0
        current["cancel_available"] = False
        current["worker"] = None
        if returncode == 0:
            current["retryable"] = False
            current["receipt"] = terminal_receipt(current, "succeeded", "verified")
            if credential_receipt is not None:
                current["receipt"]["source_credential"] = credential_receipt
            event(current, "succeeded", "Platform owner command completed with current readback.")
        else:
            current["retryable"] = True
            current["failure"] = credential_failure or {
                "code": "platform_owner_command_failed",
                "detail": "The bounded Platform owner command failed; inspect the safe log reference.",
                "owner": "platform-engineering",
            }
            current["receipt"] = terminal_receipt(current, "failed", "partial" if current["command"]["action"] in source_credentials.ACTION_SET else "none")
            event(current, "failed", "Platform owner command failed without claiming success.")
        store.write(current)
    return returncode


def terminal_receipt(record: dict[str, Any], outcome: str, effect: str) -> dict[str, Any]:
    return {
        "receipt_ref": f"platform-receipt://operations/{record['operation_id']}/attempt/{record['attempt']}",
        "outcome": outcome,
        "recorded_at": now(),
        "source_version": record["source_version"],
        "effect": effect,
    }


class ProviderService:
    def __init__(self, policy: dict[str, Any], policy_path: Path, store: OperationStore, source_version: str) -> None:
        self.policy = policy
        self.policy_path = policy_path
        self.store = store
        self.source_version = source_version
        require_security_activation(policy, source_version)

    def catalog(self) -> dict[str, Any]:
        active = activation_is_current(self.policy, self.source_version)
        return capability_catalog(self.policy, self.source_version, activated=active)

    def submit(self, body: Any) -> tuple[int, dict[str, Any]]:
        command = validate_command(body.get("command") if isinstance(body, dict) else None, self.policy, self.source_version)
        with self.store.lock(command["command_id"]):
            current = self.store.read(command["command_id"])
            if current is not None:
                if current["command_digest"] != canonical_digest(command):
                    raise ProviderError(409, "platform_provider_command_conflict", "Command identity is already bound to another intent.")
                return 200, projection(current)
            record = new_record(command, self.source_version)
            self.store.write(record)
            spawn_worker(self.store, record, self.policy_path)
            return 202, projection(record)

    def read(self, command_id: str) -> dict[str, Any]:
        with self.store.lock(command_id):
            record = self.store.read(command_id)
            if record is None:
                raise ProviderError(404, "platform_provider_operation_not_found", "Platform operation was not found.")
            if reconcile_worker(record):
                self.store.write(record)
            return projection(record)

    def control(self, operation_id_value: str, body: Any) -> dict[str, Any]:
        control = body.get("control") if isinstance(body, dict) else None
        expected = {
            "schema_version", "control_id", "idempotency_key", "action",
            "operator_id", "reason", "requested_at",
        }
        if not isinstance(control, dict) or set(control) != expected or control.get("schema_version") != 1:
            raise ProviderError(400, "platform_provider_control_invalid", "Platform control is invalid.")
        if control.get("action") not in {"retry", "cancel"}:
            raise ProviderError(400, "platform_provider_control_invalid", "Platform control action is invalid.")
        provider = self.policy["platform_operation_provider"]
        if (
            not IDENTIFIER.fullmatch(str(control.get("control_id", "")))
            or not IDENTIFIER.fullmatch(str(control.get("idempotency_key", "")))
            or control.get("operator_id") != provider["operator_id"]
            or not isinstance(control.get("reason"), str)
            or not control["reason"].strip()
            or len(control["reason"]) > 1024
        ):
            raise ProviderError(403, "platform_provider_control_invalid", "Platform control binding is invalid.")
        try:
            datetime.fromisoformat(str(control["requested_at"]).replace("Z", "+00:00"))
        except ValueError:
            raise ProviderError(400, "platform_provider_control_invalid", "Platform control time is invalid.") from None
        command_id = self._command_for_operation(operation_id_value)
        with self.store.lock(command_id):
            record = self.store.read(command_id)
            assert record is not None
            if reconcile_worker(record):
                self.store.write(record)
            controls = record.setdefault("controls", {})
            key = str(control.get("idempotency_key", ""))
            digest = canonical_digest(control)
            if not IDENTIFIER.fullmatch(key):
                raise ProviderError(400, "platform_provider_control_invalid", "Control idempotency key is invalid.")
            if key in controls:
                if controls[key] != digest:
                    raise ProviderError(409, "platform_provider_control_conflict", "Control identity is already bound to another intent.")
                return projection(record)
            controls[key] = digest
            if control["action"] == "retry":
                if record["state"] not in {"failed", "blocked"} or not record["retryable"]:
                    raise ProviderError(409, "platform_provider_retry_unavailable", "Retry is unavailable for this operation.")
                record.update({
                    "attempt": record["attempt"] + 1,
                    "retryable": False,
                    "cancel_available": record["command"]["action"] not in source_credentials.ACTION_SET,
                    "failure": None,
                    "blocker": None,
                    "receipt": None,
                    "worker": None,
                })
                event(record, "queued", "Platform accepted the exact retry control.")
                self.store.write(record)
                spawn_worker(self.store, record, self.policy_path)
                return projection(record)
            if record["state"] not in {"queued", "running"} or not record["cancel_available"]:
                raise ProviderError(409, "platform_provider_cancel_unavailable", "Cancellation is unavailable for this operation.")
            worker = record.get("worker") or {}
            pid = worker.get("pid")
            if worker_is_current(worker) and isinstance(pid, int):
                try:
                    os.killpg(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            else:
                raise ProviderError(409, "platform_provider_cancel_identity_lost", "Cancellation requires the exact current worker identity.")
            record["cancel_available"] = False
            record["retryable"] = False
            record["receipt"] = terminal_receipt(record, "cancelled", "partial")
            event(record, "cancelled", "Platform cancelled the owner operation; retained effects require inspection.")
            self.store.write(record)
            return projection(record)

    def _command_for_operation(self, operation_id_value: str) -> str:
        for path in self.store.operations.glob("*.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("operation_id") == operation_id_value:
                return value["command"]["command_id"]
        raise ProviderError(404, "platform_provider_operation_not_found", "Platform operation was not found.")


def activation_is_current(policy: dict[str, Any], source_version: str) -> bool:
    path = Path(policy["runtime_state_root"]) / "active.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    expected = {
        "schema_version": 1,
        "platform_revision": source_version,
        "platform_tree": git_tree(),
        "security_decision_digest": policy["security"]["decision_digest"],
        "security_decision_uri": policy["security"]["decision_uri"],
    }
    if not isinstance(value, dict) or set(value) != {*expected, "activated_at"}:
        return False
    try:
        datetime.fromisoformat(str(value["activated_at"]).replace("Z", "+00:00"))
    except ValueError:
        return False
    return all(value.get(key) == expected_value for key, expected_value in expected.items())


def handler_for(service: ProviderService, caller_id: str, caller_secret: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "platform-operation-provider/1"

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def authenticated(self) -> bool:
            observed_id = self.headers.get("x-platform-caller-id", "")
            observed_secret = self.headers.get("x-platform-caller-secret", "")
            return hmac.compare_digest(observed_id, caller_id) and hmac.compare_digest(observed_secret, caller_secret)

        def body(self) -> Any:
            try:
                length = int(self.headers.get("content-length", "0"))
            except ValueError:
                raise ProviderError(400, "platform_provider_request_invalid", "Request length is invalid.") from None
            if length < 0 or length > 524_288:
                raise ProviderError(413, "platform_provider_request_too_large", "Request is too large.")
            try:
                return json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                raise ProviderError(400, "platform_provider_request_invalid", "Request body is invalid JSON.") from None

        def respond(self, status: int, value: dict[str, Any]) -> None:
            encoded = canonical_bytes(value)
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(encoded)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def dispatch(self) -> None:
            try:
                if not self.authenticated():
                    raise ProviderError(403, "platform_provider_forbidden", "Platform provider caller is not admitted.")
                path = urlparse(self.path).path
                if self.command == "GET" and path == "/v1/console-operations/catalog":
                    self.respond(200, service.catalog())
                    return
                prefix = "/v1/console-operations/by-command/"
                if self.command == "GET" and path.startswith(prefix):
                    self.respond(200, service.read(unquote(path.removeprefix(prefix))))
                    return
                if self.command == "POST" and path == "/v1/console-operations/commands":
                    status, value = service.submit(self.body())
                    self.respond(status, value)
                    return
                control = re.fullmatch(r"/v1/console-operations/([^/]+)/controls", path)
                if self.command == "POST" and control:
                    self.respond(200, service.control(unquote(control.group(1)), self.body()))
                    return
                raise ProviderError(404, "platform_provider_route_not_found", "Platform provider route was not found.")
            except ProviderError as exc:
                self.respond(exc.status, {"code": exc.code, "message": str(exc)})
            except Exception:
                self.respond(500, {"code": "platform_provider_internal_error", "message": "Platform provider failed safely."})

        do_GET = dispatch
        do_POST = dispatch

    return Handler


def serve(policy_path: Path, state_root: Path, listen_host: str, listen_port: int) -> int:
    policy = load_policy(policy_path)
    source_version = git_head()
    require_security_activation(policy, source_version)
    secret = os.environ.get("PLATFORM_OPERATION_PROVIDER_CALLER_SECRET", "")
    caller_id = policy["platform_operation_provider"]["caller_id"]
    if len(secret) < 32:
        raise ProviderError(503, "platform_provider_credential_missing", "Platform provider credential is unavailable.")
    service = ProviderService(policy, policy_path, OperationStore(state_root), source_version)
    server = ThreadingHTTPServer((listen_host, listen_port), handler_for(service, caller_id, secret))
    server.serve_forever()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--state-root", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="action", required=True)
    server = subparsers.add_parser("serve")
    server.add_argument("--listen-host", required=True)
    server.add_argument("--listen-port", type=int, required=True)
    worker = subparsers.add_parser("worker")
    worker.add_argument("command_id")
    args = parser.parse_args()
    try:
        policy = load_policy(args.policy)
        if args.action == "worker":
            return execute_worker(OperationStore(args.state_root), policy, args.command_id)
        return serve(args.policy, args.state_root, args.listen_host, args.listen_port)
    except ProviderError as exc:
        print(f"Platform provider failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
