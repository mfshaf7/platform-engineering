from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .authority import (
    ContractSet,
    authorization_storage_key,
    execution_scope_lease_ref,
    validate_authorization_semantics,
)
from .model import (
    SCENARIO_ORDER,
    TERMINAL_CLEANUP_START_RESERVE_SECONDS,
    ControlledProofError,
    canonical_digest,
    create_json_exclusive,
    normalize_digest,
    now_utc,
    operator_scope_id,
    parse_timestamp,
    read_bounded_json,
    read_bounded_json_with_digest,
    require_exact_keys,
    sha256_bytes,
    sha256_file,
    validate_schema,
    write_json_atomic,
)

TERMINAL_SCENARIO_STATUSES = {"passed", "failed", "blocked"}
STOPPED_DRAFT_NAME = "controlled-proof-stopped-draft.json"
STOPPED_RESULT_NAME = "controlled-proof-result.json"
GOVERNED_EXCEPTION_NAME = "controlled-proof-governed-exception.json"
STOPPED_DRAFT_REASONS = {
    "exact-baseline-restore-failed",
    "terminal-cleanup-failed",
}


@dataclass(frozen=True)
class ProjectedContexts:
    oos: dict[str, Any]
    oos_path: Path
    oos_digest: str
    wgcf: dict[str, Any]
    wgcf_path: Path
    wgcf_digest: str


@dataclass(frozen=True)
class ScenarioExecutionResult:
    status: str
    evidence_refs: list[dict[str, str]]
    owner_receipts: list[dict[str, Any]]
    started_at: str
    completed_at: str


class ExecutionDriver(Protocol):
    def prepare(self, contexts: ProjectedContexts) -> None: ...

    def execute_scenario(
        self,
        scenario: dict[str, Any],
        contexts: ProjectedContexts,
    ) -> ScenarioExecutionResult: ...

    def restore_exact_baseline(
        self,
        scenario: dict[str, Any],
        contexts: ProjectedContexts,
        baseline: dict[str, Any],
    ) -> ScenarioExecutionResult: ...

    def cleanup(self, contexts: ProjectedContexts) -> None: ...


def project_owner_contexts(
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    consumption_receipt: dict[str, Any],
    consumption_receipt_digest: str,
    baseline: dict[str, Any],
    output_root: Path,
    contracts: ContractSet,
    started_at: str | None = None,
) -> ProjectedContexts:
    normalize_digest(authorization_digest, "authorization digest")
    normalize_digest(consumption_receipt_digest, "consumption receipt digest")
    validate_consumption_binding(
        authorization,
        authorization_digest,
        consumption_receipt,
        consumption_receipt_digest,
        contracts,
    )
    output_root = output_root.expanduser().absolute()
    if output_root.is_symlink():
        raise ControlledProofError("owner context root must not be a symbolic link")
    output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_root_stat = output_root.stat()
    if (
        not stat.S_ISDIR(output_root_stat.st_mode)
        or output_root_stat.st_uid != os.geteuid()
        or output_root_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    ):
        raise ControlledProofError(
            "owner context root must be private and operator-owned"
        )
    output_root = output_root.resolve()
    oos_path = output_root / "oos-execution-context.json"
    wgcf_path = output_root / "wgcf-owner-context.json"
    existing_oos: dict[str, Any] | None = None
    existing_oos_digest: str | None = None
    if oos_path.exists() or oos_path.is_symlink():
        existing_oos, existing_oos_digest = read_bounded_json_with_digest(oos_path)
        existing_session = existing_oos.get("commissioning_session")
        if not isinstance(existing_session, dict) or not isinstance(
            existing_session.get("started_at"), str
        ):
            raise ControlledProofError(
                "existing OOS execution context does not bind a session start"
            )
        existing_started_at = existing_session["started_at"]
        if started_at is not None and started_at != existing_started_at:
            raise ControlledProofError(
                "existing owner contexts use a different session start"
            )
        session_started_at = existing_started_at
    else:
        session_started_at = started_at or now_utc()
    consumed_at = parse_timestamp(consumption_receipt["consumed_at"], "consumed_at")
    session_started = parse_timestamp(session_started_at, "session started_at")
    expires_at = parse_timestamp(
        authorization["window"]["expires_at"],
        "authorization expires_at",
    )
    if session_started < consumed_at:
        raise ControlledProofError(
            "commissioning session must not start before permit consumption"
        )
    if (
        expires_at - session_started
    ).total_seconds() <= TERMINAL_CLEANUP_START_RESERVE_SECONDS:
        raise ControlledProofError(
            "commissioning session must preserve the exact-restore start reserve"
        )

    sources = {item["repo"]: item["commit"] for item in authorization["scope"]["source_revisions"]}
    identities = {
        item["role"]: item["identity"] for item in authorization["scope"]["runtime_identities"]
    }
    queues = {
        item["owner_repo"]: item["queue_name"] for item in authorization["scope"]["task_queues"]
    }
    required_identities = {
        "oos-api",
        "oos-workflow-worker",
        "wgcf-activity-worker",
    }
    if set(identities) != required_identities:
        raise ControlledProofError(
            "authorization runtime identities must bind OOS API, OOS worker, and WGCF worker"
        )
    if set(queues) != {
        "operator-orchestration-service",
        "workspace-governance-control-fabric",
    }:
        raise ControlledProofError("authorization task queues do not match the two worker owners")
    namespaces = authorization["scope"]["target_namespaces"]
    if len(namespaces) != 1:
        raise ControlledProofError("authorization must bind exactly one Temporal namespace")

    approvals = authorization["approvals"]
    receipt_ref = consumption_receipt["receipt_id"]
    authorization_projection = {
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "canonical_claims_digest": approvals["canonical_claims_digest"],
        "operator_approval_ref": approvals["operator_approval_ref"],
        "operator_approval_digest": approvals["operator_approval_digest"],
        "security_authorization_ref": approvals["security_authorization_ref"],
        "security_authorization_digest": approvals["security_authorization_digest"],
        "issued_at": authorization["window"]["issued_at"],
        "expires_at": authorization["window"]["expires_at"],
        "consumption_receipt_ref": receipt_ref,
        "consumption_receipt_digest": consumption_receipt_digest,
        "consumed_at": consumption_receipt["consumed_at"],
    }
    verification_ref = authorization["evidence"]["verification_pack_ref"]
    operator_id = baseline["operator_id"]
    commissioning_session = {
        "commissioning_session_id": authorization["commissioning_session"]["commissioning_session_id"],
        "started_at": session_started_at,
        "scenario_executions": authorization["commissioning_session"]["scenario_executions"],
    }
    oos_context_id = (
        "platform-controlled-proof://contexts/oos/"
        f"{authorization['commissioning_session']['commissioning_session_id']}"
    )
    oos_context = {
        "schema_version": 1,
        "context_id": oos_context_id,
        "authorization": authorization_projection,
        "commissioning_session": commissioning_session,
        "definition": {
            "definition_id": "validation-readiness-run",
            "definition_version": 1,
        },
        "request_binding": {
            "source_record_ref": verification_ref,
            "source_version_ref": (
                "git:workspace-governance-control-fabric:"
                f"{sources['workspace-governance-control-fabric']}"
            ),
            "source_projection_ref": verification_ref,
            "source_projection_version": sources[
                "workspace-governance-control-fabric"
            ],
            "operator_id": operator_id,
        },
        "runtime": {
            "profile_id": "temporal",
            "profile_lifecycle": "build-admitted",
            "environment": "dev-integration",
            "temporal_address": "temporal-frontend:7233",
            "temporal_namespace": namespaces[0],
            "api_identity": identities["oos-api"],
            "workflow_worker_identity": identities["oos-workflow-worker"],
            "workflow_task_queue": queues["operator-orchestration-service"],
            "activity_task_queue": queues["workspace-governance-control-fabric"],
        },
        "source_revisions": {
            "operator_orchestration_service": sources["operator-orchestration-service"],
            "workspace_governance_control_fabric": sources[
                "workspace-governance-control-fabric"
            ],
        },
    }
    validate_schema(oos_context, contracts.oos_context, "OOS execution context")

    if existing_oos is not None:
        if existing_oos != oos_context or existing_oos_digest is None:
            raise ControlledProofError(
                "existing OOS execution context does not match this authorization"
            )
        oos_digest = existing_oos_digest
    else:
        oos_digest = write_json_atomic(oos_path, oos_context)

    wgcf_context = {
        "schema_version": 1,
        "owner_context_id": (
            "platform-controlled-proof://contexts/wgcf/"
            f"{authorization['commissioning_session']['commissioning_session_id']}"
        ),
        "owner_repo": "workspace-governance-control-fabric",
        "orchestration_context": {
            "context_id": oos_context_id,
            "context_digest": oos_digest,
        },
        "authorization": authorization_projection,
        "commissioning_session": commissioning_session,
        "definition": {
            "definition_id": "validation-readiness-run",
            "definition_version": 1,
        },
        "request_binding": {
            "source_record_ref": verification_ref,
            "source_version_ref": authorization_digest,
            "operator_id": operator_id,
        },
        "runtime": {
            "profile_id": "temporal",
            "profile_lifecycle": "build-admitted",
            "environment": "dev-integration",
            "temporal_address": "temporal-frontend:7233",
            "temporal_namespace": namespaces[0],
            "worker_identity": identities["wgcf-activity-worker"],
            "activity_task_queue": queues["workspace-governance-control-fabric"],
        },
        "source_revisions": oos_context["source_revisions"],
    }
    validate_schema(wgcf_context, contracts.wgcf_context, "WGCF owner context")
    if wgcf_path.exists() or wgcf_path.is_symlink():
        existing_wgcf, wgcf_digest = read_bounded_json_with_digest(wgcf_path)
        if existing_wgcf != wgcf_context:
            raise ControlledProofError(
                "existing WGCF owner context does not match this authorization"
            )
    else:
        wgcf_digest = write_json_atomic(wgcf_path, wgcf_context)
    return ProjectedContexts(
        oos=oos_context,
        oos_path=oos_path,
        oos_digest=oos_digest,
        wgcf=wgcf_context,
        wgcf_path=wgcf_path,
        wgcf_digest=wgcf_digest,
    )


