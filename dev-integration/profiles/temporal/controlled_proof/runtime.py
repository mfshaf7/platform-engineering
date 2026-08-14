from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import stat
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Protocol
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import quote, urlsplit

import yaml

from .authority import (
    ContractSet,
    GitSourceResolver,
    LocalBaselineProbe,
    SourceResolver,
    authorization_storage_key,
    consumption_receipt_path,
    controlled_runtime_state_root,
    load_contracts,
    release_execution_scope_lease,
    validate_authorization,
    validate_execution_scope_lease,
    validate_runtime_bindings,
    validate_vendored_contracts,
)
from .execution import (
    ExecutionDriver,
    ProjectedContexts,
    ScenarioExecutionResult,
    create_platform_receipt,
    validate_consumption_binding,
    validate_execution_claim_binding,
    validate_owner_receipt,
)
from .model import (
    MAX_ARTIFACT_BYTES,
    TERMINAL_CLEANUP_START_RESERVE_SECONDS,
    ControlledProofError,
    canonical_digest,
    controlled_subprocess_environment,
    decode_bounded_json,
    normalize_digest,
    now_utc,
    operator_scope_id,
    operator_scoped_dns_label,
    parse_timestamp,
    read_bounded_json,
    resolve_controlled_command,
    write_json_atomic,
)

PROFILE_ROOT = Path(__file__).resolve().parents[1]
OOS_API_DEPLOYMENT = "controlled-proof-oos-api"
OOS_WORKER_DEPLOYMENT = "controlled-proof-oos-worker"
WGCF_WORKER_DEPLOYMENT = "controlled-proof-wgcf-worker"
OOS_API_SERVICE = "controlled-proof-oos-api"
TEMPORAL_ADMIN_DEPLOYMENT = "temporal-admintools"
TEMPORAL_POLLER_READY_TIMEOUT_SECONDS = 60
EXTERNAL_EVIDENCE_KINDS = {
    "workflow-worker-restart": "workflow-worker-restart-observed",
    "temporal-runtime-restart": "temporal-runtime-restart-observed",
    "deterministic-replay": "deterministic-replay-verified",
    "duplicate-suppression": "duplicate-suppression-verified",
    "backup-restore": "backup-restore-verified",
}
TERMINAL_STATES = {"cancelled", "completed", "failed"}
RUNTIME_SCRIPT_ACTIONS = {
    "prepare",
    "restart-temporal",
    "backup-restore",
    "restore-baseline",
    "cleanup",
}
RUNTIME_FAILURE_PHASES = {
    "authorization-validation",
    "prerequisite-validation",
    "baseline-validation",
    "runtime-render",
    "chart-acquisition",
    "namespace-create",
    "namespace-label",
    "database-secret",
    "postgresql-apply",
    "network-boundary-apply",
    "postgresql-readiness",
    "temporal-install",
    "runtime-readiness",
    "temporal-suspend",
    "temporal-resume",
    "backup-create",
    "backup-restore",
    "runtime-remove",
    "baseline-verification",
}
RUNTIME_FAILURE_MARKER_RE = re.compile(
    r"^controlled-proof-runtime-failure:v1 "
    r"action=([a-z-]+) phase=([a-z-]+) exit_code=([1-9][0-9]{0,2})$"
)
TERMINAL_CLEANUP_ACTIONS = {"restore-baseline", "cleanup"}
WGCF_RECEIPT_PREFIX = "wgcf-controlled-proof://receipts/"
WGCF_RECEIPT_KEY_RE = re.compile(r"^[0-9a-f]{64}$")
PERMIT_BOUND_EXECUTOR_TREE = PurePosixPath("dev-integration/profiles/temporal")
# Bubblewrap mounts a private tmpfs at this namespace-local path.
SANDBOX_TEMP_ROOT = "/tmp"  # nosec B108
SANDBOX_HOME = f"{SANDBOX_TEMP_ROOT}/controlled-proof-home"


class _NoRedirectHandler(urlrequest.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl
        return None


LOCAL_HTTP_OPENER = urlrequest.build_opener(
    urlrequest.ProxyHandler({}),
    _NoRedirectHandler(),
)


def _local_api_endpoint(api_url: str, path: str) -> str:
    try:
        parsed = urlsplit(api_url)
        port = parsed.port
    except ValueError as exc:
        raise ControlledProofError("OOS API loopback endpoint is invalid") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or not path.startswith("/")
        or path.startswith("//")
    ):
        raise ControlledProofError("OOS API endpoint must remain fixed to loopback HTTP")
    return f"http://127.0.0.1:{port}{path}"


def _task_queue_poller_identities(payload: dict[str, Any]) -> set[str]:
    pollers = payload.get("pollers")
    if pollers is None:
        return set()
    if not isinstance(pollers, list):
        raise ControlledProofError("Temporal task-queue pollers are invalid")
    identities: set[str] = set()
    for poller in pollers:
        if not isinstance(poller, dict):
            raise ControlledProofError("Temporal task-queue poller is invalid")
        identity = poller.get("identity")
        if not isinstance(identity, str) or not identity.strip():
            raise ControlledProofError("Temporal task-queue poller identity is invalid")
        identities.add(identity.strip())
    return identities


def _controlled_request_operation(method: str, path: str) -> str:
    root = "/v1/orchestration/controlled-proof/executions"
    if method == "POST" and path == root:
        return "start-controlled-proof-execution"
    if method == "GET" and path.startswith(f"{root}/"):
        return "read-controlled-proof-execution"
    if method == "POST" and path.startswith(f"{root}/") and path.endswith(
        "/controls"
    ):
        return "control-controlled-proof-execution"
    return "unknown-controlled-proof-request"


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


@dataclass(frozen=True)
class RuntimeArtifactBindings:
    authorization_path: Path
    authorization_digest: str
    operator_approval_path: Path
    security_approval_path: Path
    baseline_path: Path
    baseline_evidence_root: Path
    consumption_receipt_path: Path
    consumption_receipt_digest: str
    execution_claim_path: Path
    execution_claim_digest: str


class CommandRunner(Protocol):
    def run(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
        input_text: str | None = None,
        pass_fds: tuple[int, ...] = (),
        timeout: float = 600,
    ) -> CommandResult: ...


class SubprocessCommandRunner:
    def run(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
        input_text: str | None = None,
        pass_fds: tuple[int, ...] = (),
        timeout: float = 600,
    ) -> CommandResult:
        effective_environment = env or controlled_subprocess_environment()
        completed = subprocess.run(
            resolve_controlled_command(
                command,
                environment=effective_environment,
            ),
            check=False,
            capture_output=True,
            env=effective_environment,
            input=input_text,
            pass_fds=pass_fds,
            text=True,
            timeout=timeout,
        )
        return CommandResult(
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
            returncode=completed.returncode,
        )