def validate_consumption_binding(
    authorization: dict[str, Any],
    authorization_digest: str,
    receipt: dict[str, Any],
    receipt_digest: str,
    contracts: ContractSet,
) -> None:
    validate_schema(receipt, contracts.consumption, "consumption receipt")
    expected = {
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "canonical_claims_digest": authorization["approvals"]["canonical_claims_digest"],
        "commissioning_session_id": authorization["commissioning_session"]["commissioning_session_id"],
        "executor_source_revision": authorization["executor"]["source_revision"],
    }
    mismatched = [field for field, value in expected.items() if receipt.get(field) != value]
    if mismatched:
        raise ControlledProofError(
            "consumption receipt does not match authorization: " + ", ".join(mismatched)
        )
    normalize_digest(receipt_digest, "consumption receipt digest")


def validate_execution_claim_binding(
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    consumption_receipt: dict[str, Any],
    consumption_receipt_digest: str,
    execution_claim: dict[str, Any],
    execution_claim_digest: str,
    output_root: Path,
    operator_scope: str | None = None,
) -> None:
    require_exact_keys(
        execution_claim,
        {
            "schema_version",
            "execution_claim_id",
            "authorization_id",
            "authorization_digest",
            "consumption_receipt_ref",
            "consumption_receipt_digest",
            "commissioning_session_id",
            "executor_source_revision",
            "output_root_digest",
            "operator_scope",
            "scope_lease_ref",
            "scope_lease_digest",
            "claimed_at",
        },
        "execution claim",
    )
    if execution_claim["schema_version"] != 2:
        raise ControlledProofError("execution claim schema version is unsupported")
    expected = {
        "execution_claim_id": (
            "platform-controlled-proof://execution-claims/"
            f"{authorization_storage_key(authorization['authorization_id'])}"
        ),
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "consumption_receipt_ref": consumption_receipt["receipt_id"],
        "consumption_receipt_digest": consumption_receipt_digest,
        "commissioning_session_id": authorization["commissioning_session"][
            "commissioning_session_id"
        ],
        "executor_source_revision": authorization["executor"]["source_revision"],
        "output_root_digest": sha256_bytes(
            str(output_root.expanduser().resolve()).encode("utf-8")
        ),
        "scope_lease_ref": execution_scope_lease_ref(
            execution_claim["operator_scope"]
        ),
    }
    if operator_scope is not None:
        expected["operator_scope"] = operator_scope
    mismatched = [
        field
        for field, expected_value in expected.items()
        if execution_claim.get(field) != expected_value
    ]
    if mismatched:
        raise ControlledProofError(
            "execution claim does not match the controlled session: "
            + ", ".join(mismatched)
        )
    normalize_digest(execution_claim_digest, "execution claim digest")
    normalize_digest(execution_claim["scope_lease_digest"], "scope lease digest")
    claimed_at = parse_timestamp(execution_claim["claimed_at"], "execution claimed_at")
    consumed_at = parse_timestamp(
        consumption_receipt["consumed_at"], "consumption consumed_at"
    )
    expires_at = parse_timestamp(
        authorization["window"]["expires_at"], "authorization expires_at"
    )
    if claimed_at < consumed_at or claimed_at >= expires_at:
        raise ControlledProofError("execution claim timeline is outside permit authority")