def validate_runtime_action_binding(
    *,
    action: str,
    workspace_root: Path,
    bindings: RuntimeArtifactBindings,
    output_root: Path,
    kubernetes_namespace: str,
    temporal_namespace: str,
    state_root: Path,
    operator_scope: str,
    source_resolver: SourceResolver | None = None,
) -> None:
    """Revalidate the complete consumed authority before any shell mutation."""

    if action not in RUNTIME_SCRIPT_ACTIONS:
        raise ControlledProofError("controlled runtime action is not permitted")
    workspace_root = workspace_root.expanduser().resolve()
    output_root = output_root.expanduser().resolve()
    contracts = load_contracts()
    authorization = read_bounded_json(
        bindings.authorization_path,
        expected_digest=bindings.authorization_digest,
    )
    validate_authorization(
        authorization,
        contracts=contracts,
        baseline_path=bindings.baseline_path,
        baseline_evidence_root=bindings.baseline_evidence_root,
        source_resolver=source_resolver or GitSourceResolver(workspace_root),
        operator_approval_path=bindings.operator_approval_path,
        security_approval_path=bindings.security_approval_path,
        allow_terminal_cleanup=action in TERMINAL_CLEANUP_ACTIONS,
    )
    consumption_receipt = read_bounded_json(
        bindings.consumption_receipt_path,
        expected_digest=bindings.consumption_receipt_digest,
    )
    expected_consumption_path = consumption_receipt_path(
        authorization["authorization_id"],
        workspace_root
        / "platform-engineering"
        / ".platform-drills"
        / "_controlled-proof-consumptions",
    )
    if bindings.consumption_receipt_path.expanduser().resolve() != expected_consumption_path:
        raise ControlledProofError(
            "runtime action requires the canonical permit-consumption receipt"
        )
    validate_consumption_binding(
        authorization,
        bindings.authorization_digest,
        consumption_receipt,
        bindings.consumption_receipt_digest,
        contracts,
    )

    execution_claim = read_bounded_json(
        bindings.execution_claim_path,
        expected_digest=bindings.execution_claim_digest,
    )
    expected_execution_path = (
        workspace_root
        / "platform-engineering"
        / ".platform-drills"
        / "_controlled-proof-executions"
        / f"{authorization_storage_key(authorization['authorization_id'])}.json"
    ).resolve()
    if bindings.execution_claim_path.expanduser().resolve() != expected_execution_path:
        raise ControlledProofError(
            "runtime action requires the canonical single-use execution claim"
        )
    validate_execution_claim_binding(
        authorization=authorization,
        authorization_digest=bindings.authorization_digest,
        consumption_receipt=consumption_receipt,
        consumption_receipt_digest=bindings.consumption_receipt_digest,
        execution_claim=execution_claim,
        execution_claim_digest=bindings.execution_claim_digest,
        output_root=output_root,
        operator_scope=operator_scope,
    )
    validate_execution_scope_lease(
        authorization=authorization,
        authorization_digest=bindings.authorization_digest,
        consumption_receipt=consumption_receipt,
        consumption_receipt_digest=bindings.consumption_receipt_digest,
        execution_claim=execution_claim,
        output_root=output_root,
        operator_scope=operator_scope,
        lease_root=(
            workspace_root
            / "platform-engineering"
            / ".platform-drills"
            / "_controlled-proof-scope-leases"
        ),
    )

    baseline = read_bounded_json(
        bindings.baseline_path,
        expected_digest=authorization["baseline_and_restore"][
            "baseline_snapshot_digest"
        ],
    )
    operator_id = baseline["operator_id"]
    expected_scope = {
        "kubernetes_namespace": _kubernetes_namespace(operator_id),
        "temporal_namespace": authorization["scope"]["target_namespaces"][0],
        "state_root": str(controlled_runtime_state_root(workspace_root, operator_id)),
        "operator_scope": operator_scope_id(operator_id),
    }
    actual_scope = {
        "kubernetes_namespace": kubernetes_namespace,
        "temporal_namespace": temporal_namespace,
        "state_root": str(state_root.expanduser().resolve()),
        "operator_scope": operator_scope,
    }
    mismatched = [
        key for key, expected in expected_scope.items() if actual_scope[key] != expected
    ]
    if mismatched:
        raise ControlledProofError(
            "runtime action scope does not match its authorization: "
            + ", ".join(mismatched)
        )


class RuntimeControl(Protocol):
    def assert_current(self) -> None: ...

    def prepare(self, contexts: ProjectedContexts) -> None: ...

    def start(self, scenario_execution_id: str) -> dict[str, Any]: ...

    def get(self, run_id: str) -> dict[str, Any]: ...

    def signal(
        self,
        *,
        run_id: str,
        scenario: dict[str, Any],
        evidence_kind: str,
        evidence_ref: dict[str, str],
        observed_at: str,
    ) -> dict[str, Any]: ...

    def cancel(self, *, run_id: str, scenario: dict[str, Any]) -> dict[str, Any]: ...

    def restart_oos_worker(self) -> None: ...

    def restart_temporal(self) -> None: ...

    def backup_restore(self) -> None: ...

    def load_wgcf_receipt(self, oos_receipt: dict[str, Any]) -> dict[str, Any]: ...

    def restore_baseline(self, baseline: dict[str, Any]) -> dict[str, str]: ...

    def cleanup(self) -> None: ...


class ControlledRuntimeDriver(ExecutionDriver):
    """Translate the fixed scenario set into bounded runtime-control calls."""

    def __init__(
        self,
        *,
        authorization: dict[str, Any],
        authorization_digest: str,
        contracts: ContractSet,
        control: RuntimeControl,
        output_root: Path,
    ):
        self.authorization = authorization
        self.authorization_digest = authorization_digest
        self.contracts = contracts
        self.control = control
        self.output_root = output_root.resolve()

    def prepare(self, contexts: ProjectedContexts) -> None:
        self.control.prepare(contexts)

    def execute_scenario(
        self,
        scenario: dict[str, Any],
        contexts: ProjectedContexts,
    ) -> ScenarioExecutionResult:
        del contexts
        self.control.assert_current()
        started_at = now_utc()
        start = self.control.start(scenario["scenario_execution_id"])
        run_id = _required_text(start, "run_id")
        scenario_id = scenario["scenario_id"]

        external_evidence: dict[str, str] | None = None
        if scenario_id == "duplicate-suppression":
            duplicate = self.control.start(scenario["scenario_execution_id"])
            if duplicate.get("duplicate") is not True or duplicate.get("run_id") != run_id:
                raise ControlledProofError(
                    "duplicate-suppression did not retain one immutable workflow run"
                )
            external_evidence = self._record_action(
                scenario,
                "duplicate-start-suppressed",
                {"run_id": run_id},
            )

        if scenario_id == "cancellation":
            self._wait_for_state(run_id, {"running"})
            terminal = self.control.cancel(run_id=run_id, scenario=scenario)
        elif scenario_id in EXTERNAL_EVIDENCE_KINDS:
            waiting = self._wait_for_state(run_id, {"waiting"})
            if scenario_id == "workflow-worker-restart":
                self.control.restart_oos_worker()
                action = "oos-workflow-worker-restarted"
            elif scenario_id == "temporal-runtime-restart":
                self.control.restart_temporal()
                action = "temporal-runtime-restarted"
            elif scenario_id == "deterministic-replay":
                before = canonical_digest(waiting["projection"])
                self.control.restart_oos_worker()
                after = canonical_digest(self.control.get(run_id)["projection"])
                if before != after:
                    raise ControlledProofError(
                        "deterministic replay changed the retained run projection"
                    )
                action = "deterministic-replay-verified"
            elif scenario_id == "backup-restore":
                self.control.backup_restore()
                action = "temporal-backup-restored"
            else:
                action = "duplicate-start-suppressed"
            external_evidence = external_evidence or self._record_action(
                scenario,
                action,
                {"run_id": run_id},
            )
            terminal = self.control.signal(
                run_id=run_id,
                scenario=scenario,
                evidence_kind=EXTERNAL_EVIDENCE_KINDS[scenario_id],
                evidence_ref=external_evidence,
                observed_at=now_utc(),
            )
        else:
            terminal = self._wait_for_state(run_id, TERMINAL_STATES)

        if terminal.get("owner_receipt") is None:
            terminal = self._wait_for_state(run_id, TERMINAL_STATES)
        projection = terminal.get("projection")
        oos_receipt = terminal.get("owner_receipt")
        if not isinstance(projection, dict) or not isinstance(oos_receipt, dict):
            raise ControlledProofError(
                f"{scenario_id} did not return terminal OOS evidence"
            )
        assertion = projection.get("scenario_assertion") or {}
        if assertion.get("status") != "passed" or oos_receipt.get("owner_result") != "passed":
            raise ControlledProofError(
                f"{scenario_id} did not satisfy its authorized scenario assertion"
            )
        validate_owner_receipt(
            oos_receipt,
            authorization=self.authorization,
            authorization_digest=self.authorization_digest,
            scenario=scenario,
            expected_status="passed",
            contracts=self.contracts,
        )
        wgcf_receipt = self.control.load_wgcf_receipt(oos_receipt)
        if wgcf_receipt.get("owner_result") != "passed":
            raise ControlledProofError(f"{scenario_id} has no passing WGCF receipt")
        validate_owner_receipt(
            wgcf_receipt,
            authorization=self.authorization,
            authorization_digest=self.authorization_digest,
            scenario=scenario,
            expected_status="passed",
            contracts=self.contracts,
        )

        final_evidence = self._record_action(
            scenario,
            "scenario-terminal-assertion",
            {
                "run_id": run_id,
                "state": projection.get("state"),
                "scenario_assertion": assertion.get("status"),
                "oos_receipt_digest": oos_receipt.get("receipt_digest"),
                "wgcf_receipt_digest": wgcf_receipt.get("receipt_digest"),
            },
        )
        completed_at = _required_text(projection, "completed_at")
        self.control.assert_current()
        platform_receipt = create_platform_receipt(
            authorization=self.authorization,
            authorization_digest=self.authorization_digest,
            scenario=scenario,
            owner_result="passed",
            evidence_refs=[external_evidence, final_evidence]
            if external_evidence
            else [final_evidence],
            execution_id=f"platform-action:{scenario['scenario_execution_id']}",
            recorded_at=completed_at,
            contracts=self.contracts,
        )
        return ScenarioExecutionResult(
            status="passed",
            evidence_refs=[final_evidence],
            owner_receipts=[platform_receipt, oos_receipt, wgcf_receipt],
            started_at=started_at,
            completed_at=completed_at,
        )

    def restore_exact_baseline(
        self,
        scenario: dict[str, Any],
        contexts: ProjectedContexts,
        baseline: dict[str, Any],
    ) -> ScenarioExecutionResult:
        del contexts
        started_at = now_utc()
        evidence = self.control.restore_baseline(baseline)
        completed_at = now_utc()
        receipt = create_platform_receipt(
            authorization=self.authorization,
            authorization_digest=self.authorization_digest,
            scenario=scenario,
            owner_result="passed",
            evidence_refs=[evidence],
            execution_id=f"platform-action:{scenario['scenario_execution_id']}",
            recorded_at=completed_at,
            contracts=self.contracts,
        )
        return ScenarioExecutionResult(
            status="passed",
            evidence_refs=[evidence],
            owner_receipts=[receipt],
            started_at=started_at,
            completed_at=completed_at,
        )

    def cleanup(self, contexts: ProjectedContexts) -> None:
        del contexts
        self.control.cleanup()

    def _wait_for_state(
        self,
        run_id: str,
        states: set[str],
        *,
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            current = self.control.get(run_id)
            projection = current.get("projection") or {}
            if projection.get("state") in states:
                if projection.get("state") in TERMINAL_STATES and current.get(
                    "owner_receipt"
                ) is None:
                    time.sleep(0.5)
                    continue
                return current
            time.sleep(0.5)
        raise ControlledProofError(
            f"controlled proof run did not reach one of {sorted(states)}"
        )

    def _record_action(
        self,
        scenario: dict[str, Any],
        action: str,
        detail: dict[str, Any],
    ) -> dict[str, str]:
        payload = {
            "schema_version": 1,
            "authorization_id": self.authorization["authorization_id"],
            "commissioning_session_id": self.authorization["commissioning_session"][
                "commissioning_session_id"
            ],
            "scenario_id": scenario["scenario_id"],
            "scenario_execution_id": scenario["scenario_execution_id"],
            "action": action,
            "detail": detail,
            "recorded_at": now_utc(),
        }
        path = (
            self.output_root
            / "scenario-evidence"
            / f"{scenario['scenario_id']}-{action}.json"
        )
        digest = write_json_atomic(path, payload)
        return {
            "artifact_ref": (
                "platform-controlled-proof://scenario-evidence/"
                f"{scenario['scenario_execution_id']}/{action}"
            ),
            "artifact_digest": digest,
        }


class LocalK3sRuntimeControl:
    """Concrete local-k3s adapter for the reviewed commissioning path."""

    def __init__(
        self,
        *,
        authorization: dict[str, Any],
        baseline: dict[str, Any],
        contexts: ProjectedContexts | None,
        artifacts: RuntimeArtifactBindings,
        output_root: Path,
        workspace_root: Path,
        runner: CommandRunner | None = None,
    ):
        self.authorization = authorization
        self.baseline = baseline
        self.contexts = contexts
        self.artifacts = artifacts
        self.consumption_receipt_digest = artifacts.consumption_receipt_digest
        self.output_root = output_root.resolve()
        self.workspace_root = workspace_root.resolve()
        self.runner = runner or SubprocessCommandRunner()
        self.operator_id = baseline["operator_id"]
        self.operator_scope = operator_scope_id(self.operator_id)
        self.kubernetes_namespace = _kubernetes_namespace(self.operator_id)
        self.temporal_namespace = authorization["scope"]["target_namespaces"][0]
        self.state_root = controlled_runtime_state_root(
            self.workspace_root,
            self.operator_id,
        )
        self.api_secret = secrets.token_hex(32)
        self.api_url = ""
        self.port_forward: subprocess.Popen[str] | None = None
        self.restored = False
        self.execution_scope_lease_root = (
            self.workspace_root
            / "platform-engineering"
            / ".platform-drills"
            / "_controlled-proof-scope-leases"
        )
        self.consumption_receipt = read_bounded_json(
            artifacts.consumption_receipt_path,
            expected_digest=artifacts.consumption_receipt_digest,
        )
        self.execution_claim = read_bounded_json(
            artifacts.execution_claim_path,
            expected_digest=artifacts.execution_claim_digest,
        )
        self.platform_executor_snapshot = (
            self.output_root
            / "runtime"
            / "source-snapshots"
            / "platform-engineering"
        )
        self.workspace_governance_snapshot = (
            self.output_root
            / "runtime"
            / "source-snapshots"
            / "workspace-governance"
        )

    def assert_current(self) -> None:
        self._assert_authorization_current()
        expected_sources = {
            item["repo"]: item["commit"]
            for item in self.authorization["scope"]["execution_source_revisions"]
        }
        resolver = GitSourceResolver(self.workspace_root)
        for repo, expected_revision in expected_sources.items():
            current_revision, dirty = resolver.revision(repo)
            if dirty or current_revision != expected_revision:
                raise ControlledProofError(
                    f"controlled proof source drifted during execution: {repo}"
                )
        validate_vendored_contracts()
        validate_runtime_bindings(self.authorization)

    def prepare(self, contexts: ProjectedContexts) -> None:
        if self.contexts is None or contexts != self.contexts:
            raise ControlledProofError("runtime contexts changed before preparation")
        self.assert_current()
        self._require_tools()
        self._prepare_platform_executor_snapshot()
        self._runtime_script("prepare")
        self._prepare_workspace_governance_snapshot()
        manifest = _owner_runtime_manifest(
            authorization=self.authorization,
            contexts=contexts,
            kubernetes_namespace=self.kubernetes_namespace,
            workspace_governance_source=self.workspace_governance_snapshot,
        )
        manifest_path = self.output_root / "runtime" / "owner-runtime.yaml"
        manifest_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        manifest_path.write_text(
            yaml.safe_dump_all(manifest, sort_keys=False), encoding="utf-8"
        )
        os.chmod(manifest_path, 0o600)
        self._run(
            ["k3s", "kubectl", "apply", "-f", "-"],
            input_text=_caller_secret_manifest(
                self.kubernetes_namespace, self.api_secret
            ),
        )
        self._run(["k3s", "kubectl", "apply", "-f", str(manifest_path)])
        for deployment in (
            OOS_API_DEPLOYMENT,
            OOS_WORKER_DEPLOYMENT,
            WGCF_WORKER_DEPLOYMENT,
        ):
            self._run(
                [
                    "k3s",
                    "kubectl",
                    "-n",
                    self.kubernetes_namespace,
                    "rollout",
                    "status",
                    f"deployment/{deployment}",
                    "--timeout=300s",
                ]
            )
        self._wait_for_temporal_pollers()
        self._start_port_forward()

    def _wait_for_temporal_pollers(
        self,
        *,
        timeout_seconds: float = TEMPORAL_POLLER_READY_TIMEOUT_SECONDS,
        poll_interval_seconds: float = 0.5,
    ) -> None:
        if self.contexts is None:
            raise ControlledProofError("controlled runtime owner contexts are unavailable")
        requirements = (
            {
                "task_queue_type": "workflow",
                "task_queue": self.contexts.oos["runtime"]["workflow_task_queue"],
                "expected_identity": self.contexts.oos["runtime"][
                    "workflow_worker_identity"
                ],
            },
            {
                "task_queue_type": "activity",
                "task_queue": self.contexts.wgcf["runtime"]["activity_task_queue"],
                "expected_identity": self.contexts.wgcf["runtime"]["worker_identity"],
            },
        )
        deadline = time.monotonic() + min(
            timeout_seconds,
            self._remaining_authorization_seconds(),
        )
        observations: dict[str, list[str]] = {}
        while True:
            pending = False
            for requirement in requirements:
                result = self._run(
                    [
                        "k3s",
                        "kubectl",
                        "-n",
                        self.kubernetes_namespace,
                        "exec",
                        f"deployment/{TEMPORAL_ADMIN_DEPLOYMENT}",
                        "--",
                        "temporal",
                        "task-queue",
                        "describe",
                        "--namespace",
                        self.temporal_namespace,
                        "--task-queue",
                        requirement["task_queue"],
                        "--task-queue-type",
                        requirement["task_queue_type"],
                        "--disable-stats",
                        "--output",
                        "json",
                    ],
                    timeout=15,
                )
                try:
                    payload = decode_bounded_json(
                        result.stdout.encode("utf-8"),
                        label="Temporal task-queue readiness",
                    )
                    identities = _task_queue_poller_identities(payload)
                except Exception as exc:
                    evidence = self._record_bounded_runtime_failure(
                        category="poller-readiness-failures",
                        detail={
                            "failure_kind": "invalid-task-queue-response",
                            "task_queue_type": requirement["task_queue_type"],
                            "task_queue_digest": "sha256:"
                            + hashlib.sha256(
                                requirement["task_queue"].encode("utf-8")
                            ).hexdigest(),
                            "stdout": {
                                "sha256": "sha256:"
                                + hashlib.sha256(
                                    result.stdout.encode("utf-8")
                                ).hexdigest(),
                                "bytes": len(result.stdout.encode("utf-8")),
                            },
                        },
                    )
                    raise ControlledProofError(
                        "Temporal poller readiness returned invalid bounded evidence",
                        evidence_refs=[evidence],
                    ) from exc
                observations[requirement["task_queue_type"]] = sorted(identities)
                expected = {requirement["expected_identity"]}
                if identities - expected:
                    evidence = self._record_bounded_runtime_failure(
                        category="poller-readiness-failures",
                        detail={
                            "failure_kind": "unexpected-poller-identity",
                            "task_queue_type": requirement["task_queue_type"],
                            "expected_identities": sorted(expected),
                            "observed_identities": sorted(identities),
                        },
                    )
                    raise ControlledProofError(
                        "Temporal task queue has an unadmitted poller identity",
                        evidence_refs=[evidence],
                    )
                if identities != expected:
                    pending = True
            if not pending:
                readiness = {
                    "schema_version": 1,
                    "authorization_id": self.authorization["authorization_id"],
                    "commissioning_session_id": self.authorization[
                        "commissioning_session"
                    ]["commissioning_session_id"],
                    "status": "ready",
                    "pollers": [
                        {
                            "task_queue_type": requirement["task_queue_type"],
                            "expected_identity": requirement["expected_identity"],
                            "observed_identities": observations[
                                requirement["task_queue_type"]
                            ],
                        }
                        for requirement in requirements
                    ],
                    "recorded_at": now_utc(),
                }
                write_json_atomic(
                    self.output_root / "runtime" / "temporal-poller-readiness.json",
                    readiness,
                )
                return
            if time.monotonic() >= deadline:
                evidence = self._record_bounded_runtime_failure(
                    category="poller-readiness-failures",
                    detail={
                        "failure_kind": "poller-readiness-timeout",
                        "requirements": [
                            {
                                "task_queue_type": requirement[
                                    "task_queue_type"
                                ],
                                "expected_identity": requirement[
                                    "expected_identity"
                                ],
                                "observed_identities": observations.get(
                                    requirement["task_queue_type"], []
                                ),
                            }
                            for requirement in requirements
                        ],
                    },
                )
                raise ControlledProofError(
                    "Temporal controlled-proof pollers did not become ready",
                    evidence_refs=[evidence],
                )
            time.sleep(min(poll_interval_seconds, max(deadline - time.monotonic(), 0)))

    def start(self, scenario_execution_id: str) -> dict[str, Any]:
        self.assert_current()
        return self._request(
            "POST",
            "/v1/orchestration/controlled-proof/executions",
            {"schema_version": 1, "scenario_execution_id": scenario_execution_id},
        )

    def get(self, run_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            (
                "/v1/orchestration/controlled-proof/executions/"
                f"{quote(run_id, safe='')}"
            ),
        )

    def signal(
        self,
        *,
        run_id: str,
        scenario: dict[str, Any],
        evidence_kind: str,
        evidence_ref: dict[str, str],
        observed_at: str,
    ) -> dict[str, Any]:
        self.assert_current()
        return self._control(
            run_id=run_id,
            scenario=scenario,
            action="signal",
            evidence={
                "evidence_kind": evidence_kind,
                "evidence_refs": [evidence_ref],
                "observed_at": observed_at,
            },
        )

    def cancel(self, *, run_id: str, scenario: dict[str, Any]) -> dict[str, Any]:
        self.assert_current()
        return self._control(
            run_id=run_id,
            scenario=scenario,
            action="cancel",
            evidence=None,
        )

    def restart_oos_worker(self) -> None:
        self.assert_current()
        self._restart_deployment(OOS_WORKER_DEPLOYMENT)

    def restart_temporal(self) -> None:
        self.assert_current()
        self._runtime_script("restart-temporal")

    def backup_restore(self) -> None:
        self.assert_current()
        self._runtime_script("backup-restore")

    def load_wgcf_receipt(self, oos_receipt: dict[str, Any]) -> dict[str, Any]:
        self.assert_current()
        receipt_id, receipt_ref, expected_digest = _wgcf_receipt_binding(oos_receipt)
        receipt_path = (
            "/var/lib/wgcf/orchestration/controlled-proof/receipts/"
            f"{receipt_id}.json"
        )
        result = self._run(
            [
                "k3s",
                "kubectl",
                "-n",
                self.kubernetes_namespace,
                "exec",
                f"deployment/{WGCF_WORKER_DEPLOYMENT}",
                "--",
                "cat",
                receipt_path,
            ]
        )
        receipt = decode_bounded_json(
            result.stdout.encode("utf-8"),
            label="WGCF receipt",
        )
        _validate_loaded_wgcf_receipt(
            receipt,
            receipt_ref=receipt_ref,
            expected_digest=expected_digest,
        )
        local_path = (
            self.output_root / "owner-receipts" / f"wgcf-{receipt_id}.json"
        )
        write_json_atomic(local_path, receipt)
        return read_bounded_json(local_path)

    def restore_baseline(self, baseline: dict[str, Any]) -> dict[str, str]:
        if baseline != self.baseline:
            raise ControlledProofError("restore baseline changed after permit validation")
        self._stop_port_forward()
        if self.platform_executor_snapshot.exists():
            self._runtime_script("restore-baseline", allow_expired=True)
        restored = self._verify_baseline(baseline)
        payload = {
            "schema_version": 1,
            "authorization_id": self.authorization["authorization_id"],
            "baseline_snapshot_ref": baseline["baseline_id"],
            "restored_surfaces": restored,
            "restored_at": now_utc(),
        }
        path = self.output_root / "restore" / "exact-baseline-restore.json"
        digest = write_json_atomic(path, payload)
        self.restored = True
        return {
            "artifact_ref": (
                "platform-controlled-proof://restore/"
                f"{self.authorization['commissioning_session']['commissioning_session_id']}"
            ),
            "artifact_digest": digest,
        }

    def _verify_baseline(self, baseline: dict[str, Any]) -> list[dict[str, str]]:
        probe = LocalBaselineProbe(self.workspace_root, self.operator_id)
        restored: list[dict[str, str]] = []
        expected = {
            item["surface_id"]: item for item in baseline["surface_observations"]
        }
        for surface_id, expected_item in expected.items():
            state, observation = probe.capture(surface_id)
            if state != expected_item["state"]:
                raise ControlledProofError(
                    f"exact baseline restore did not recover {surface_id}"
                )
            observation_digest = canonical_digest(observation)
            if observation_digest != expected_item["observation_digest"]:
                raise ControlledProofError(
                    f"exact baseline restore observation drifted for {surface_id}"
                )
            restored.append(
                {
                    "surface_id": surface_id,
                    "state": state,
                    "observation_digest": observation_digest,
                }
            )
        return restored

    def cleanup(self) -> list[dict[str, str]]:
        self._stop_port_forward()
        if not self.restored and self.platform_executor_snapshot.exists():
            self._runtime_script("cleanup", allow_expired=True)
        restored = self._verify_baseline(self.baseline)
        release_execution_scope_lease(
            authorization=self.authorization,
            authorization_digest=self.artifacts.authorization_digest,
            consumption_receipt=self.consumption_receipt,
            consumption_receipt_digest=self.artifacts.consumption_receipt_digest,
            execution_claim=self.execution_claim,
            output_root=self.output_root,
            operator_scope=self.operator_scope,
            lease_root=self.execution_scope_lease_root,
        )
        if self.workspace_governance_snapshot.parent.exists():
            shutil.rmtree(self.workspace_governance_snapshot.parent, ignore_errors=True)
        return restored

    def _control(
        self,
        *,
        run_id: str,
        scenario: dict[str, Any],
        action: str,
        evidence: dict[str, Any] | None,
    ) -> dict[str, Any]:
        execution_id = scenario["scenario_execution_id"]
        return self._request(
            "POST",
            (
                "/v1/orchestration/controlled-proof/executions/"
                f"{quote(run_id, safe='')}/controls"
            ),
            {
                "schema_version": 1,
                "commissioning_session_id": self.authorization[
                    "commissioning_session"
                ]["commissioning_session_id"],
                "scenario_execution_id": execution_id,
                "control": {
                    "schema_version": 1,
                    "control_id": f"control:platform:{execution_id}:{action}",
                    "action": action,
                    "operator_id": self.operator_id,
                    "reason_ref": f"policy:controlled-proof:{scenario['scenario_id']}",
                    "idempotency_key": f"idempotency:platform:{execution_id}:{action}",
                },
                "scenario_evidence": evidence,
            },
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._assert_authorization_current()
        if not self.api_url:
            raise ControlledProofError("OOS controlled-proof API is unavailable")
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urlrequest.Request(
            _local_api_endpoint(self.api_url, path),
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-OOS-Caller-Id": "platform-controlled-proof-executor",
                "X-OOS-Caller-Secret": self.api_secret,
            },
        )
        try:
            with LOCAL_HTTP_OPENER.open(
                request,
                timeout=min(15.0, self._remaining_authorization_seconds()),
            ) as response:
                raw = response.read(MAX_ARTIFACT_BYTES + 1)
        except urlerror.HTTPError as exc:
            raw = exc.read(MAX_ARTIFACT_BYTES + 1)
            response_error = None
            try:
                candidate = decode_bounded_json(
                    raw,
                    label="OOS controlled-proof error response",
                )
                value = candidate.get("error")
                if isinstance(value, str) and re.fullmatch(r"[a-z0-9_]{1,96}", value):
                    response_error = value
            except Exception:
                pass
            evidence = self._record_bounded_runtime_failure(
                category="request-failures",
                detail={
                    "failure_kind": "http-error",
                    "operation": _controlled_request_operation(method, path),
                    "http_status": exc.code,
                    "response_error": response_error,
                    "response": {
                        "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                        "bytes": len(raw),
                    },
                },
            )
            raise ControlledProofError(
                "OOS controlled-proof request failed; bounded failure evidence was recorded",
                evidence_refs=[evidence],
            ) from exc
        except (urlerror.URLError, TimeoutError) as exc:
            evidence = self._record_bounded_runtime_failure(
                category="request-failures",
                detail={
                    "failure_kind": "transport-error",
                    "operation": _controlled_request_operation(method, path),
                    "transport_error_type": exc.__class__.__name__,
                },
            )
            raise ControlledProofError(
                "OOS controlled-proof request failed; bounded failure evidence was recorded",
                evidence_refs=[evidence],
            ) from exc
        try:
            result = decode_bounded_json(raw, label="OOS controlled-proof response")
        except Exception as exc:
            evidence = self._record_bounded_runtime_failure(
                category="request-failures",
                detail={
                    "failure_kind": "invalid-response",
                    "operation": _controlled_request_operation(method, path),
                    "response": {
                        "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                        "bytes": len(raw),
                    },
                },
            )
            raise ControlledProofError(
                "OOS controlled-proof response was invalid; bounded failure evidence was recorded",
                evidence_refs=[evidence],
            ) from exc
        return result

    def _record_bounded_runtime_failure(
        self,
        *,
        category: str,
        detail: dict[str, Any],
    ) -> dict[str, str]:
        recorded_at = now_utc()
        failure_key = hashlib.sha256(
            json.dumps(
                {"category": category, "detail": detail, "recorded_at": recorded_at},
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        payload = {
            "schema_version": 1,
            "authorization_id": self.authorization["authorization_id"],
            "commissioning_session_id": self.authorization[
                "commissioning_session"
            ]["commissioning_session_id"],
            **detail,
            "recorded_at": recorded_at,
        }
        path = self.output_root / "runtime" / category / f"{failure_key}.json"
        digest = write_json_atomic(path, payload)
        return {
            "artifact_ref": (
                f"platform-controlled-proof://runtime-{category}/{failure_key}"
            ),
            "artifact_digest": digest,
        }

    def _restart_deployment(self, deployment: str) -> None:
        self._run(
            [
                "k3s",
                "kubectl",
                "-n",
                self.kubernetes_namespace,
                "rollout",
                "restart",
                f"deployment/{deployment}",
            ]
        )
        self._run(
            [
                "k3s",
                "kubectl",
                "-n",
                self.kubernetes_namespace,
                "rollout",
                "status",
                f"deployment/{deployment}",
                "--timeout=300s",
            ]
        )

    def _runtime_script(self, action: str, *, allow_expired: bool = False) -> None:
        attested_files = self._assert_platform_executor_snapshot(
            allow_expired=allow_expired
        )
        runtime_script = (
            self.platform_executor_snapshot
            / "dev-integration"
            / "profiles"
            / "temporal"
            / "scripts"
            / "controlled-proof-runtime.sh"
        )
        env = {
            "CONTROLLED_PROOF_AUTHORIZATION_PATH": str(
                self.artifacts.authorization_path
            ),
            "CONTROLLED_PROOF_AUTHORIZATION_DIGEST": (
                self.artifacts.authorization_digest
            ),
            "CONTROLLED_PROOF_OPERATOR_APPROVAL_PATH": str(
                self.artifacts.operator_approval_path
            ),
            "CONTROLLED_PROOF_SECURITY_AUTHORIZATION_PATH": str(
                self.artifacts.security_approval_path
            ),
            "CONTROLLED_PROOF_BASELINE_PATH": str(self.artifacts.baseline_path),
            "CONTROLLED_PROOF_BASELINE_EVIDENCE_ROOT": str(
                self.artifacts.baseline_evidence_root
            ),
            "CONTROLLED_PROOF_CONSUMPTION_RECEIPT_PATH": str(
                self.artifacts.consumption_receipt_path
            ),
            "CONTROLLED_PROOF_CONSUMPTION_RECEIPT_DIGEST": (
                self.consumption_receipt_digest
            ),
            "CONTROLLED_PROOF_EXECUTION_CLAIM_PATH": str(
                self.artifacts.execution_claim_path
            ),
            "CONTROLLED_PROOF_EXECUTION_CLAIM_DIGEST": (
                self.artifacts.execution_claim_digest
            ),
            "CONTROLLED_PROOF_OUTPUT_ROOT": str(self.output_root),
            "CONTROLLED_PROOF_OPERATOR_SCOPE": self.operator_scope,
            "CONTROLLED_PROOF_WORKSPACE_ROOT": str(self.workspace_root),
            "HOME": SANDBOX_HOME,
            "PYTHONDONTWRITEBYTECODE": "1",
            "DEVINT_OPERATOR": self.operator_id,
            "DEVINT_PROFILE_ID": "temporal",
            "DEVINT_PROFILE_LIFECYCLE": "build-admitted",
            "DEVINT_NAMESPACE": self.kubernetes_namespace,
            "DEVINT_STATE_ROOT": str(self.state_root),
            "DEVINT_WORKSPACE_ROOT": str(
                self.workspace_root / "platform-engineering"
            ),
            "DEVINT_TEMPORAL_WORKFLOW_NAMESPACE": self.temporal_namespace,
            "DEVINT_KUBECONFIG": "/etc/rancher/k3s/k3s.yaml",
            "DEVINT_KUBECTL": "k3s kubectl",
        }
        with self._sealed_executor_files(attested_files) as sealed_files:
            self._run(
                self._sandboxed_runtime_command(
                    runtime_script=runtime_script,
                    action=action,
                    sealed_files=sealed_files,
                ),
                env=env,
                pass_fds=tuple(
                    descriptor for descriptor, _mode in sealed_files.values()
                ),
                timeout=900,
                allow_expired=allow_expired,
                expected_runtime_action=action,
            )

    def _prepare_platform_executor_snapshot(self) -> None:
        snapshot = self.platform_executor_snapshot
        if snapshot.exists() or snapshot.is_symlink():
            raise ControlledProofError("Platform executor source snapshot already exists")
        snapshot.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        source = self.workspace_root / "platform-engineering"
        expected_revision = self.authorization["executor"]["source_revision"]
        self._run(
            [
                "git",
                "clone",
                "--no-hardlinks",
                "--no-checkout",
                str(source),
                str(snapshot),
            ]
        )
        self._run(
            ["git", "-C", str(snapshot), "checkout", "--detach", expected_revision]
        )
        self._assert_platform_executor_snapshot()

    def _assert_platform_executor_snapshot(
        self, *, allow_expired: bool = False
    ) -> dict[PurePosixPath, tuple[bytes, int]]:
        snapshot = self.platform_executor_snapshot
        if not snapshot.is_dir() or snapshot.is_symlink():
            raise ControlledProofError("permit-bound Platform executor snapshot is unavailable")
        expected_revision = self.authorization["executor"]["source_revision"]
        head = self._run(
            ["git", "-C", str(snapshot), "rev-parse", "HEAD"],
            env={"GIT_NO_REPLACE_OBJECTS": "1"},
            allow_expired=allow_expired,
        ).stdout
        object_format = self._run(
            ["git", "-C", str(snapshot), "rev-parse", "--show-object-format"],
            env={"GIT_NO_REPLACE_OBJECTS": "1"},
            allow_expired=allow_expired,
        ).stdout
        self._run(
            [
                "git",
                "-C",
                str(snapshot),
                "fsck",
                "--strict",
                "--no-dangling",
                expected_revision,
            ],
            env={"GIT_NO_REPLACE_OBJECTS": "1"},
            allow_expired=allow_expired,
        )
        tree_listing = self._run(
            [
                "git",
                "-C",
                str(snapshot),
                "ls-tree",
                "-r",
                "--full-tree",
                expected_revision,
                "--",
                str(PERMIT_BOUND_EXECUTOR_TREE),
            ],
            env={"GIT_NO_REPLACE_OBJECTS": "1"},
            allow_expired=allow_expired,
        ).stdout
        status = self._run(
            [
                "git",
                "-C",
                str(snapshot),
                "status",
                "--short",
                "--untracked-files=all",
            ],
            env={"GIT_NO_REPLACE_OBJECTS": "1"},
            allow_expired=allow_expired,
        ).stdout
        if head != expected_revision or status:
            raise ControlledProofError(
                "permit-bound Platform executor snapshot changed during execution"
            )
        return self._assert_executor_tree_bytes(
            snapshot=snapshot,
            object_format=object_format,
            tree_listing=tree_listing,
        )

    @staticmethod
    def _assert_executor_tree_bytes(
        *,
        snapshot: Path,
        object_format: str,
        tree_listing: str,
    ) -> dict[PurePosixPath, tuple[bytes, int]]:
        if object_format not in {"sha1", "sha256"}:
            raise ControlledProofError("permit-bound Git object format is unsupported")

        expected_files: dict[PurePosixPath, tuple[str, str]] = {}
        for line in tree_listing.splitlines():
            metadata, separator, raw_path = line.partition("\t")
            fields = metadata.split()
            if separator != "\t" or len(fields) != 3:
                raise ControlledProofError("permit-bound executor tree is malformed")
            mode, object_type, object_id = fields
            relative = PurePosixPath(raw_path)
            if (
                object_type != "blob"
                or mode not in {"100644", "100755"}
                or relative.is_absolute()
                or ".." in relative.parts
                or not relative.is_relative_to(PERMIT_BOUND_EXECUTOR_TREE)
            ):
                raise ControlledProofError("permit-bound executor tree is outside policy")
            expected_files[relative] = (mode, object_id)
        if not expected_files:
            raise ControlledProofError("permit-bound executor tree is empty")

        snapshot_root = snapshot.resolve()
        profile_root = snapshot.joinpath(*PERMIT_BOUND_EXECUTOR_TREE.parts)
        current_path = snapshot
        for part in PERMIT_BOUND_EXECUTOR_TREE.parts:
            current_path /= part
            if current_path.is_symlink() or not current_path.is_dir():
                raise ControlledProofError(
                    "permit-bound executor tree contains an invalid directory"
                )
        for current_root, directory_names, file_names in os.walk(
            profile_root,
            topdown=True,
            followlinks=False,
        ):
            current = Path(current_root)
            for name in [*directory_names, *file_names]:
                candidate = current / name
                if candidate.is_symlink():
                    raise ControlledProofError(
                        "permit-bound executor tree contains a symbolic link"
                    )
            for name in file_names:
                relative = PurePosixPath((current / name).relative_to(snapshot).as_posix())
                if relative not in expected_files:
                    raise ControlledProofError(
                        "permit-bound executor tree contains an untracked file"
                    )

        attested_files: dict[PurePosixPath, tuple[bytes, int]] = {}
        for relative, (expected_mode, expected_object_id) in expected_files.items():
            path = snapshot.joinpath(*relative.parts)
            try:
                resolved_parent = path.parent.resolve(strict=True)
                descriptor = os.open(
                    path,
                    os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
                )
            except OSError as exc:
                raise ControlledProofError(
                    f"permit-bound executor file is unavailable: {relative}"
                ) from exc
            try:
                file_stat = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(file_stat.st_mode)
                    or not resolved_parent.is_relative_to(snapshot_root)
                ):
                    raise ControlledProofError(
                        f"permit-bound executor path is not a regular file: {relative}"
                    )
                with os.fdopen(descriptor, "rb", closefd=False) as handle:
                    content = handle.read()
            finally:
                os.close(descriptor)

            hasher = hashlib.new(object_format)
            hasher.update(f"blob {len(content)}\0".encode("ascii"))
            hasher.update(content)
            executable = bool(file_stat.st_mode & 0o111)
            if hasher.hexdigest() != expected_object_id or executable != (
                expected_mode == "100755"
            ):
                raise ControlledProofError(
                    f"permit-bound executor bytes changed during execution: {relative}"
                )
            attested_files[relative] = (
                content,
                0o755 if expected_mode == "100755" else 0o644,
            )
        return attested_files

    @staticmethod
    @contextmanager
    def _sealed_executor_files(
        attested_files: dict[PurePosixPath, tuple[bytes, int]],
    ) -> Iterator[dict[PurePosixPath, tuple[int, int]]]:
        required_constants = (
            "F_ADD_SEALS",
            "F_GET_SEALS",
            "F_SEAL_GROW",
            "F_SEAL_SEAL",
            "F_SEAL_SHRINK",
            "F_SEAL_WRITE",
        )
        required_os_constants = ("MFD_ALLOW_SEALING", "MFD_CLOEXEC")
        if (
            not hasattr(os, "memfd_create")
            or any(not hasattr(os, name) for name in required_os_constants)
            or any(not hasattr(fcntl, name) for name in required_constants)
        ):
            raise ControlledProofError(
                "sealed permit-bound executor files are unavailable on this host"
            )

        sealed_files: dict[PurePosixPath, tuple[int, int]] = {}
        try:
            for relative, (content, mode) in attested_files.items():
                try:
                    descriptor = os.memfd_create(
                        f"controlled-proof-{relative.name}",
                        flags=(
                            getattr(os, "MFD_CLOEXEC")
                            | getattr(os, "MFD_ALLOW_SEALING")
                        ),
                    )
                    sealed_files[relative] = (descriptor, mode)
                    os.fchmod(descriptor, mode)
                    offset = 0
                    while offset < len(content):
                        written = os.write(descriptor, content[offset:])
                        if written <= 0:
                            raise OSError("sealed executor file write made no progress")
                        offset += written
                    os.fsync(descriptor)
                    required_seals = (
                        fcntl.F_SEAL_GROW
                        | fcntl.F_SEAL_SEAL
                        | fcntl.F_SEAL_SHRINK
                        | fcntl.F_SEAL_WRITE
                    )
                    fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, required_seals)
                    applied_seals = fcntl.fcntl(descriptor, fcntl.F_GET_SEALS)
                    if applied_seals & required_seals != required_seals:
                        raise OSError("sealed executor file is missing required seals")
                    os.lseek(descriptor, 0, os.SEEK_SET)
                except OSError as exc:
                    raise ControlledProofError(
                        "failed to seal permit-bound executor file"
                    ) from exc
            yield sealed_files
        finally:
            for descriptor, _mode in sealed_files.values():
                os.close(descriptor)

    def _sandboxed_runtime_command(
        self,
        *,
        runtime_script: Path,
        action: str,
        sealed_files: dict[PurePosixPath, tuple[int, int]],
    ) -> list[str]:
        state_parent = self.state_root.parent
        state_parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        for label, directory in (
            ("output", self.output_root),
            ("state", state_parent),
        ):
            if directory.is_symlink() or not directory.is_dir():
                raise ControlledProofError(
                    f"controlled runtime {label} directory is unavailable"
                )
            directory_stat = directory.stat()
            if (
                directory_stat.st_uid != os.geteuid()
                or directory_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
            ):
                raise ControlledProofError(
                    f"controlled runtime {label} directory must be private and operator-owned"
                )

        profile_root = self.platform_executor_snapshot.joinpath(
            *PERMIT_BOUND_EXECUTOR_TREE.parts
        )
        command = [
            "bwrap",
            "--die-with-parent",
            "--ro-bind",
            "/",
            "/",
            "--dev-bind",
            "/dev",
            "/dev",
            "--proc",
            "/proc",
            "--tmpfs",
            SANDBOX_TEMP_ROOT,
            "--dir",
            SANDBOX_HOME,
            "--bind",
            str(self.output_root),
            str(self.output_root),
            "--bind",
            str(state_parent),
            str(state_parent),
            "--tmpfs",
            str(profile_root),
        ]

        relative_directories: set[PurePosixPath] = set()
        for relative in sealed_files:
            profile_relative = relative.relative_to(PERMIT_BOUND_EXECUTOR_TREE)
            parent = profile_relative.parent
            while parent != PurePosixPath("."):
                relative_directories.add(parent)
                parent = parent.parent
        for relative in sorted(
            relative_directories, key=lambda item: (len(item.parts), str(item))
        ):
            command.extend(["--dir", str(profile_root.joinpath(*relative.parts))])
        for relative, (descriptor, mode) in sorted(
            sealed_files.items(), key=lambda item: str(item[0])
        ):
            profile_relative = relative.relative_to(PERMIT_BOUND_EXECUTOR_TREE)
            command.extend(
                [
                    "--perms",
                    f"0{mode:o}",
                    "--ro-bind-data",
                    str(descriptor),
                    str(profile_root.joinpath(*profile_relative.parts)),
                ]
            )
        command.extend(
            [
                "--remount-ro",
                str(profile_root),
                "--chdir",
                str(self.platform_executor_snapshot),
                "--",
                "bash",
                str(runtime_script),
                action,
            ]
        )
        return command

    def _run(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
        input_text: str | None = None,
        pass_fds: tuple[int, ...] = (),
        timeout: float = 600,
        allow_expired: bool = False,
        expected_runtime_action: str | None = None,
    ) -> CommandResult:
        effective_timeout = timeout
        if not allow_expired:
            effective_timeout = min(timeout, self._remaining_authorization_seconds())
        runtime_environment = controlled_subprocess_environment(env)
        result = self.runner.run(
            command,
            env=runtime_environment,
            input_text=input_text,
            pass_fds=pass_fds,
            timeout=effective_timeout,
        )
        if result.returncode != 0:
            recorded_at = now_utc()
            command_digest = hashlib.sha256(
                "\0".join(command).encode("utf-8")
            ).hexdigest()
            attempt_key = hashlib.sha256(
                f"{command_digest}\0{recorded_at}\0{time.time_ns()}".encode("utf-8")
            ).hexdigest()
            failure_path = (
                self.output_root
                / "runtime"
                / "command-failures"
                / f"{attempt_key}.json"
            )
            failure = {
                "schema_version": 1,
                "authorization_id": self.authorization["authorization_id"],
                "commissioning_session_id": self.authorization[
                    "commissioning_session"
                ]["commissioning_session_id"],
                "command_digest": f"sha256:{command_digest}",
                "executable": Path(command[0]).name,
                "returncode": result.returncode,
                "stdout": {
                    "sha256": "sha256:"
                    + hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
                    "bytes": len(result.stdout.encode("utf-8")),
                },
                "stderr": {
                    "sha256": "sha256:"
                    + hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
                    "bytes": len(result.stderr.encode("utf-8")),
                },
                "recorded_at": recorded_at,
            }
            if expected_runtime_action is not None:
                failure["runtime_diagnostic"] = self._runtime_failure_diagnostic(
                    stderr=result.stderr,
                    expected_action=expected_runtime_action,
                    returncode=result.returncode,
                )
            failure_digest = write_json_atomic(failure_path, failure)
            raise ControlledProofError(
                "controlled runtime command failed; bounded failure evidence was recorded",
                evidence_refs=[
                    {
                        "artifact_ref": (
                            "platform-controlled-proof://runtime-command-failures/"
                            f"{attempt_key}"
                        ),
                        "artifact_digest": failure_digest,
                    }
                ],
            )
        return result

    @staticmethod
    def _runtime_failure_diagnostic(
        *,
        stderr: str,
        expected_action: str,
        returncode: int,
    ) -> dict[str, Any]:
        diagnostic: dict[str, Any] = {
            "schema_version": 1,
            "status": "unavailable",
            "action": expected_action,
        }
        for line in reversed(stderr.splitlines()):
            match = RUNTIME_FAILURE_MARKER_RE.fullmatch(line.strip())
            if match is None:
                continue
            action, phase, exit_code_text = match.groups()
            exit_code = int(exit_code_text)
            if (
                action != expected_action
                or action not in RUNTIME_SCRIPT_ACTIONS
                or phase not in RUNTIME_FAILURE_PHASES
                or exit_code != returncode
            ):
                continue
            return {
                "schema_version": 1,
                "status": "available",
                "action": action,
                "phase": phase,
                "exit_code": exit_code,
            }
        return diagnostic

    def _assert_authorization_current(self) -> None:
        current = datetime.now(timezone.utc)
        issued_at = parse_timestamp(
            self.authorization["window"]["issued_at"],
            "authorization issued_at",
        )
        expires_at = parse_timestamp(
            self.authorization["window"]["expires_at"],
            "authorization expires_at",
        )
        if current < issued_at or current >= expires_at:
            raise ControlledProofError("authorization expired during commissioning")

    def _remaining_authorization_seconds(self) -> float:
        expires_at = parse_timestamp(
            self.authorization["window"]["expires_at"],
            "authorization expires_at",
        )
        remaining = (
            (expires_at - datetime.now(timezone.utc)).total_seconds()
            - TERMINAL_CLEANUP_START_RESERVE_SECONDS
        )
        if remaining <= 0:
            raise ControlledProofError(
                "authorization no longer has the required exact-restore start reserve"
            )
        return max(0.1, remaining)

    def _prepare_workspace_governance_snapshot(self) -> None:
        snapshot = self.workspace_governance_snapshot
        if snapshot.exists():
            raise ControlledProofError(
                "workspace-governance source snapshot already exists"
            )
        snapshot.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        source = self.workspace_root / "workspace-governance"
        expected_revision = next(
            item["commit"]
            for item in self.authorization["scope"]["execution_source_revisions"]
            if item["repo"] == "workspace-governance"
        )
        self._run(
            [
                "git",
                "clone",
                "--no-hardlinks",
                "--no-checkout",
                str(source),
                str(snapshot),
            ]
        )
        self._run(
            ["git", "-C", str(snapshot), "checkout", "--detach", expected_revision]
        )
        head = self._run(
            ["git", "-C", str(snapshot), "rev-parse", "HEAD"]
        ).stdout
        status = self._run(
            ["git", "-C", str(snapshot), "status", "--short"]
        ).stdout
        if head != expected_revision or status:
            raise ControlledProofError(
                "workspace-governance runtime snapshot does not match authorization"
            )

    def _require_tools(self) -> None:
        environment = controlled_subprocess_environment()
        for command in (
            "bash",
            "bwrap",
            "git",
            "helm",
            "k3s",
            "python3",
            "sha256sum",
        ):
            try:
                resolve_controlled_command([command], environment=environment)
            except ControlledProofError as exc:
                raise ControlledProofError(
                    f"controlled runtime prerequisite is unavailable: {command}"
                ) from exc
        sandbox_probe = self.runner.run(
            [
                "bwrap",
                "--die-with-parent",
                "--ro-bind",
                "/",
                "/",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--",
                "/bin/true",
            ],
            env=environment,
            timeout=30,
        )
        if sandbox_probe.returncode != 0:
            raise ControlledProofError(
                "controlled runtime prerequisite is unavailable: bwrap sandbox capability"
            )

    def _start_port_forward(self) -> None:
        self._assert_authorization_current()
        port = _available_port()
        log_path = self.output_root / "runtime" / "oos-port-forward.log"
        log_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        log_handle = log_path.open("w", encoding="utf-8")
        os.chmod(log_path, 0o600)
        environment = controlled_subprocess_environment()
        self.port_forward = subprocess.Popen(
            resolve_controlled_command(
                [
                    "k3s",
                    "kubectl",
                    "-n",
                    self.kubernetes_namespace,
                    "port-forward",
                    f"service/{OOS_API_SERVICE}",
                    f"{port}:8080",
                    "--address=127.0.0.1",
                ],
                environment=environment,
            ),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            env=environment,
        )
        log_handle.close()
        self.api_url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            self._assert_authorization_current()
            if self.port_forward.poll() is not None:
                raise ControlledProofError("OOS API port-forward stopped during startup")
            try:
                health_request = urlrequest.Request(
                    _local_api_endpoint(self.api_url, "/healthz"),
                    method="GET",
                )
                with LOCAL_HTTP_OPENER.open(health_request, timeout=1):
                    return
            except urlerror.URLError:
                time.sleep(0.25)
        raise ControlledProofError("OOS API port-forward did not become ready")

    def _stop_port_forward(self) -> None:
        if self.port_forward is None:
            return
        if self.port_forward.poll() is None:
            self.port_forward.terminate()
            try:
                self.port_forward.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.port_forward.kill()
                self.port_forward.wait(timeout=5)
        self.port_forward = None
        self.api_url = ""


def _wgcf_receipt_binding(oos_receipt: dict[str, Any]) -> tuple[str, str, str]:
    evidence_refs = oos_receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        raise ControlledProofError("OOS receipt evidence references are invalid")
    matches: list[dict[str, Any]] = []
    for item in evidence_refs:
        if not isinstance(item, dict):
            raise ControlledProofError("OOS receipt evidence reference is invalid")
        artifact_ref = item.get("artifact_ref")
        if isinstance(artifact_ref, str) and artifact_ref.startswith(
            WGCF_RECEIPT_PREFIX
        ):
            matches.append(item)
    if len(matches) != 1:
        raise ControlledProofError("OOS receipt does not bind one WGCF receipt")
    binding = matches[0]
    if set(binding) != {"artifact_ref", "artifact_digest"}:
        raise ControlledProofError("OOS WGCF receipt binding fields are invalid")
    receipt_ref = binding["artifact_ref"]
    receipt_id = receipt_ref.removeprefix(WGCF_RECEIPT_PREFIX)
    if WGCF_RECEIPT_KEY_RE.fullmatch(receipt_id) is None:
        raise ControlledProofError("OOS WGCF receipt reference is not a fixed receipt key")
    expected_digest = normalize_digest(
        binding["artifact_digest"], "OOS WGCF receipt digest"
    )
    return receipt_id, receipt_ref, expected_digest


def _validate_loaded_wgcf_receipt(
    receipt: dict[str, Any],
    *,
    receipt_ref: str,
    expected_digest: str,
) -> None:
    if receipt.get("receipt_ref") != receipt_ref:
        raise ControlledProofError("loaded WGCF receipt reference does not match OOS")
    if receipt.get("receipt_digest") != expected_digest:
        raise ControlledProofError("loaded WGCF receipt digest does not match OOS")


def _owner_runtime_manifest(
    *,
    authorization: dict[str, Any],
    contexts: ProjectedContexts,
    kubernetes_namespace: str,
    workspace_governance_source: Path,
) -> list[dict[str, Any]]:
    images = {
        item["image_ref"]: f"{item['image_ref']}@{item['digest']}"
        for item in authorization["scope"]["runtime_images"]
    }
    oos_api_image = images["ghcr.io/mfshaf7/operator-orchestration-service"]
    oos_worker_image = images[
        "ghcr.io/mfshaf7/operator-orchestration-service-worker"
    ]
    wgcf_worker_image = images[
        "ghcr.io/mfshaf7/workspace-governance-control-fabric-worker"
    ]
    execution_source_revisions = {
        item["repo"]: item["commit"]
        for item in authorization["scope"]["execution_source_revisions"]
    }
    common_oos_env = [
        {
            "name": "GIT_COMMIT",
            "value": execution_source_revisions["operator-orchestration-service"],
        },
        {"name": "OOS_ORCHESTRATION_CONTROLLED_PROOF_ENABLED", "value": "true"},
        {
            "name": "OOS_ORCHESTRATION_CONTROLLED_PROOF_CONTEXT_PATH",
            "value": "/var/run/controlled-proof/oos-execution-context.json",
        },
        {
            "name": "OOS_ORCHESTRATION_CONTROLLED_PROOF_CONTEXT_DIGEST",
            "value": contexts.oos_digest,
        },
        {"name": "OOS_TEMPORAL_ADDRESS", "value": "temporal-frontend:7233"},
        {"name": "OOS_TEMPORAL_NAMESPACE", "value": contexts.oos["runtime"]["temporal_namespace"]},
    ]
    context_volumes = [
        {
            "name": "controlled-proof-context",
            "configMap": {
                "name": "controlled-proof-oos-context",
                "defaultMode": 0o444,
            },
        }
    ]
    context_mounts = [
        {
            "name": "controlled-proof-context",
            "mountPath": "/var/run/controlled-proof",
            "readOnly": True,
        }
    ]

    def deployment(
        *,
        name: str,
        image: str,
        service_account: str,
        identity_label: str,
        env: list[dict[str, Any]],
        command: list[str] | None = None,
        volumes: list[dict[str, Any]] | None = None,
        mounts: list[dict[str, Any]] | None = None,
        ports: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        container: dict[str, Any] = {
            "name": name,
            "image": image,
            "imagePullPolicy": "IfNotPresent",
            "env": env,
            "securityContext": {
                "allowPrivilegeEscalation": False,
                "capabilities": {"drop": ["ALL"]},
            },
            "volumeMounts": mounts or context_mounts,
        }
        if command:
            container["command"] = command
        if ports:
            container["ports"] = ports
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name, "namespace": kubernetes_namespace},
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"app": name}},
                "template": {
                    "metadata": {
                        "labels": {
                            "app": name,
                            "app.kubernetes.io/part-of": "temporal-controlled-proof",
                            "orchestration.workspace/identity": identity_label,
                        }
                    },
                    "spec": {
                        "automountServiceAccountToken": False,
                        "serviceAccountName": service_account,
                        "containers": [container],
                        "volumes": volumes or context_volumes,
                    },
                },
            },
        }

    wgcf_volumes = [
        {
            "name": "controlled-proof-context",
            "configMap": {
                "name": "controlled-proof-wgcf-context",
                "defaultMode": 0o444,
            },
        },
        {"name": "controlled-proof-evidence", "emptyDir": {}},
        {
            "name": "workspace-governance-source",
            "hostPath": {
                "path": str(workspace_governance_source),
                "type": "Directory",
            },
        },
    ]
    wgcf_mounts = [
        *context_mounts,
        {
            "name": "controlled-proof-evidence",
            "mountPath": "/var/lib/wgcf/orchestration/controlled-proof",
        },
        {
            "name": "workspace-governance-source",
            "mountPath": "/workspace/workspace-governance",
            "readOnly": True,
        },
    ]
    return [
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "controlled-proof-oos-context",
                "namespace": kubernetes_namespace,
            },
            "immutable": True,
            "data": {
                "oos-execution-context.json": contexts.oos_path.read_text(
                    encoding="utf-8"
                )
            },
        },
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "controlled-proof-wgcf-context",
                "namespace": kubernetes_namespace,
            },
            "immutable": True,
            "data": {
                "wgcf-owner-context.json": contexts.wgcf_path.read_text(
                    encoding="utf-8"
                )
            },
        },
        deployment(
            name=OOS_API_DEPLOYMENT,
            image=oos_api_image,
            service_account="temporal-oos-api",
            identity_label="oos-api",
            env=[
                *common_oos_env,
                {"name": "OOS_TEMPORAL_IDENTITY", "value": contexts.oos["runtime"]["api_identity"]},
                {"name": "CALLER_ALLOWED_IDS", "value": "platform-controlled-proof-executor"},
                {
                    "name": "CALLER_AUTH_SHARED_SECRET",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": "controlled-proof-oos-caller",
                            "key": "shared-secret",
                        }
                    },
                },
            ],
            ports=[{"name": "http", "containerPort": 8080}],
        ),
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": OOS_API_SERVICE, "namespace": kubernetes_namespace},
            "spec": {
                "selector": {"app": OOS_API_DEPLOYMENT},
                "ports": [{"name": "http", "port": 8080, "targetPort": 8080}],
            },
        },
        deployment(
            name=OOS_WORKER_DEPLOYMENT,
            image=oos_worker_image,
            service_account="temporal-oos-worker",
            identity_label="oos-workflow-worker",
            env=[
                *common_oos_env,
                {
                    "name": "OOS_TEMPORAL_IDENTITY",
                    "value": contexts.oos["runtime"]["workflow_worker_identity"],
                },
            ],
            command=["node", "src/orchestration-worker.js", "controlled-proof-run"],
        ),
        deployment(
            name=WGCF_WORKER_DEPLOYMENT,
            image=wgcf_worker_image,
            service_account="temporal-wgcf-activity",
            identity_label="wgcf-activity-worker",
            env=[
                {"name": "WGCF_CONTROLLED_PROOF_ENABLED", "value": "true"},
                {"name": "WGCF_CONTROLLED_PROOF_EXECUTION_AUTHORIZED", "value": "true"},
                {
                    "name": "WGCF_CONTROLLED_PROOF_CONTEXT_PATH",
                    "value": "/var/run/controlled-proof/wgcf-owner-context.json",
                },
                {"name": "WGCF_CONTROLLED_PROOF_CONTEXT_DIGEST", "value": contexts.wgcf_digest},
                {
                    "name": "WGCF_CONTROLLED_PROOF_EVIDENCE_ROOT",
                    "value": "/var/lib/wgcf/orchestration/controlled-proof",
                },
                {"name": "WGCF_CONTROLLED_PROOF_TEMPORAL_ADDRESS", "value": "temporal-frontend:7233"},
                {"name": "WGCF_CONTROLLED_PROOF_TEMPORAL_NAMESPACE", "value": contexts.wgcf["runtime"]["temporal_namespace"]},
                {"name": "WGCF_CONTROLLED_PROOF_TEMPORAL_TASK_QUEUE", "value": contexts.wgcf["runtime"]["activity_task_queue"]},
                {"name": "WGCF_CONTROLLED_PROOF_TEMPORAL_WORKER_ID", "value": contexts.wgcf["runtime"]["worker_identity"]},
                {"name": "WGCF_WORKSPACE_ROOT", "value": "/workspace"},
                {"name": "WGCF_REPO_ROOT", "value": "/app"},
            ],
            command=["wgcf-worker", "controlled-proof", "run"],
            volumes=wgcf_volumes,
            mounts=wgcf_mounts,
        ),
    ]


def _caller_secret_manifest(namespace: str, secret: str) -> str:
    return json.dumps(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": "controlled-proof-oos-caller",
                "namespace": namespace,
            },
            "type": "Opaque",
            "stringData": {"shared-secret": secret},
        }
    )


def _kubernetes_namespace(operator_id: str) -> str:
    return operator_scoped_dns_label("devint-temporal", operator_id)


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ControlledProofError(f"runtime response is missing {field}")
    return value