class ControlledProofExecutor:
    def __init__(
        self,
        *,
        authorization: dict[str, Any],
        authorization_digest: str,
        consumption_receipt: dict[str, Any],
        consumption_receipt_digest: str,
        execution_claim: dict[str, Any],
        execution_claim_digest: str,
        baseline: dict[str, Any],
        contexts: ProjectedContexts,
        contracts: ContractSet,
        driver: ExecutionDriver,
        output_root: Path,
    ):
        self.authorization = authorization
        self.authorization_digest = normalize_digest(
            authorization_digest, "authorization digest"
        )
        self.consumption_receipt = consumption_receipt
        self.consumption_receipt_digest = consumption_receipt_digest
        self.execution_claim = execution_claim
        self.execution_claim_digest = execution_claim_digest
        self.baseline = baseline
        self.contexts = contexts
        self.contracts = contracts
        self.driver = driver
        self.output_root = output_root.resolve()

    def run(self) -> tuple[dict[str, Any], str]:
        validate_consumption_binding(
            self.authorization,
            self.authorization_digest,
            self.consumption_receipt,
            self.consumption_receipt_digest,
            self.contracts,
        )
        validate_execution_claim_binding(
            authorization=self.authorization,
            authorization_digest=self.authorization_digest,
            consumption_receipt=self.consumption_receipt,
            consumption_receipt_digest=self.consumption_receipt_digest,
            execution_claim=self.execution_claim,
            execution_claim_digest=self.execution_claim_digest,
            output_root=self.output_root,
            operator_scope=operator_scope_id(self.baseline["operator_id"]),
        )
        scenarios = self.authorization["commissioning_session"]["scenario_executions"]
        scenario_outcomes: list[dict[str, Any]] = []
        owner_receipts: list[dict[str, Any]] = []
        first_failure: ControlledProofError | None = None
        preparation_failed = False
        restore_passed = False
        cleanup_failure: ControlledProofError | None = None

        try:
            try:
                self._assert_proof_action_window()
                self.driver.prepare(self.contexts)
            except Exception as exc:
                first_failure = self._controlled_error(exc)
                preparation_failed = True

            for scenario in scenarios[:-1]:
                if first_failure is not None:
                    scenario_outcomes.append(
                        self._record_terminal_outcome(
                            scenario,
                            status="not-run",
                            reason=(
                                "preparation-failed"
                                if preparation_failed
                                else "earlier-scenario-failed"
                            ),
                        )
                    )
                    continue
                try:
                    self._assert_proof_action_window()
                    result = self.driver.execute_scenario(scenario, self.contexts)
                    validated = self._validate_scenario_result(scenario, result)
                    scenario_outcomes.append(validated[0])
                    owner_receipts.extend(validated[1])
                    if result.status != "passed":
                        first_failure = ControlledProofError(
                            f"scenario {scenario['scenario_id']} ended {result.status}"
                        )
                except Exception as exc:
                    first_failure = self._controlled_error(exc)
                    scenario_outcomes.append(
                        self._record_terminal_outcome(
                            scenario,
                            status="failed",
                            reason="scenario-executor-failed",
                        )
                    )

            restore_scenario = scenarios[-1]
            try:
                restore_result = self.driver.restore_exact_baseline(
                    restore_scenario,
                    self.contexts,
                    self.baseline,
                )
                restore_outcome, restore_receipts = self._validate_scenario_result(
                    restore_scenario,
                    restore_result,
                )
                scenario_outcomes.append(restore_outcome)
                owner_receipts.extend(restore_receipts)
                restore_passed = restore_result.status == "passed"
            except Exception as exc:
                restore_passed = False
                if first_failure is None:
                    first_failure = self._controlled_error(exc)
                restore_outcome = self._record_terminal_outcome(
                    restore_scenario,
                    status="failed",
                    reason="exact-baseline-restore-failed",
                )
                scenario_outcomes.append(restore_outcome)
                owner_receipts.append(
                    create_platform_receipt(
                        authorization=self.authorization,
                        authorization_digest=self.authorization_digest,
                        scenario=restore_scenario,
                        owner_result="failed",
                        evidence_refs=restore_outcome["evidence_refs"],
                        execution_id=(
                            "platform-action:"
                            f"{restore_scenario['scenario_execution_id']}"
                        ),
                        recorded_at=restore_outcome["completed_at"],
                        contracts=self.contracts,
                    )
                )
        finally:
            try:
                self.driver.cleanup(self.contexts)
            except Exception as exc:
                cleanup_failure = self._controlled_error(exc)

        if cleanup_failure is not None:
            restore_passed = False
            first_failure = first_failure or cleanup_failure
            restore_scenario = scenarios[-1]
            cleanup_outcome = self._record_terminal_outcome(
                restore_scenario,
                status="failed",
                reason="terminal-cleanup-failed",
            )
            if scenario_outcomes and scenario_outcomes[-1]["scenario_id"] == (
                restore_scenario["scenario_id"]
            ):
                scenario_outcomes[-1] = cleanup_outcome
            else:
                scenario_outcomes.append(cleanup_outcome)
            owner_receipts = [
                receipt
                for receipt in owner_receipts
                if receipt["scenario_execution_id"]
                != restore_scenario["scenario_execution_id"]
            ]
            owner_receipts.append(
                create_platform_receipt(
                    authorization=self.authorization,
                    authorization_digest=self.authorization_digest,
                    scenario=restore_scenario,
                    owner_result="failed",
                    evidence_refs=cleanup_outcome["evidence_refs"],
                    execution_id=(
                        "platform-action:"
                        f"{restore_scenario['scenario_execution_id']}"
                    ),
                    recorded_at=cleanup_outcome["completed_at"],
                    contracts=self.contracts,
                )
            )

        if not restore_passed:
            reason = (
                "terminal-cleanup-failed"
                if cleanup_failure is not None
                else "exact-baseline-restore-failed"
            )
            draft, draft_digest = build_stopped_draft(
                authorization=self.authorization,
                authorization_digest=self.authorization_digest,
                consumption_receipt=self.consumption_receipt,
                consumption_receipt_digest=self.consumption_receipt_digest,
                execution_claim=self.execution_claim,
                execution_claim_digest=self.execution_claim_digest,
                scenario_outcomes=scenario_outcomes,
                owner_receipts=owner_receipts,
                failure_reason=reason,
                output_root=self.output_root,
                contracts=self.contracts,
                session_started_at=self.contexts.oos["commissioning_session"][
                    "started_at"
                ],
            )
            raise ControlledProofError(
                "exact-baseline cleanup did not complete; record a governed exception "
                f"for stopped draft {draft['draft_id']} ({draft_digest})"
            ) from first_failure

        result = build_result(
            authorization=self.authorization,
            authorization_digest=self.authorization_digest,
            consumption_receipt=self.consumption_receipt,
            scenario_outcomes=scenario_outcomes,
            owner_receipts=owner_receipts,
            restore_outcome=scenario_outcomes[-1],
            outcome="failed" if first_failure else "passed",
            contracts=self.contracts,
            session_started_at=self.contexts.oos["commissioning_session"][
                "started_at"
            ],
        )
        result_path = self.output_root / STOPPED_RESULT_NAME
        return result, write_json_atomic(result_path, result)

    @staticmethod
    def _controlled_error(exc: Exception) -> ControlledProofError:
        return (
            exc
            if isinstance(exc, ControlledProofError)
            else ControlledProofError(str(exc) or exc.__class__.__name__)
        )

    def _assert_proof_action_window(self) -> None:
        expires_at = parse_timestamp(self.authorization["window"]["expires_at"], "expires_at")
        remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
        if remaining <= TERMINAL_CLEANUP_START_RESERVE_SECONDS:
            raise ControlledProofError(
                "authorization no longer has the required exact-restore start reserve"
            )

    def _record_terminal_outcome(
        self,
        scenario: dict[str, Any],
        *,
        status: str,
        reason: str,
    ) -> dict[str, Any]:
        timestamp = now_utc()
        payload = {
            "schema_version": 1,
            "authorization_id": self.authorization["authorization_id"],
            "commissioning_session_id": self.authorization["commissioning_session"][
                "commissioning_session_id"
            ],
            "scenario_id": scenario["scenario_id"],
            "scenario_execution_id": scenario["scenario_execution_id"],
            "status": status,
            "reason": reason,
            "recorded_at": timestamp,
        }
        evidence_path = (
            self.output_root
            / "scenario-evidence"
            / f"{scenario['scenario_id']}-{status}-{reason}.json"
        )
        evidence_digest = write_json_atomic(evidence_path, payload)
        return {
            "scenario_id": scenario["scenario_id"],
            "scenario_execution_id": scenario["scenario_execution_id"],
            "status": status,
            "evidence_refs": [
                {
                    "artifact_ref": (
                        "platform-controlled-proof://scenario-evidence/"
                        f"{scenario['scenario_execution_id']}/{status}/{reason}"
                    ),
                    "artifact_digest": evidence_digest,
                }
            ],
            "started_at": timestamp,
            "completed_at": timestamp,
        }

    def _validate_scenario_result(
        self,
        scenario: dict[str, Any],
        result: ScenarioExecutionResult,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if result.status not in TERMINAL_SCENARIO_STATUSES:
            raise ControlledProofError(
                f"{scenario['scenario_id']} returned non-terminal status {result.status}"
            )
        started = parse_timestamp(result.started_at, "scenario started_at")
        completed = parse_timestamp(result.completed_at, "scenario completed_at")
        if completed < started:
            raise ControlledProofError(f"{scenario['scenario_id']} completed before it started")
        if not result.evidence_refs:
            raise ControlledProofError(f"{scenario['scenario_id']} has no evidence")
        for evidence in result.evidence_refs:
            _validate_evidence_pointer(evidence)

        required_owners = scenario["required_receipt_owners"]
        receipts = list(result.owner_receipts)
        owners = [receipt.get("owner_repo") for receipt in receipts]
        if set(owners) != set(required_owners) or len(owners) != len(set(owners)):
            raise ControlledProofError(
                f"{scenario['scenario_id']} does not have the exact required owner receipts"
            )
        for receipt in receipts:
            validate_owner_receipt(
                receipt,
                authorization=self.authorization,
                authorization_digest=self.authorization_digest,
                scenario=scenario,
                expected_status=result.status,
                contracts=self.contracts,
            )
            recorded_at = parse_timestamp(
                receipt["recorded_at"],
                f"{receipt['owner_repo']} receipt recorded_at",
            )
            if recorded_at < started or recorded_at > completed:
                raise ControlledProofError(
                    f"{receipt['owner_repo']} receipt is outside the scenario timeline"
                )
        return (
            {
                "scenario_id": scenario["scenario_id"],
                "scenario_execution_id": scenario["scenario_execution_id"],
                "status": result.status,
                "evidence_refs": result.evidence_refs,
                "started_at": result.started_at,
                "completed_at": result.completed_at,
            },
            receipts,
        )


def create_platform_receipt(
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    scenario: dict[str, Any],
    owner_result: str,
    evidence_refs: list[dict[str, str]],
    execution_id: str,
    recorded_at: str,
    contracts: ContractSet,
) -> dict[str, Any]:
    unsigned = {
        "owner_repo": "platform-engineering",
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "commissioning_session_id": authorization["commissioning_session"]["commissioning_session_id"],
        "scenario_id": scenario["scenario_id"],
        "scenario_execution_id": scenario["scenario_execution_id"],
        "owner_execution": {
            "execution_type": "platform-action",
            "execution_id": execution_id,
        },
        "owner_result": owner_result,
        "evidence_refs": evidence_refs,
        "receipt_ref": (
            "platform-controlled-proof://receipts/"
            f"{authorization['commissioning_session']['commissioning_session_id']}/"
            f"{scenario['scenario_execution_id']}"
        ),
        "recorded_at": recorded_at,
    }
    receipt = {**unsigned, "receipt_digest": canonical_digest(unsigned)}
    validate_schema(receipt, contracts.platform_receipt, "Platform owner receipt")
    return receipt


def build_stopped_draft(
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    consumption_receipt: dict[str, Any],
    consumption_receipt_digest: str,
    execution_claim: dict[str, Any],
    execution_claim_digest: str,
    scenario_outcomes: list[dict[str, Any]],
    owner_receipts: list[dict[str, Any]],
    failure_reason: str,
    output_root: Path,
    contracts: ContractSet,
    recorded_at: str | None = None,
    session_started_at: str | None = None,
) -> tuple[dict[str, Any], str]:
    if failure_reason not in STOPPED_DRAFT_REASONS:
        raise ControlledProofError("stopped draft reason is not permitted")
    output_root = output_root.expanduser().resolve()
    draft = {
        "schema_version": 1,
        "draft_id": (
            "platform-controlled-proof://stopped-drafts/"
            f"{authorization['commissioning_session']['commissioning_session_id']}"
        ),
        "authorization": {
            "authorization_id": authorization["authorization_id"],
            "authorization_digest": authorization_digest,
            "canonical_claims_digest": authorization["approvals"][
                "canonical_claims_digest"
            ],
        },
        "commissioning_session": {
            "commissioning_session_id": authorization["commissioning_session"][
                "commissioning_session_id"
            ],
            "scenario_execution_count": len(scenario_outcomes),
            "authorization_consumed_at": consumption_receipt["consumed_at"],
            "started_at": session_started_at or _earliest_started_at(scenario_outcomes),
        },
        "consumption_receipt_digest": consumption_receipt_digest,
        "execution_claim": {
            "execution_claim_id": execution_claim["execution_claim_id"],
            "execution_claim_digest": execution_claim_digest,
            "output_root_digest": execution_claim["output_root_digest"],
        },
        "failure_reason": failure_reason,
        "scenario_outcomes": scenario_outcomes,
        "owner_receipts": owner_receipts,
        "recorded_at": recorded_at or now_utc(),
    }
    validate_stopped_draft(
        draft,
        authorization=authorization,
        authorization_digest=authorization_digest,
        consumption_receipt=consumption_receipt,
        consumption_receipt_digest=consumption_receipt_digest,
        execution_claim=execution_claim,
        execution_claim_digest=execution_claim_digest,
        output_root=output_root,
        contracts=contracts,
    )
    draft_path = output_root / STOPPED_DRAFT_NAME
    digest = create_json_exclusive(
        draft_path,
        draft,
        conflict_message="controlled proof stopped draft already exists",
    )
    return draft, digest


def validate_stopped_draft(
    draft: dict[str, Any],
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    consumption_receipt: dict[str, Any],
    consumption_receipt_digest: str,
    execution_claim: dict[str, Any],
    execution_claim_digest: str,
    output_root: Path,
    contracts: ContractSet,
) -> None:
    require_exact_keys(
        draft,
        {
            "schema_version",
            "draft_id",
            "authorization",
            "commissioning_session",
            "consumption_receipt_digest",
            "execution_claim",
            "failure_reason",
            "scenario_outcomes",
            "owner_receipts",
            "recorded_at",
        },
        "stopped result draft",
    )
    if draft["schema_version"] != 1:
        raise ControlledProofError("stopped result draft schema version is unsupported")
    if draft["failure_reason"] not in STOPPED_DRAFT_REASONS:
        raise ControlledProofError("stopped result draft reason is not permitted")
    expected_draft_id = (
        "platform-controlled-proof://stopped-drafts/"
        f"{authorization['commissioning_session']['commissioning_session_id']}"
    )
    if draft["draft_id"] != expected_draft_id:
        raise ControlledProofError("stopped result draft id does not match the session")
    expected_authorization = {
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "canonical_claims_digest": authorization["approvals"][
            "canonical_claims_digest"
        ],
    }
    if draft["authorization"] != expected_authorization:
        raise ControlledProofError("stopped result draft authorization binding does not match")
    session = draft["commissioning_session"]
    require_exact_keys(
        session,
        {
            "commissioning_session_id",
            "scenario_execution_count",
            "authorization_consumed_at",
            "started_at",
        },
        "stopped result draft session",
    )
    expected_session = {
        "commissioning_session_id": authorization["commissioning_session"][
            "commissioning_session_id"
        ],
        "scenario_execution_count": len(SCENARIO_ORDER),
        "authorization_consumed_at": consumption_receipt["consumed_at"],
    }
    if any(session.get(key) != value for key, value in expected_session.items()):
        raise ControlledProofError("stopped result draft session binding does not match")
    if draft["consumption_receipt_digest"] != normalize_digest(
        consumption_receipt_digest, "consumption receipt digest"
    ):
        raise ControlledProofError("stopped result draft consumption binding does not match")
    expected_claim = {
        "execution_claim_id": execution_claim["execution_claim_id"],
        "execution_claim_digest": normalize_digest(
            execution_claim_digest, "execution claim digest"
        ),
        "output_root_digest": execution_claim["output_root_digest"],
    }
    if draft["execution_claim"] != expected_claim:
        raise ControlledProofError("stopped result draft execution binding does not match")
    if execution_claim["output_root_digest"] != sha256_bytes(
        str(output_root.expanduser().resolve()).encode("utf-8")
    ):
        raise ControlledProofError("stopped result draft output root does not match")

    scenarios = authorization["commissioning_session"]["scenario_executions"]
    outcomes = draft["scenario_outcomes"]
    if [item.get("scenario_id") for item in outcomes] != list(SCENARIO_ORDER):
        raise ControlledProofError("stopped result draft scenario order does not match")
    if len(outcomes) != len(scenarios):
        raise ControlledProofError("stopped result draft scenario count does not match")
    session_started = parse_timestamp(session["started_at"], "session started_at")
    consumed_at = parse_timestamp(
        consumption_receipt["consumed_at"], "consumption consumed_at"
    )
    if session_started < consumed_at:
        raise ControlledProofError("stopped result draft session predates consumption")
    scenario_by_id = {item["scenario_id"]: item for item in scenarios}
    outcome_by_id = {item["scenario_id"]: item for item in outcomes}
    for outcome in outcomes:
        require_exact_keys(
            outcome,
            {
                "scenario_id",
                "scenario_execution_id",
                "status",
                "evidence_refs",
                "started_at",
                "completed_at",
            },
            "stopped result draft scenario outcome",
        )
        scenario = scenario_by_id[outcome["scenario_id"]]
        if outcome["scenario_execution_id"] != scenario["scenario_execution_id"]:
            raise ControlledProofError(
                "stopped result draft scenario execution binding does not match"
            )
        if outcome["status"] not in TERMINAL_SCENARIO_STATUSES | {"not-run"}:
            raise ControlledProofError("stopped result draft scenario status is invalid")
        if not outcome["evidence_refs"]:
            raise ControlledProofError("stopped result draft scenario has no evidence")
        for pointer in outcome["evidence_refs"]:
            _validate_evidence_pointer(pointer)
        started = parse_timestamp(outcome["started_at"], "scenario started_at")
        completed = parse_timestamp(outcome["completed_at"], "scenario completed_at")
        if started < session_started or completed < started:
            raise ControlledProofError("stopped result draft scenario timeline is invalid")
    restore_outcome = outcome_by_id["exact-baseline-restore"]
    if restore_outcome["status"] == "passed":
        raise ControlledProofError("stopped result draft cannot claim exact restoration")

    expected_pairs = {
        (scenario["scenario_execution_id"], owner)
        for scenario in scenarios
        for owner in scenario["required_receipt_owners"]
    }
    actual_pairs: set[tuple[str, str]] = set()
    for receipt in draft["owner_receipts"]:
        pair = (receipt.get("scenario_execution_id"), receipt.get("owner_repo"))
        if pair in actual_pairs or pair not in expected_pairs:
            raise ControlledProofError("stopped result draft owner receipt set is invalid")
        actual_pairs.add(pair)
        scenario = next(
            item
            for item in scenarios
            if item["scenario_execution_id"] == receipt["scenario_execution_id"]
        )
        outcome = outcome_by_id[scenario["scenario_id"]]
        validate_owner_receipt(
            receipt,
            authorization=authorization,
            authorization_digest=authorization_digest,
            scenario=scenario,
            expected_status=outcome["status"],
            contracts=contracts,
        )
    restore_pair = (
        scenario_by_id["exact-baseline-restore"]["scenario_execution_id"],
        "platform-engineering",
    )
    if restore_pair not in actual_pairs:
        raise ControlledProofError("stopped result draft lacks the failed restore receipt")
    restore_receipt = next(
        receipt
        for receipt in draft["owner_receipts"]
        if (
            receipt["scenario_execution_id"],
            receipt["owner_repo"],
        )
        == restore_pair
    )
    if restore_receipt["owner_result"] != "failed":
        raise ControlledProofError("stopped result draft restore receipt is not failed")
    recorded_at = parse_timestamp(draft["recorded_at"], "stopped draft recorded_at")
    latest_outcome = max(
        parse_timestamp(item["completed_at"], "scenario completed_at")
        for item in outcomes
    )
    if recorded_at < latest_outcome:
        raise ControlledProofError("stopped result draft predates scenario completion")


def record_governed_exception(
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    consumption_receipt: dict[str, Any],
    consumption_receipt_digest: str,
    execution_claim: dict[str, Any],
    execution_claim_digest: str,
    stopped_draft: dict[str, Any],
    stopped_draft_digest: str,
    output_root: Path,
    decision: str,
    justification: str,
    owner: str,
    review_on: str,
    actor: str,
    note: str,
    contracts: ContractSet,
    recorded_at: str | None = None,
) -> tuple[dict[str, Any], Path, str]:
    validate_stopped_draft(
        stopped_draft,
        authorization=authorization,
        authorization_digest=authorization_digest,
        consumption_receipt=consumption_receipt,
        consumption_receipt_digest=consumption_receipt_digest,
        execution_claim=execution_claim,
        execution_claim_digest=execution_claim_digest,
        output_root=output_root,
        contracts=contracts,
    )
    normalized_draft_digest = normalize_digest(
        stopped_draft_digest, "stopped draft digest"
    )
    rendered_draft_digest = sha256_bytes(
        (json.dumps(stopped_draft, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    if rendered_draft_digest != normalized_draft_digest:
        raise ControlledProofError("stopped result draft digest does not match")
    if decision not in authorization["exception_handling"]["allowed_decisions"]:
        raise ControlledProofError("governed exception decision is not authorized")
    fields = {
        "justification": justification.strip(),
        "owner": owner.strip(),
        "actor": actor.strip(),
    }
    empty = [label for label, value in fields.items() if not value]
    if empty:
        raise ControlledProofError(
            "governed exception fields must not be blank: " + ", ".join(empty)
        )
    try:
        datetime.strptime(review_on, "%Y-%m-%d")
    except ValueError as exc:
        raise ControlledProofError(
            "governed exception review_on must be YYYY-MM-DD"
        ) from exc
    session_id = authorization["commissioning_session"]["commissioning_session_id"]
    exception = {
        "schema_version": 1,
        "record_id": f"platform-controlled-proof://exceptions/{session_id}",
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "commissioning_session_id": session_id,
        "execution_claim_id": execution_claim["execution_claim_id"],
        "execution_claim_digest": execution_claim_digest,
        "stopped_draft_ref": stopped_draft["draft_id"],
        "stopped_draft_digest": stopped_draft_digest,
        "scope": "exact-captured-restore-scope",
        "decision": decision,
        "justification": fields["justification"],
        "owner": fields["owner"],
        "review_on": review_on,
        "recorded_by": fields["actor"],
        "note": note.strip(),
        "recorded_at": recorded_at or now_utc(),
    }
    if parse_timestamp(
        exception["recorded_at"], "governed exception recorded_at"
    ) < parse_timestamp(stopped_draft["recorded_at"], "stopped draft recorded_at"):
        raise ControlledProofError("governed exception predates the stopped draft")
    exception_path = output_root.expanduser().resolve() / GOVERNED_EXCEPTION_NAME
    if exception_path.exists():
        existing = read_bounded_json(exception_path)
        comparable_fields = set(exception) - {"recorded_at"}
        if any(existing.get(key) != exception[key] for key in comparable_fields):
            raise ControlledProofError(
                "governed exception already exists with different content"
            )
        require_exact_keys(existing, set(exception), "governed exception")
        return existing, exception_path, sha256_file(exception_path)
    digest = create_json_exclusive(
        exception_path,
        exception,
        conflict_message="governed exception already exists",
    )
    return exception, exception_path, digest


def finalize_stopped_result(
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    consumption_receipt: dict[str, Any],
    consumption_receipt_digest: str,
    execution_claim: dict[str, Any],
    execution_claim_digest: str,
    stopped_draft: dict[str, Any],
    stopped_draft_digest: str,
    governed_exception: dict[str, Any],
    governed_exception_digest: str,
    output_root: Path,
    contracts: ContractSet,
    completed_at: str | None = None,
) -> tuple[dict[str, Any], str]:
    validate_schema(authorization, contracts.authorization, "authorization")
    validate_authorization_semantics(authorization)
    validate_consumption_binding(
        authorization,
        authorization_digest,
        consumption_receipt,
        consumption_receipt_digest,
        contracts,
    )
    validate_execution_claim_binding(
        authorization=authorization,
        authorization_digest=authorization_digest,
        consumption_receipt=consumption_receipt,
        consumption_receipt_digest=consumption_receipt_digest,
        execution_claim=execution_claim,
        execution_claim_digest=execution_claim_digest,
        output_root=output_root,
    )
    validate_stopped_draft(
        stopped_draft,
        authorization=authorization,
        authorization_digest=authorization_digest,
        consumption_receipt=consumption_receipt,
        consumption_receipt_digest=consumption_receipt_digest,
        execution_claim=execution_claim,
        execution_claim_digest=execution_claim_digest,
        output_root=output_root,
        contracts=contracts,
    )
    if sha256_bytes(
        (json.dumps(stopped_draft, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ) != normalize_digest(stopped_draft_digest, "stopped draft digest"):
        raise ControlledProofError("stopped result draft digest does not match")
    validate_governed_exception(
        governed_exception,
        governed_exception_digest=governed_exception_digest,
        authorization=authorization,
        authorization_digest=authorization_digest,
        execution_claim=execution_claim,
        execution_claim_digest=execution_claim_digest,
        stopped_draft=stopped_draft,
        stopped_draft_digest=stopped_draft_digest,
    )
    result_path = output_root.expanduser().resolve() / STOPPED_RESULT_NAME
    existing = read_bounded_json(result_path) if result_path.exists() else None
    effective_completed_at = completed_at or (
        existing["completed_at"] if existing is not None else now_utc()
    )
    if parse_timestamp(
        effective_completed_at, "stopped result completed_at"
    ) < parse_timestamp(
        governed_exception["recorded_at"], "governed exception recorded_at"
    ):
        raise ControlledProofError("stopped result predates the governed exception")
    result = build_result(
        authorization=authorization,
        authorization_digest=authorization_digest,
        consumption_receipt=consumption_receipt,
        scenario_outcomes=stopped_draft["scenario_outcomes"],
        owner_receipts=stopped_draft["owner_receipts"],
        restore_outcome=stopped_draft["scenario_outcomes"][-1],
        outcome="stopped",
        contracts=contracts,
        completed_at=effective_completed_at,
        restore_status="governed-exception-recorded",
        restore_evidence={
            "artifact_ref": governed_exception["record_id"],
            "artifact_digest": governed_exception_digest,
        },
        exception={
            "decision": governed_exception["decision"],
            "record_ref": governed_exception["record_id"],
            "record_digest": governed_exception_digest,
        },
        session_started_at=stopped_draft["commissioning_session"]["started_at"],
    )
    if existing is not None:
        if existing != result:
            raise ControlledProofError(
                "controlled proof result already exists with different content"
            )
        return existing, sha256_file(result_path)
    return result, create_json_exclusive(
        result_path,
        result,
        conflict_message="controlled proof result already exists",
    )


def validate_governed_exception(
    exception: dict[str, Any],
    *,
    governed_exception_digest: str,
    authorization: dict[str, Any],
    authorization_digest: str,
    execution_claim: dict[str, Any],
    execution_claim_digest: str,
    stopped_draft: dict[str, Any],
    stopped_draft_digest: str,
) -> None:
    require_exact_keys(
        exception,
        {
            "schema_version",
            "record_id",
            "authorization_id",
            "authorization_digest",
            "commissioning_session_id",
            "execution_claim_id",
            "execution_claim_digest",
            "stopped_draft_ref",
            "stopped_draft_digest",
            "scope",
            "decision",
            "justification",
            "owner",
            "review_on",
            "recorded_by",
            "note",
            "recorded_at",
        },
        "governed exception",
    )
    session_id = authorization["commissioning_session"]["commissioning_session_id"]
    expected = {
        "record_id": f"platform-controlled-proof://exceptions/{session_id}",
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "commissioning_session_id": session_id,
        "execution_claim_id": execution_claim["execution_claim_id"],
        "execution_claim_digest": execution_claim_digest,
        "stopped_draft_ref": stopped_draft["draft_id"],
        "stopped_draft_digest": stopped_draft_digest,
        "scope": "exact-captured-restore-scope",
    }
    mismatched = [key for key, value in expected.items() if exception.get(key) != value]
    if exception.get("schema_version") != 1 or mismatched:
        raise ControlledProofError("governed exception binding does not match")
    if exception["decision"] not in authorization["exception_handling"][
        "allowed_decisions"
    ]:
        raise ControlledProofError("governed exception decision is not authorized")
    for field in ("justification", "owner", "recorded_by"):
        if not str(exception[field]).strip():
            raise ControlledProofError(f"governed exception {field} is blank")
    parse_timestamp(exception["recorded_at"], "governed exception recorded_at")
    try:
        datetime.strptime(exception["review_on"], "%Y-%m-%d")
    except ValueError as exc:
        raise ControlledProofError(
            "governed exception review_on must be YYYY-MM-DD"
        ) from exc
    rendered_digest = sha256_bytes(
        (json.dumps(exception, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    if rendered_digest != normalize_digest(
        governed_exception_digest, "governed exception digest"
    ):
        raise ControlledProofError("governed exception digest does not match")
    if parse_timestamp(
        exception["recorded_at"], "governed exception recorded_at"
    ) < parse_timestamp(stopped_draft["recorded_at"], "stopped draft recorded_at"):
        raise ControlledProofError("governed exception predates the stopped draft")


def validate_owner_receipt(
    receipt: dict[str, Any],
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    scenario: dict[str, Any],
    expected_status: str,
    contracts: ContractSet,
) -> None:
    owner = receipt.get("owner_repo")
    schemas = {
        "platform-engineering": contracts.platform_receipt,
        "operator-orchestration-service": contracts.oos_receipt,
        "workspace-governance-control-fabric": contracts.wgcf_receipt,
    }
    if owner not in schemas:
        raise ControlledProofError("receipt owner is not part of the controlled proof")
    validate_schema(receipt, schemas[owner], f"{owner} owner receipt")
    expected = {
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "commissioning_session_id": authorization["commissioning_session"]["commissioning_session_id"],
        "scenario_id": scenario["scenario_id"],
        "scenario_execution_id": scenario["scenario_execution_id"],
    }
    mismatched = [field for field, value in expected.items() if receipt.get(field) != value]
    if mismatched:
        raise ControlledProofError(
            f"{owner} receipt binding mismatch: {', '.join(mismatched)}"
        )
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    if receipt["receipt_digest"] != canonical_digest(unsigned):
        raise ControlledProofError(f"{owner} receipt digest does not match its content")
    if expected_status == "passed" and receipt["owner_result"] != "passed":
        raise ControlledProofError(f"{owner} receipt does not support a passing scenario")
    for evidence in receipt["evidence_refs"]:
        _validate_evidence_pointer(evidence)


def build_result(
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    consumption_receipt: dict[str, Any],
    scenario_outcomes: list[dict[str, Any]],
    owner_receipts: list[dict[str, Any]],
    restore_outcome: dict[str, Any],
    outcome: str,
    contracts: ContractSet,
    completed_at: str | None = None,
    restore_status: str = "exact-baseline-restored",
    restore_evidence: dict[str, str] | None = None,
    exception: dict[str, str] | None = None,
    session_started_at: str | None = None,
) -> dict[str, Any]:
    if [item["scenario_id"] for item in scenario_outcomes] != list(SCENARIO_ORDER):
        raise ControlledProofError("result scenario outcomes do not preserve exact order")
    expected_pairs = {
        (scenario["scenario_execution_id"], owner)
        for scenario in authorization["commissioning_session"]["scenario_executions"]
        for owner in scenario["required_receipt_owners"]
    }
    actual_pairs = {
        (receipt["scenario_execution_id"], receipt["owner_repo"])
        for receipt in owner_receipts
    }
    if len(actual_pairs) != len(owner_receipts):
        raise ControlledProofError("result contains duplicate owner receipts")
    if not actual_pairs.issubset(expected_pairs):
        raise ControlledProofError("result contains an unauthorized owner receipt")
    if outcome == "passed" and actual_pairs != expected_pairs:
        raise ControlledProofError("passing result does not have every required owner receipt")
    if outcome == "passed" and any(item["status"] != "passed" for item in scenario_outcomes):
        raise ControlledProofError("passing result contains a non-passing scenario")
    if outcome == "passed" and any(
        receipt["owner_result"] != "passed" for receipt in owner_receipts
    ):
        raise ControlledProofError("passing result contains a non-passing owner receipt")

    scenarios_by_execution = {
        scenario["scenario_execution_id"]: scenario
        for scenario in authorization["commissioning_session"]["scenario_executions"]
    }
    outcomes_by_execution = {
        scenario["scenario_execution_id"]: scenario for scenario in scenario_outcomes
    }
    for receipt in owner_receipts:
        scenario = scenarios_by_execution[receipt["scenario_execution_id"]]
        scenario_outcome = outcomes_by_execution[receipt["scenario_execution_id"]]
        validate_owner_receipt(
            receipt,
            authorization=authorization,
            authorization_digest=authorization_digest,
            scenario=scenario,
            expected_status=scenario_outcome["status"],
            contracts=contracts,
        )
        recorded_at = parse_timestamp(
            receipt["recorded_at"],
            f"{receipt['owner_repo']} receipt recorded_at",
        )
        if recorded_at < parse_timestamp(
            scenario_outcome["started_at"], "scenario started_at"
        ) or recorded_at > parse_timestamp(
            scenario_outcome["completed_at"], "scenario completed_at"
        ):
            raise ControlledProofError(
                f"{receipt['owner_repo']} receipt is outside the scenario timeline"
            )

    if outcome not in {"passed", "failed", "stopped"}:
        raise ControlledProofError("result outcome is invalid")
    if restore_status not in {
        "exact-baseline-restored",
        "governed-exception-recorded",
    }:
        raise ControlledProofError("result restore status is invalid")
    if outcome == "stopped" and exception is None:
        raise ControlledProofError("stopped result requires a governed exception")
    if outcome != "stopped" and exception is not None:
        raise ControlledProofError("non-stopped result cannot carry an exception")
    if restore_status == "governed-exception-recorded" and outcome != "stopped":
        raise ControlledProofError("restore exception requires a stopped result")
    selected_restore_evidence = (
        restore_evidence or restore_outcome["evidence_refs"][0]
    )
    _validate_evidence_pointer(selected_restore_evidence)
    result = {
        "schema_version": 2,
        "result_id": (
            "platform-controlled-proof://results/"
            f"{authorization['commissioning_session']['commissioning_session_id']}"
        ),
        "authorization": {
            "authorization_id": authorization["authorization_id"],
            "authorization_digest": authorization_digest,
            "canonical_claims_digest": authorization["approvals"]["canonical_claims_digest"],
        },
        "commissioning_session": {
            "commissioning_session_id": authorization["commissioning_session"]["commissioning_session_id"],
            "scenario_execution_count": len(scenario_outcomes),
            "authorization_consumed_at": consumption_receipt["consumed_at"],
            "started_at": session_started_at or _earliest_started_at(scenario_outcomes),
        },
        "outcome": outcome,
        "scenario_outcomes": scenario_outcomes,
        "owner_receipts": owner_receipts,
        "baseline_restore": {
            "baseline_snapshot_ref": authorization["baseline_and_restore"]["baseline_snapshot_ref"],
            "baseline_snapshot_digest": authorization["baseline_and_restore"]["baseline_snapshot_digest"],
            "status": restore_status,
            "evidence_ref": selected_restore_evidence["artifact_ref"],
            "evidence_digest": selected_restore_evidence["artifact_digest"],
        },
        "completed_at": completed_at or now_utc(),
    }
    if exception is not None:
        result["exception"] = exception
    validate_schema(result, contracts.result, "controlled proof result")
    validate_result_semantics(
        result,
        authorization=authorization,
        authorization_digest=authorization_digest,
    )
    return result


def validate_result_semantics(
    result: dict[str, Any],
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
) -> None:
    expected_authorization = {
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "canonical_claims_digest": authorization["approvals"][
            "canonical_claims_digest"
        ],
    }
    if result["authorization"] != expected_authorization:
        raise ControlledProofError("result authorization binding does not match")
    if result["commissioning_session"]["commissioning_session_id"] != (
        authorization["commissioning_session"]["commissioning_session_id"]
    ):
        raise ControlledProofError("result commissioning session does not match")
    expected_executions = {
        item["scenario_id"]: item["scenario_execution_id"]
        for item in authorization["commissioning_session"]["scenario_executions"]
    }
    actual_executions = {
        item["scenario_id"]: item["scenario_execution_id"]
        for item in result["scenario_outcomes"]
    }
    if actual_executions != expected_executions:
        raise ControlledProofError("result scenario executions do not match authorization")
    if result["baseline_restore"]["baseline_snapshot_ref"] != (
        authorization["baseline_and_restore"]["baseline_snapshot_ref"]
    ) or result["baseline_restore"]["baseline_snapshot_digest"] != (
        authorization["baseline_and_restore"]["baseline_snapshot_digest"]
    ):
        raise ControlledProofError("result baseline binding does not match authorization")
    started_at = parse_timestamp(
        result["commissioning_session"]["started_at"], "result started_at"
    )
    completed_at = parse_timestamp(result["completed_at"], "result completed_at")
    consumed_at = parse_timestamp(
        result["commissioning_session"]["authorization_consumed_at"],
        "result authorization_consumed_at",
    )
    issued_at = parse_timestamp(
        authorization["window"]["issued_at"], "authorization issued_at"
    )
    expires_at = parse_timestamp(
        authorization["window"]["expires_at"], "authorization expires_at"
    )
    if consumed_at < issued_at or consumed_at >= expires_at:
        raise ControlledProofError("result permit consumption is outside authority")
    if started_at < consumed_at or started_at >= expires_at:
        raise ControlledProofError("result session start is outside authority")
    if completed_at < started_at:
        raise ControlledProofError("result timeline does not match permit consumption")
    latest_scenario_completion = started_at
    for outcome in result["scenario_outcomes"]:
        scenario_started = parse_timestamp(
            outcome["started_at"], "result scenario started_at"
        )
        scenario_completed = parse_timestamp(
            outcome["completed_at"], "result scenario completed_at"
        )
        if scenario_started < started_at or scenario_started >= expires_at:
            raise ControlledProofError("result scenario start is outside authority")
        if scenario_completed < scenario_started:
            raise ControlledProofError("result scenario timeline is invalid")
        latest_scenario_completion = max(
            latest_scenario_completion,
            scenario_completed,
        )
    if completed_at < latest_scenario_completion:
        raise ControlledProofError("result completes before its scenarios")
    if result["outcome"] == "passed" and completed_at >= expires_at:
        raise ControlledProofError("passing result completed after authorization expiry")
    if result["outcome"] == "stopped":
        exception = result.get("exception") or {}
        if result["baseline_restore"]["status"] != "governed-exception-recorded":
            raise ControlledProofError("stopped result lacks governed restore closure")
        if exception.get("record_ref") != result["baseline_restore"]["evidence_ref"]:
            raise ControlledProofError("stopped result exception reference does not match")
        if exception.get("record_digest") != result["baseline_restore"][
            "evidence_digest"
        ]:
            raise ControlledProofError("stopped result exception digest does not match")


def _earliest_started_at(outcomes: list[dict[str, Any]]) -> str:
    started = [item["started_at"] for item in outcomes if item["status"] != "not-run"]
    if not started:
        raise ControlledProofError("result has no started scenario")
    return min(started, key=lambda value: parse_timestamp(value, "scenario started_at"))


def _validate_evidence_pointer(pointer: dict[str, str]) -> None:
    if set(pointer) != {"artifact_ref", "artifact_digest"}:
        raise ControlledProofError("evidence pointer fields are invalid")
    if not isinstance(pointer["artifact_ref"], str) or "://" not in pointer["artifact_ref"]:
        raise ControlledProofError("evidence reference is not a URI")
    normalize_digest(pointer["artifact_digest"], "evidence digest")
