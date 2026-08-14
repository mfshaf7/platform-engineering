from __future__ import annotations

import copy
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any
from unittest import mock
from urllib import error as urlerror

import yaml

PROFILE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROFILE_ROOT.parents[2]
sys.path.insert(0, str(PROFILE_ROOT))

import controlled_proof.authority as authority_module  # noqa: E402
import controlled_proof.execution as execution_module  # noqa: E402
import controlled_proof.model as model_module  # noqa: E402
import controlled_proof.runtime as runtime_module  # noqa: E402
import validate_source as validate_source_module  # noqa: E402
from controlled_proof.authority import (  # noqa: E402
    EXPECTED_BASELINE_STATES,
    EXPECTED_RUNTIME_IDENTITIES,
    EXPECTED_TASK_QUEUES,
    OWNER_RUNTIME_IMAGES,
    PROBE_IDS,
    SURFACE_ORDER,
    EXECUTION_SOURCE_REPOS,
    SECURITY_AUTHORIZATION_MERGED_REF,
    SECURITY_AUTHORIZATION_SOURCE_REPO,
    GitSourceResolver,
    assemble_claims,
    capture_baseline,
    claim_execution,
    consume_authorization,
    controlled_runtime_state_root,
    execution_scope_lease_path,
    issue_permit,
    load_contracts,
    prepare_claims,
    release_execution_scope_lease,
    reviewed_contract_source_revisions,
    validate_authorization,
)
from controlled_proof.cli import (  # noqa: E402
    _canonical_execution_output_root,
    _execution_lock,
    _validate_execution_output_root,
    validate_claims_command,
)
from controlled_proof.execution import (  # noqa: E402
    GOVERNED_EXCEPTION_NAME,
    STOPPED_DRAFT_NAME,
    STOPPED_RESULT_NAME,
    ControlledProofExecutor,
    ProjectedContexts,
    ScenarioExecutionResult,
    build_result,
    create_platform_receipt,
    finalize_stopped_result,
    project_owner_contexts,
    record_governed_exception,
)
from controlled_proof.model import (  # noqa: E402
    CONTROLLED_EXECUTABLE_PATH,
    PERMITTED_ACTIONS,
    REQUIRED_SCENARIO_OWNERS,
    REQUIRED_STOP_CONDITIONS,
    SCENARIO_ORDER,
    TERMINAL_CLEANUP_START_RESERVE_SECONDS,
    ControlledProofError,
    canonical_digest,
    controlled_subprocess_environment,
    create_json_exclusive,
    now_utc,
    operator_scope_id,
    operator_scoped_dns_label,
    read_bounded_json,
    read_bounded_json_with_digest,
    sha256_file,
    write_json_atomic,
)
from controlled_proof.runtime import (  # noqa: E402
    CommandResult,
    ControlledRuntimeDriver,
    LocalK3sRuntimeControl,
    RuntimeArtifactBindings,
    _local_api_endpoint,
    _owner_runtime_manifest,
    _validate_loaded_wgcf_receipt,
    _wgcf_receipt_binding,
    validate_runtime_action_binding,
)

PLATFORM_DRILL_SPEC = importlib.util.spec_from_file_location(
    "platform_drill", REPO_ROOT / "scripts" / "platform_drill.py"
)
if PLATFORM_DRILL_SPEC is None or PLATFORM_DRILL_SPEC.loader is None:
    raise RuntimeError("could not load platform_drill module")
platform_drill = importlib.util.module_from_spec(PLATFORM_DRILL_SPEC)
PLATFORM_DRILL_SPEC.loader.exec_module(platform_drill)


REVISION = "a" * 40
DIGEST = "sha256:" + "c" * 64
SOURCE_REVISIONS = {
    **{
        "platform-engineering": REVISION,
        "security-architecture": "b" * 40,
    },
    **reviewed_contract_source_revisions(),
}


class FakeSourceResolver:
    def __init__(self, dirty_repo: str | None = None):
        self.revisions = dict(SOURCE_REVISIONS)
        self.merged_revisions = {
            (repo, revision) for repo, revision in self.revisions.items()
        }
        self.dirty_repo = dirty_repo
        self.source_files: dict[tuple[str, str, str], bytes] = {}

    def revision(self, repo: str) -> tuple[str, bool]:
        return self.revisions[repo], repo == self.dirty_repo

    def revision_is_ancestor_of(
        self, repo: str, revision: str, ref: str
    ) -> bool:
        return (
            ref == SECURITY_AUTHORIZATION_MERGED_REF
            and (repo, revision) in self.merged_revisions
        )

    def add_file(self, repo: str, relative_path: str, content: bytes) -> None:
        self.source_files[(repo, self.revisions[repo], relative_path)] = content

    def read_file(
        self,
        repo: str,
        revision: str,
        relative_path: str,
        *,
        require_current_checkout: bool = True,
    ) -> bytes:
        if require_current_checkout:
            current_revision, dirty = self.revision(repo)
            if dirty or current_revision != revision:
                raise ControlledProofError(
                    "source artifact repo is not clean at its bound revision"
                )
        try:
            return self.source_files[(repo, revision, relative_path)]
        except KeyError as exc:
            raise ControlledProofError("source artifact is unavailable") from exc


def initialize_git_repo(root: Path, seed_name: str) -> str:
    remote_root = root.parent / f"{root.name}-origin.git"
    subprocess.run(
        ["git", "init", "--bare", "--quiet", "--initial-branch=main", str(remote_root)],
        check=True,
    )
    root.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch=main", str(root)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "remote", "add", "origin", str(remote_root)],
        check=True,
    )
    (root / seed_name).write_text("reviewed source\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", seed_name], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Controlled Proof Test",
            "-c",
            "user.email=controlled-proof@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "seed reviewed source",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "push", "--quiet", "-u", "origin", "main"],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def merge_git_branch_to_main(root: Path, branch: str) -> str:
    subprocess.run(["git", "-C", str(root), "checkout", "--quiet", "main"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Controlled Proof Test",
            "-c",
            "user.email=controlled-proof@example.invalid",
            "merge",
            "--quiet",
            "--no-ff",
            branch,
            "-m",
            "merge reviewed security authorization",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "push", "--quiet", "origin", "main"],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit_git_path(root: Path, relative_path: str, message: str) -> str:
    subprocess.run(["git", "-C", str(root), "add", relative_path], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Controlled Proof Test",
            "-c",
            "user.email=controlled-proof@example.invalid",
            "commit",
            "--quiet",
            "-m",
            message,
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class RealApprovalSourceResolver(FakeSourceResolver):
    def __init__(self, workspace_root: Path):
        super().__init__()
        self.git = GitSourceResolver(workspace_root)

    def revision(self, repo: str) -> tuple[str, bool]:
        if repo in {"platform-engineering", SECURITY_AUTHORIZATION_SOURCE_REPO}:
            return self.git.revision(repo)
        return super().revision(repo)

    def revision_is_ancestor_of(
        self, repo: str, revision: str, ref: str
    ) -> bool:
        if repo == SECURITY_AUTHORIZATION_SOURCE_REPO:
            return self.git.revision_is_ancestor_of(repo, revision, ref)
        return super().revision_is_ancestor_of(repo, revision, ref)

    def read_file(
        self,
        repo: str,
        revision: str,
        relative_path: str,
        *,
        require_current_checkout: bool = True,
    ) -> bytes:
        if repo == SECURITY_AUTHORIZATION_SOURCE_REPO:
            return self.git.read_file(
                repo,
                revision,
                relative_path,
                require_current_checkout=require_current_checkout,
            )
        return super().read_file(
            repo,
            revision,
            relative_path,
            require_current_checkout=require_current_checkout,
        )


class FakeProbe:
    def capture(self, surface_id: str) -> tuple[str, dict[str, object]]:
        return EXPECTED_BASELINE_STATES[surface_id], {
            "schema_version": 1,
            "surface_id": surface_id,
            "probe_id": PROBE_IDS[surface_id],
            "exit_code": 0,
            "stdout": f"stable:{surface_id}",
            "stderr": "",
        }


class FailingProbe(FakeProbe):
    def capture(self, surface_id: str) -> tuple[str, dict[str, object]]:
        if surface_id == "oos-validation-readiness-worker":
            raise ControlledProofError("probe failed")
        return super().capture(surface_id)


def timestamp(delta: timedelta = timedelta()) -> str:
    return (
        (datetime.now(timezone.utc) + delta)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def runtime_artifacts() -> list[dict[str, str]]:
    contract_root = PROFILE_ROOT / "controlled_proof" / "contracts"
    lock = yaml.safe_load(
        (PROFILE_ROOT / "runtime" / "artifact-lock.yaml").read_text(
            encoding="utf-8"
        )
    )
    return [
        {
            "artifact_id": "platform:temporal-profile",
            "digest": sha256_file(PROFILE_ROOT / "profile.yaml"),
        },
        {
            "artifact_id": "platform:temporal-artifact-lock",
            "digest": sha256_file(PROFILE_ROOT / "runtime" / "artifact-lock.yaml"),
        },
        {
            "artifact_id": "platform:temporal-boundary-contract",
            "digest": sha256_file(
                PROFILE_ROOT / "runtime" / "boundary-contract.yaml"
            ),
        },
        {
            "artifact_id": "platform:controlled-proof-contract-set",
            "digest": sha256_file(contract_root / "source-manifest.yaml"),
        },
        {
            "artifact_id": "platform:temporal-chart",
            "digest": f"sha256:{lock['chart']['sha256']}",
        },
    ]


def runtime_images() -> list[dict[str, str]]:
    lock = yaml.safe_load(
        (PROFILE_ROOT / "runtime" / "artifact-lock.yaml").read_text(
            encoding="utf-8"
        )
    )
    images = [
        {
            "image_ref": f"{item['repository']}:{item['tag']}",
            "digest": item["digest"],
        }
        for item in lock["images"].values()
    ]
    images.extend(
        {"image_ref": image_ref, "digest": DIGEST}
        for image_ref in sorted(OWNER_RUNTIME_IMAGES)
    )
    return images


def claims_for(baseline: dict[str, object], baseline_digest: str) -> dict[str, object]:
    execution_source_revisions = [
        {"repo": repo, "commit": SOURCE_REVISIONS[repo]}
        for repo in EXECUTION_SOURCE_REPOS
    ]
    scenarios = [
        {
            "scenario_id": scenario_id,
            "scenario_execution_id": f"session-001:{index:02d}:{scenario_id}",
            "required_receipt_owners": list(
                REQUIRED_SCENARIO_OWNERS[scenario_id]
            ),
        }
        for index, scenario_id in enumerate(SCENARIO_ORDER, start=1)
    ]
    reviewed_source = {
        "owner_repo": "platform-engineering",
        "implementation_ref": "openproject://work_packages/825",
        "source_revision": REVISION,
        "review_packet_ref": "artifact://review-packets/platform-825",
    }
    return {
        "schema_version": 4,
        "authorization_id": "platform-controlled-proof://authorizations/session-001",
        "authority_type": "runtime-drill",
        "drill_type": "component-commissioning-proof",
        "target": {
            "profile_id": "temporal",
            "profile_lifecycle": "build-admitted",
            "environment": "dev-integration",
        },
        "scope": {
            "allowed_definitions": [
                {
                    "definition_id": "validation-readiness-run",
                    "definition_version": 1,
                }
            ],
            "execution_source_revisions": execution_source_revisions,
            "runtime_artifacts": runtime_artifacts(),
            "runtime_images": runtime_images(),
            "target_namespaces": [
                operator_scoped_dns_label("governance", str(baseline["operator_id"]))
            ],
            "runtime_identities": [
                {"role": role, "identity": identity}
                for role, identity in EXPECTED_RUNTIME_IDENTITIES.items()
            ],
            "task_queues": [
                {"owner_repo": owner, "queue_name": queue}
                for owner, queue in EXPECTED_TASK_QUEUES.items()
            ],
            "permitted_actions": list(PERMITTED_ACTIONS),
        },
        "commissioning_session": {
            "commissioning_session_id": "session-001",
            "consumption_mode": "atomic-single-use",
            "consume_before_first_mutation": True,
            "duplicate_consumption_denied": True,
            "scenario_executions": scenarios,
        },
        "permit_issuer": copy.deepcopy(reviewed_source),
        "executor": copy.deepcopy(reviewed_source),
        "window": {
            "issued_at": timestamp(timedelta(seconds=-30)),
            "expires_at": timestamp(timedelta(hours=1)),
        },
        "evidence": {
            "owner_repo": "platform-engineering",
            "verification_pack_ref": "artifact://controlled-proof/verification/session-001",
        },
        "baseline_and_restore": {
            "baseline_snapshot_ref": baseline["baseline_id"],
            "baseline_snapshot_digest": baseline_digest,
            "restore_mode": "exact-baseline",
            "restore_scope": list(SURFACE_ORDER),
            "terminal_cleanup_authority": {
                "mode": "exact-baseline-restore-only",
                "applies_to": "already-started-commissioning-session",
                "trigger_scope": "any-triggered-stop-condition",
                "scope_binding": "exact-captured-restore-scope",
                "new_proof_actions_denied": True,
                "scope_expansion_denied": True,
                "runtime_retention_denied": True,
                "permitted_actions": [
                    "remove-scoped-runtime",
                    "restore-exact-baseline",
                    "record-restore-evidence",
                    "record-governed-exception",
                ],
                "termination_conditions": [
                    "exact-baseline-restored",
                    "governed-exception-recorded",
                ],
            },
        },
        "exception_handling": {
            "allowed_decisions": ["remove", "workaround", "accept-risk", "defer"],
            "record_ref_required": True,
        },
        "stop_conditions": list(REQUIRED_STOP_CONDITIONS),
    }


def write_approval(
    path: Path,
    *,
    role: str,
    claims: dict[str, object],
    claims_digest: str,
    source_path: str | None = None,
) -> None:
    approval = {
        "schema_version": 1,
        "approval_id": f"artifact://controlled-proof/approvals/{role}",
        "approval_role": role,
        "decision": "approved",
        "authorization_id": claims["authorization_id"],
        "canonicalization": "rfc8785",
        "canonical_claims_digest": claims_digest,
        "approved_by": "test-reviewer",
        "approved_at": timestamp(timedelta(minutes=-1)),
    }
    if role == "security-authorization":
        approval["source_provenance"] = {
            "owner_repo": "security-architecture",
            "source_path": source_path,
        }
    write_json_atomic(
        path,
        approval,
    )


class ProofFixture:
    def __init__(self, root: Path, *, operator_id: str = "alice"):
        self.root = root
        self.contracts = load_contracts()
        self.source = FakeSourceResolver()
        self.baseline_path = root / "baseline.json"
        self.evidence_root = root / "baseline-evidence"
        self.baseline, self.baseline_digest = capture_baseline(
            baseline_id="artifact://controlled-proof/baselines/session-001",
            operator_id=operator_id,
            output_path=self.baseline_path,
            evidence_root=self.evidence_root,
            source_resolver=self.source,
            probe=FakeProbe(),
            contracts=self.contracts,
            captured_at=timestamp(timedelta(minutes=-10)),
        )
        self.claims = claims_for(self.baseline, self.baseline_digest)
        _, self.claims_digest = prepare_claims(
            self.claims, contracts=self.contracts
        )
        self.operator_approval = root / "operator-approval.json"
        self.security_approval = root / "security-authorization.json"
        self.security_source_path = (
            "records/controlled-proof-authorizations/session-001.json"
        )
        write_approval(
            self.operator_approval,
            role="operator-approval",
            claims=self.claims,
            claims_digest=self.claims_digest,
        )
        write_approval(
            self.security_approval,
            role="security-authorization",
            claims=self.claims,
            claims_digest=self.claims_digest,
            source_path=self.security_source_path,
        )
        self.source.add_file(
            "security-architecture",
            self.security_source_path,
            self.security_approval.read_bytes(),
        )
        self.authorization = issue_permit(
            claims=self.claims,
            operator_approval_path=self.operator_approval,
            security_approval_path=self.security_approval,
            baseline_path=self.baseline_path,
            baseline_evidence_root=self.evidence_root,
            source_resolver=self.source,
            contracts=self.contracts,
        )
        self.authorization_path = root / "authorization.json"
        self.authorization_digest = write_json_atomic(
            self.authorization_path, self.authorization
        )
        (
            self.consumption,
            self.consumption_path,
            self.consumption_digest,
        ) = consume_authorization(
            authorization=self.authorization,
            authorization_digest=self.authorization_digest,
            executor_source_revision=REVISION,
            consumption_root=root / "consumptions",
            contracts=self.contracts,
        )
        self.contexts = project_owner_contexts(
            authorization=self.authorization,
            authorization_digest=self.authorization_digest,
            consumption_receipt=self.consumption,
            consumption_receipt_digest=self.consumption_digest,
            baseline=self.baseline,
            output_root=root / "contexts",
            contracts=self.contracts,
        )

    def claim_for(
        self, output_root: Path
    ) -> tuple[dict[str, object], Path, str]:
        return claim_execution(
            authorization=self.authorization,
            authorization_digest=self.authorization_digest,
            consumption_receipt=self.consumption,
            consumption_receipt_digest=self.consumption_digest,
            output_root=output_root,
            operator_id=self.baseline["operator_id"],
            execution_root=self.root / "execution-claims",
            contracts=self.contracts,
        )


def owner_receipt(
    fixture: ProofFixture,
    scenario: dict[str, object],
    owner: str,
    recorded_at: str,
) -> dict[str, object]:
    evidence = {
        "artifact_ref": f"artifact://test/{owner}/{scenario['scenario_id']}",
        "artifact_digest": DIGEST,
    }
    if owner == "platform-engineering":
        return create_platform_receipt(
            authorization=fixture.authorization,
            authorization_digest=fixture.authorization_digest,
            scenario=scenario,
            owner_result="passed",
            evidence_refs=[evidence],
            execution_id=f"platform:{scenario['scenario_execution_id']}",
            recorded_at=recorded_at,
            contracts=fixture.contracts,
        )
    execution_type = (
        "workflow" if owner == "operator-orchestration-service" else "activity"
    )
    unsigned = {
        "owner_repo": owner,
        "authorization_id": fixture.authorization["authorization_id"],
        "authorization_digest": fixture.authorization_digest,
        "commissioning_session_id": fixture.authorization["commissioning_session"][
            "commissioning_session_id"
        ],
        "scenario_id": scenario["scenario_id"],
        "scenario_execution_id": scenario["scenario_execution_id"],
        "owner_execution": {
            "execution_type": execution_type,
            "execution_id": f"{execution_type}:{scenario['scenario_execution_id']}",
        },
        "owner_result": "passed",
        "evidence_refs": [evidence],
        "receipt_ref": f"artifact://test/receipts/{owner}/{scenario['scenario_id']}",
        "recorded_at": recorded_at,
    }
    return {**unsigned, "receipt_digest": canonical_digest(unsigned)}


def executor_for(
    fixture: ProofFixture,
    driver: "FakeDriver",
    output_root: Path,
) -> ControlledProofExecutor:
    claim, _claim_path, claim_digest = fixture.claim_for(output_root)
    return ControlledProofExecutor(
        authorization=fixture.authorization,
        authorization_digest=fixture.authorization_digest,
        consumption_receipt=fixture.consumption,
        consumption_receipt_digest=fixture.consumption_digest,
        execution_claim=claim,
        execution_claim_digest=claim_digest,
        baseline=fixture.baseline,
        contexts=fixture.contexts,
        contracts=fixture.contracts,
        driver=driver,
        output_root=output_root,
    )


class FakeDriver:
    def __init__(
        self,
        fixture: ProofFixture,
        *,
        fail_scenario: str | None = None,
        fail_restore: bool = False,
        fail_prepare: bool = False,
        fail_cleanup: bool = False,
        stale_receipt: bool = False,
    ):
        self.fixture = fixture
        self.fail_scenario = fail_scenario
        self.fail_restore = fail_restore
        self.fail_prepare = fail_prepare
        self.fail_cleanup = fail_cleanup
        self.stale_receipt = stale_receipt
        self.cleaned = False

    def prepare(self, contexts: ProjectedContexts) -> None:
        if self.fail_prepare:
            raise ControlledProofError(
                "prepare failed",
                evidence_refs=[
                    {
                        "artifact_ref": "artifact://test/runtime/prepare-failure",
                        "artifact_digest": DIGEST,
                    }
                ],
            )
        self._check_contexts(contexts)

    def execute_scenario(
        self,
        scenario: dict[str, object],
        contexts: ProjectedContexts,
    ) -> ScenarioExecutionResult:
        self._check_contexts(contexts)
        if scenario["scenario_id"] == self.fail_scenario:
            raise ControlledProofError("scenario failed")
        scenario_time = now_utc()
        receipt_time = (
            timestamp(timedelta(hours=-1)) if self.stale_receipt else now_utc()
        )
        evidence = {
            "artifact_ref": f"artifact://test/scenarios/{scenario['scenario_id']}",
            "artifact_digest": DIGEST,
        }
        return ScenarioExecutionResult(
            status="passed",
            evidence_refs=[evidence],
            owner_receipts=[
                owner_receipt(self.fixture, scenario, owner, receipt_time)
                for owner in scenario["required_receipt_owners"]
            ],
            started_at=scenario_time,
            completed_at=now_utc(),
        )

    def restore_exact_baseline(
        self,
        scenario: dict[str, object],
        contexts: ProjectedContexts,
        baseline: dict[str, object],
    ) -> ScenarioExecutionResult:
        self._check_contexts(contexts)
        if baseline != self.fixture.baseline or self.fail_restore:
            raise ControlledProofError("restore failed")
        recorded_at = now_utc()
        evidence = {
            "artifact_ref": "artifact://test/restore/exact-baseline",
            "artifact_digest": DIGEST,
        }
        return ScenarioExecutionResult(
            status="passed",
            evidence_refs=[evidence],
            owner_receipts=[
                owner_receipt(
                    self.fixture,
                    scenario,
                    "platform-engineering",
                    recorded_at,
                )
            ],
            started_at=recorded_at,
            completed_at=recorded_at,
        )

    def cleanup(self, contexts: ProjectedContexts) -> None:
        self._check_contexts(contexts)
        if self.fail_cleanup:
            raise ControlledProofError("cleanup failed")
        self.cleaned = True

    def _check_contexts(self, contexts: ProjectedContexts) -> None:
        if contexts != self.fixture.contexts:
            raise ControlledProofError("contexts changed")


class ControlledProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="controlled-proof-test-")
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_operator_scoped_namespaces_are_stable_and_collision_resistant(self) -> None:
        self.assertEqual(
            operator_scoped_dns_label("governance", "alice"),
            "governance-alice",
        )
        first = "operator-" + "a" * 80 + "-one"
        second = "operator-" + "a" * 80 + "-two"
        for prefix in ("governance", "devint-temporal"):
            first_label = operator_scoped_dns_label(prefix, first)
            second_label = operator_scoped_dns_label(prefix, second)
            self.assertLessEqual(len(first_label), 63)
            self.assertLessEqual(len(second_label), 63)
            self.assertNotEqual(first_label, second_label)
        self.assertNotEqual(
            operator_scoped_dns_label("governance", "alice.example"),
            operator_scoped_dns_label("governance", "alice-example"),
        )
        self.assertNotEqual(
            operator_scoped_dns_label("governance", "Alice"),
            operator_scoped_dns_label("governance", "alice"),
        )

    def test_runtime_adapter_propagates_exact_collision_resistant_scope(self) -> None:
        fixture = ProofFixture(self.root / "fixture", operator_id="alice.example")
        workspace_root = self.root / "workspace"

        class RecordingRunner:
            def __init__(self) -> None:
                self.environment: dict[str, str] = {}
                self.commands: list[list[str]] = []

            def run(
                self,
                command: list[str],
                *,
                env: dict[str, str] | None = None,
                input_text: str | None = None,
                pass_fds: tuple[int, ...] = (),
                timeout: float = 600,
            ) -> CommandResult:
                del input_text, pass_fds, timeout
                self.commands.append(command)
                self.environment = dict(env or {})
                return CommandResult(stdout="", stderr="", returncode=0)

        runner = RecordingRunner()
        output_root = self.root / "output"
        _claim, execution_claim_path, execution_claim_digest = fixture.claim_for(
            output_root
        )
        artifacts = RuntimeArtifactBindings(
            authorization_path=fixture.authorization_path,
            authorization_digest=fixture.authorization_digest,
            operator_approval_path=fixture.operator_approval,
            security_approval_path=fixture.security_approval,
            baseline_path=fixture.baseline_path,
            baseline_evidence_root=fixture.evidence_root,
            consumption_receipt_path=fixture.consumption_path,
            consumption_receipt_digest=fixture.consumption_digest,
            execution_claim_path=execution_claim_path,
            execution_claim_digest=execution_claim_digest,
        )
        control = LocalK3sRuntimeControl(
            authorization=fixture.authorization,
            baseline=fixture.baseline,
            contexts=fixture.contexts,
            artifacts=artifacts,
            output_root=output_root,
            workspace_root=workspace_root,
            runner=runner,
        )
        control.platform_executor_snapshot.mkdir(parents=True)
        output_root.mkdir(parents=True, exist_ok=True)
        runtime_relative = PurePosixPath(
            "dev-integration/profiles/temporal/scripts/controlled-proof-runtime.sh"
        )
        with mock.patch.object(
            control,
            "_assert_platform_executor_snapshot",
            return_value={runtime_relative: (b"#!/usr/bin/env bash\nexit 0\n", 0o755)},
        ):
            control._runtime_script("prepare")

        expected_temporal_namespace = operator_scoped_dns_label(
            "governance", "alice.example"
        )
        self.assertEqual(
            runner.environment["DEVINT_TEMPORAL_WORKFLOW_NAMESPACE"],
            expected_temporal_namespace,
        )
        self.assertEqual(
            runner.environment["DEVINT_STATE_ROOT"],
            str(controlled_runtime_state_root(workspace_root, "alice.example")),
        )
        self.assertEqual(
            runner.environment["DEVINT_WORKSPACE_ROOT"],
            str(workspace_root / "platform-engineering"),
        )
        self.assertEqual(
            runner.environment["CONTROLLED_PROOF_OPERATOR_SCOPE"],
            operator_scope_id("alice.example"),
        )
        self.assertEqual(
            runner.environment["CONTROLLED_PROOF_WORKSPACE_ROOT"],
            str(workspace_root),
        )
        self.assertEqual(runner.commands[-1][0], "bwrap")
        self.assertIn(
            str(
                control.platform_executor_snapshot
                / "dev-integration"
                / "profiles"
                / "temporal"
                / "scripts"
                / "controlled-proof-runtime.sh"
            ),
            runner.commands[-1],
        )
        self.assertNotEqual(expected_temporal_namespace, "governance-alice-example")

    def test_runtime_executes_sealed_attested_bytes_not_mutable_snapshot_path(
        self,
    ) -> None:
        fixture = ProofFixture(self.root / "fixture")
        output_root = self.root / "output"
        _claim, claim_path, claim_digest = fixture.claim_for(output_root)
        control = LocalK3sRuntimeControl(
            authorization=fixture.authorization,
            baseline=fixture.baseline,
            contexts=fixture.contexts,
            artifacts=RuntimeArtifactBindings(
                authorization_path=fixture.authorization_path,
                authorization_digest=fixture.authorization_digest,
                operator_approval_path=fixture.operator_approval,
                security_approval_path=fixture.security_approval,
                baseline_path=fixture.baseline_path,
                baseline_evidence_root=fixture.evidence_root,
                consumption_receipt_path=fixture.consumption_path,
                consumption_receipt_digest=fixture.consumption_digest,
                execution_claim_path=claim_path,
                execution_claim_digest=claim_digest,
            ),
            output_root=output_root,
            workspace_root=self.root / "workspace",
        )
        runtime_relative = PurePosixPath(
            "dev-integration/profiles/temporal/scripts/controlled-proof-runtime.sh"
        )
        runtime_path = control.platform_executor_snapshot.joinpath(
            *runtime_relative.parts
        )
        runtime_path.parent.mkdir(parents=True)
        runtime_path.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'mutable-path\\n' > "
            '"${CONTROLLED_PROOF_OUTPUT_ROOT}/executed.txt"\n',
            encoding="utf-8",
        )
        runtime_path.chmod(0o755)
        attested_runtime = (
            b"#!/usr/bin/env bash\n"
            b"set -euo pipefail\n"
            b"readonly STATE_ROOT=\"${DEVINT_STATE_ROOT:?}\"\n"
            b"readonly OWNER_REPO_ROOT=/sealed-owner-repo\n"
            b"readonly PROFILE_ID=\"${DEVINT_PROFILE_ID:?}\"\n"
            b"readonly OPERATOR_SLUG=unused\n"
            b"source \"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)"
            b"/lib/persistence.sh\"\n"
            b"assert_state_root_boundary\n"
            b"printf 'sealed-attested\\n' > "
            b'"${CONTROLLED_PROOF_OUTPUT_ROOT}/executed.txt"\n'
        )
        persistence_relative = PurePosixPath(
            "dev-integration/profiles/temporal/scripts/lib/persistence.sh"
        )
        with mock.patch.object(
            control,
            "_assert_platform_executor_snapshot",
            return_value={
                runtime_relative: (attested_runtime, 0o755),
                persistence_relative: (
                    (PROFILE_ROOT / "scripts" / "lib" / "persistence.sh").read_bytes(),
                    0o644,
                ),
            },
        ):
            control._runtime_script("prepare")

        self.assertEqual(
            (output_root / "executed.txt").read_text(encoding="utf-8"),
            "sealed-attested\n",
        )

    def test_runtime_command_failure_records_bounded_diagnostic_evidence(self) -> None:
        fixture = ProofFixture(self.root / "fixture")
        output_root = self.root / "output"
        _claim, claim_path, claim_digest = fixture.claim_for(output_root)

        class FailingRunner:
            def run(self, command, **kwargs):
                del command, kwargs
                return CommandResult(
                    stdout="sensitive stdout",
                    stderr="sensitive stderr",
                    returncode=17,
                )

        control = LocalK3sRuntimeControl(
            authorization=fixture.authorization,
            baseline=fixture.baseline,
            contexts=fixture.contexts,
            artifacts=RuntimeArtifactBindings(
                authorization_path=fixture.authorization_path,
                authorization_digest=fixture.authorization_digest,
                operator_approval_path=fixture.operator_approval,
                security_approval_path=fixture.security_approval,
                baseline_path=fixture.baseline_path,
                baseline_evidence_root=fixture.evidence_root,
                consumption_receipt_path=fixture.consumption_path,
                consumption_receipt_digest=fixture.consumption_digest,
                execution_claim_path=claim_path,
                execution_claim_digest=claim_digest,
            ),
            output_root=output_root,
            workspace_root=self.root / "workspace",
            runner=FailingRunner(),
        )
        with self.assertRaisesRegex(
            ControlledProofError,
            "bounded failure evidence",
        ) as raised:
            control._run(["k3s", "kubectl", "get", "namespace"])

        self.assertEqual(len(raised.exception.evidence_refs), 1)
        failure_path = next(
            (output_root / "runtime" / "command-failures").glob("*.json")
        )
        failure = read_bounded_json(failure_path)
        self.assertEqual(failure["returncode"], 17)
        self.assertEqual(failure["stderr"]["bytes"], len("sensitive stderr"))
        self.assertNotIn("sensitive stderr", failure_path.read_text(encoding="utf-8"))

    def test_runtime_waits_for_exact_admitted_temporal_pollers(self) -> None:
        fixture = ProofFixture(self.root / "fixture")
        output_root = self.root / "output"
        _claim, claim_path, claim_digest = fixture.claim_for(output_root)

        class PollerRunner:
            def __init__(self) -> None:
                self.commands: list[list[str]] = []
                self.attempts: dict[str, int] = {}

            def run(self, command, **kwargs):
                del kwargs
                self.commands.append(command)
                queue_type = command[command.index("--task-queue-type") + 1]
                self.attempts[queue_type] = self.attempts.get(queue_type, 0) + 1
                identity = (
                    "oos-workflow-worker"
                    if queue_type == "workflow"
                    else "wgcf-controlled-proof-activity-worker"
                )
                pollers = (
                    None
                    if queue_type == "workflow" and self.attempts[queue_type] == 1
                    else [{"identity": identity}]
                )
                return CommandResult(
                    stdout=json.dumps(
                        {
                            "reachability": None,
                            "pollers": pollers,
                            "stats": None,
                        }
                    ),
                    stderr="",
                    returncode=0,
                )

        runner = PollerRunner()
        control = LocalK3sRuntimeControl(
            authorization=fixture.authorization,
            baseline=fixture.baseline,
            contexts=fixture.contexts,
            artifacts=RuntimeArtifactBindings(
                authorization_path=fixture.authorization_path,
                authorization_digest=fixture.authorization_digest,
                operator_approval_path=fixture.operator_approval,
                security_approval_path=fixture.security_approval,
                baseline_path=fixture.baseline_path,
                baseline_evidence_root=fixture.evidence_root,
                consumption_receipt_path=fixture.consumption_path,
                consumption_receipt_digest=fixture.consumption_digest,
                execution_claim_path=claim_path,
                execution_claim_digest=claim_digest,
            ),
            output_root=output_root,
            workspace_root=self.root / "workspace",
            runner=runner,
        )

        control._wait_for_temporal_pollers(
            timeout_seconds=1,
            poll_interval_seconds=0,
        )

        readiness = read_bounded_json(
            output_root / "runtime" / "temporal-poller-readiness.json"
        )
        self.assertEqual(readiness["status"], "ready")
        self.assertEqual(len(readiness["pollers"]), 2)
        self.assertEqual(len(runner.commands), 4)

    def test_runtime_rejects_an_unadmitted_temporal_poller(self) -> None:
        fixture = ProofFixture(self.root / "fixture")
        output_root = self.root / "output"
        _claim, claim_path, claim_digest = fixture.claim_for(output_root)

        class UnexpectedPollerRunner:
            def run(self, command, **kwargs):
                del command, kwargs
                return CommandResult(
                    stdout=json.dumps(
                        {
                            "reachability": None,
                            "pollers": [{"identity": "unadmitted-worker"}],
                            "stats": None,
                        }
                    ),
                    stderr="",
                    returncode=0,
                )

        control = LocalK3sRuntimeControl(
            authorization=fixture.authorization,
            baseline=fixture.baseline,
            contexts=fixture.contexts,
            artifacts=RuntimeArtifactBindings(
                authorization_path=fixture.authorization_path,
                authorization_digest=fixture.authorization_digest,
                operator_approval_path=fixture.operator_approval,
                security_approval_path=fixture.security_approval,
                baseline_path=fixture.baseline_path,
                baseline_evidence_root=fixture.evidence_root,
                consumption_receipt_path=fixture.consumption_path,
                consumption_receipt_digest=fixture.consumption_digest,
                execution_claim_path=claim_path,
                execution_claim_digest=claim_digest,
            ),
            output_root=output_root,
            workspace_root=self.root / "workspace",
            runner=UnexpectedPollerRunner(),
        )

        with self.assertRaisesRegex(
            ControlledProofError,
            "unadmitted poller identity",
        ) as raised:
            control._wait_for_temporal_pollers(timeout_seconds=1)

        self.assertEqual(len(raised.exception.evidence_refs), 1)
        failure = next(
            (output_root / "runtime" / "poller-readiness-failures").glob(
                "*.json"
            )
        )
        self.assertEqual(
            read_bounded_json(failure)["failure_kind"],
            "unexpected-poller-identity",
        )

    def test_runtime_records_bounded_evidence_when_pollers_are_absent(self) -> None:
        fixture = ProofFixture(self.root / "fixture")
        output_root = self.root / "output"
        _claim, claim_path, claim_digest = fixture.claim_for(output_root)

        class MissingPollerRunner:
            def run(self, command, **kwargs):
                del command, kwargs
                return CommandResult(
                    stdout=json.dumps(
                        {
                            "reachability": None,
                            "pollers": None,
                            "stats": None,
                        }
                    ),
                    stderr="",
                    returncode=0,
                )

        control = LocalK3sRuntimeControl(
            authorization=fixture.authorization,
            baseline=fixture.baseline,
            contexts=fixture.contexts,
            artifacts=RuntimeArtifactBindings(
                authorization_path=fixture.authorization_path,
                authorization_digest=fixture.authorization_digest,
                operator_approval_path=fixture.operator_approval,
                security_approval_path=fixture.security_approval,
                baseline_path=fixture.baseline_path,
                baseline_evidence_root=fixture.evidence_root,
                consumption_receipt_path=fixture.consumption_path,
                consumption_receipt_digest=fixture.consumption_digest,
                execution_claim_path=claim_path,
                execution_claim_digest=claim_digest,
            ),
            output_root=output_root,
            workspace_root=self.root / "workspace",
            runner=MissingPollerRunner(),
        )

        with self.assertRaisesRegex(
            ControlledProofError,
            "pollers did not become ready",
        ) as raised:
            control._wait_for_temporal_pollers(timeout_seconds=0)

        self.assertEqual(len(raised.exception.evidence_refs), 1)
        failure = next(
            (output_root / "runtime" / "poller-readiness-failures").glob(
                "*.json"
            )
        )
        payload = read_bounded_json(failure)
        self.assertEqual(payload["failure_kind"], "poller-readiness-timeout")
        self.assertEqual(
            [
                requirement["observed_identities"]
                for requirement in payload["requirements"]
            ],
            [[], []],
        )

    def test_runtime_http_failure_records_bounded_request_evidence(self) -> None:
        fixture = ProofFixture(self.root / "fixture")
        output_root = self.root / "output"
        _claim, claim_path, claim_digest = fixture.claim_for(output_root)
        control = LocalK3sRuntimeControl(
            authorization=fixture.authorization,
            baseline=fixture.baseline,
            contexts=fixture.contexts,
            artifacts=RuntimeArtifactBindings(
                authorization_path=fixture.authorization_path,
                authorization_digest=fixture.authorization_digest,
                operator_approval_path=fixture.operator_approval,
                security_approval_path=fixture.security_approval,
                baseline_path=fixture.baseline_path,
                baseline_evidence_root=fixture.evidence_root,
                consumption_receipt_path=fixture.consumption_path,
                consumption_receipt_digest=fixture.consumption_digest,
                execution_claim_path=claim_path,
                execution_claim_digest=claim_digest,
            ),
            output_root=output_root,
            workspace_root=self.root / "workspace",
        )
        control.api_url = "http://127.0.0.1:18080"
        response_body = (
            b'{"error":"controlled_proof_not_admitted",'
            b'"message":"sensitive runtime detail"}'
        )
        error = urlerror.HTTPError(
            "http://127.0.0.1:18080/v1/orchestration/controlled-proof/executions",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(response_body),
        )

        with mock.patch.object(
            runtime_module.LOCAL_HTTP_OPENER,
            "open",
            side_effect=error,
        ):
            with self.assertRaisesRegex(
                ControlledProofError,
                "bounded failure evidence",
            ) as raised:
                control._request(
                    "POST",
                    "/v1/orchestration/controlled-proof/executions",
                    {"schema_version": 1},
                )

        self.assertEqual(len(raised.exception.evidence_refs), 1)
        failure_path = next(
            (output_root / "runtime" / "request-failures").glob("*.json")
        )
        failure = read_bounded_json(failure_path)
        self.assertEqual(failure["http_status"], 503)
        self.assertEqual(failure["response_error"], "controlled_proof_not_admitted")
        self.assertNotIn(
            "sensitive runtime detail",
            failure_path.read_text(encoding="utf-8"),
        )

    def test_executor_snapshot_rejects_index_hidden_and_ignored_changes(self) -> None:
        fixture = ProofFixture(self.root / "fixture")
        output_root = self.root / "output"
        _claim, claim_path, claim_digest = fixture.claim_for(output_root)
        control = LocalK3sRuntimeControl(
            authorization=fixture.authorization,
            baseline=fixture.baseline,
            contexts=fixture.contexts,
            artifacts=RuntimeArtifactBindings(
                authorization_path=fixture.authorization_path,
                authorization_digest=fixture.authorization_digest,
                operator_approval_path=fixture.operator_approval,
                security_approval_path=fixture.security_approval,
                baseline_path=fixture.baseline_path,
                baseline_evidence_root=fixture.evidence_root,
                consumption_receipt_path=fixture.consumption_path,
                consumption_receipt_digest=fixture.consumption_digest,
                execution_claim_path=claim_path,
                execution_claim_digest=claim_digest,
            ),
            output_root=output_root,
            workspace_root=self.root / "workspace",
        )
        snapshot = control.platform_executor_snapshot
        script_path = (
            snapshot
            / "dev-integration"
            / "profiles"
            / "temporal"
            / "scripts"
            / "controlled-proof-runtime.sh"
        )
        ignore_path = (
            snapshot
            / "dev-integration"
            / "profiles"
            / "temporal"
            / ".gitignore"
        )
        script_path.parent.mkdir(parents=True)
        script_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        script_path.chmod(0o755)
        ignore_path.write_text("scripts/sitecustomize.py\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=snapshot, check=True)
        subprocess.run(["git", "add", "."], cwd=snapshot, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Controlled Proof Test",
                "-c",
                "user.email=controlled-proof@example.invalid",
                "commit",
                "-qm",
                "executor snapshot",
            ],
            cwd=snapshot,
            check=True,
        )
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=snapshot,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        control.authorization["executor"]["source_revision"] = revision
        control._assert_platform_executor_snapshot()

        relative_script = script_path.relative_to(snapshot)
        subprocess.run(
            ["git", "update-index", "--assume-unchanged", str(relative_script)],
            cwd=snapshot,
            check=True,
        )
        script_path.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
        with self.assertRaisesRegex(ControlledProofError, "executor bytes changed"):
            control._assert_platform_executor_snapshot()

        subprocess.run(
            ["git", "update-index", "--no-assume-unchanged", str(relative_script)],
            cwd=snapshot,
            check=True,
        )
        subprocess.run(
            ["git", "checkout", "--", str(relative_script)],
            cwd=snapshot,
            check=True,
        )
        ignored_injection = script_path.parent / "sitecustomize.py"
        ignored_injection.write_text("raise RuntimeError('injected')\n", encoding="utf-8")
        with self.assertRaisesRegex(ControlledProofError, "untracked file"):
            control._assert_platform_executor_snapshot()

    def test_runtime_renderer_preserves_exact_collision_resistant_scope(self) -> None:
        operator_id = "alice.example"
        kubernetes_namespace = operator_scoped_dns_label(
            "devint-temporal", operator_id
        )
        temporal_namespace = operator_scoped_dns_label("governance", operator_id)
        operator_scope = operator_scope_id(operator_id)
        output_root = self.root / "rendered"

        subprocess.run(
            [
                sys.executable,
                str(PROFILE_ROOT / "scripts" / "render_runtime.py"),
                "--profile-root",
                str(PROFILE_ROOT),
                "--output-dir",
                str(output_root),
                "--namespace",
                kubernetes_namespace,
                "--operator-scope",
                operator_scope,
                "--temporal-namespace",
                temporal_namespace,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        temporal_values = yaml.safe_load(
            (output_root / "temporal-values.yaml").read_text(encoding="utf-8")
        )
        postgresql_documents = list(
            yaml.safe_load_all(
                (output_root / "postgresql.yaml").read_text(encoding="utf-8")
            )
        )
        self.assertEqual(
            temporal_values["additionalLabels"]["dev-integration-operator"],
            operator_scope,
        )
        self.assertEqual(
            temporal_values["server"]["config"]["namespaces"]["namespace"][0][
                "name"
            ],
            temporal_namespace,
        )
        namespace_document = next(
            document
            for document in postgresql_documents
            if document["kind"] == "Namespace"
        )
        self.assertEqual(
            namespace_document["metadata"]["name"], kubernetes_namespace
        )
        self.assertTrue(postgresql_documents)
        postgresql_statefulset = next(
            document
            for document in postgresql_documents
            if document.get("kind") == "StatefulSet"
            and document.get("metadata", {}).get("name")
            == "temporal-postgresql"
        )
        self.assertEqual(
            validate_source_module.postgresql_init_script_mode(
                postgresql_statefulset
            ),
            0o555,
        )
        self.assertTrue(
            all(
                document["metadata"]["namespace"] == kubernetes_namespace
                for document in postgresql_documents
                if document["kind"] != "Namespace"
            )
        )
        self.assertNotEqual(temporal_namespace, "governance-alice-example")

    def test_postgresql_init_mode_rejects_non_world_executable_mount(self) -> None:
        statefulset = {
            "spec": {
                "template": {
                    "spec": {
                        "volumes": [
                            {
                                "name": "init",
                                "configMap": {"defaultMode": 0o550},
                            }
                        ]
                    }
                }
            }
        }
        self.assertNotEqual(
            validate_source_module.postgresql_init_script_mode(statefulset),
            0o555,
        )

    def test_state_root_guard_accepts_exact_collision_resistant_scope(self) -> None:
        operator_id = "Alice"
        operator_scope = operator_scope_id(operator_id)
        workspace_root = self.root / "workspace"
        owner_root = workspace_root / "platform-engineering"
        state_root = owner_root / ".dev-integration" / "temporal" / operator_scope
        environment = controlled_subprocess_environment(
            {
                "CONTROLLED_PROOF_OPERATOR_SCOPE": operator_scope,
                "DEVINT_OPERATOR": operator_id,
                "DEVINT_PROFILE_ID": "temporal",
                "DEVINT_STATE_ROOT": str(state_root),
                "DEVINT_WORKSPACE_ROOT": str(owner_root),
                "DEVINT_TEMPORAL_WORKFLOW_NAMESPACE": operator_scoped_dns_label(
                    "governance", operator_id
                ),
            }
        )
        completed = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; assert_state_root_boundary',
                "state-root-boundary-test",
                str(PROFILE_ROOT / "scripts" / "common.sh"),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_state_root_guard_rejects_scope_outside_platform_profile_root(self) -> None:
        operator_id = "Alice"
        operator_scope = operator_scope_id(operator_id)
        workspace_root = self.root / "workspace"
        owner_root = workspace_root / "platform-engineering"
        state_root = workspace_root / "outside" / "temporal" / operator_scope
        environment = controlled_subprocess_environment(
            {
                "CONTROLLED_PROOF_OPERATOR_SCOPE": operator_scope,
                "DEVINT_OPERATOR": operator_id,
                "DEVINT_PROFILE_ID": "temporal",
                "DEVINT_STATE_ROOT": str(state_root),
                "DEVINT_WORKSPACE_ROOT": str(owner_root),
                "DEVINT_TEMPORAL_WORKFLOW_NAMESPACE": operator_scoped_dns_label(
                    "governance", operator_id
                ),
            }
        )
        completed = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; assert_state_root_boundary',
                "state-root-boundary-test",
                str(PROFILE_ROOT / "scripts" / "common.sh"),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(
            "Temporal state root is outside an approved profile root",
            completed.stderr,
        )

    def test_owner_contexts_bind_the_pinned_wgcf_source_revision(self) -> None:
        fixture = ProofFixture(self.root / "fixture")
        expected_source_ref = (
            "git:workspace-governance-control-fabric:"
            f"{SOURCE_REVISIONS['workspace-governance-control-fabric']}"
        )

        self.assertEqual(
            fixture.contexts.oos["request_binding"]["source_version_ref"],
            expected_source_ref,
        )
        self.assertEqual(
            fixture.contexts.wgcf["request_binding"]["source_version_ref"],
            expected_source_ref,
        )
        self.assertNotEqual(expected_source_ref, fixture.authorization_digest)

    def test_temporal_restart_scenario_restarts_runtime_once(self) -> None:
        fixture = ProofFixture(self.root)
        scenario = next(
            item
            for item in fixture.authorization["commissioning_session"][
                "scenario_executions"
            ]
            if item["scenario_id"] == "temporal-runtime-restart"
        )
        completed_at = now_utc()

        class RecordingControl:
            restart_count = 0

            def assert_current(self) -> None:
                return None

            def prepare(self, contexts: ProjectedContexts) -> None:
                del contexts
                raise AssertionError("prepare is not used by one scenario execution")

            def start(self, scenario_execution_id: str) -> dict[str, Any]:
                self.scenario_execution_id = scenario_execution_id
                return {"run_id": "runtime-restart-run"}

            def get(self, run_id: str) -> dict[str, Any]:
                self.run_id = run_id
                return {"projection": {"state": "waiting"}}

            def signal(
                self,
                *,
                run_id: str,
                scenario: dict[str, Any],
                evidence_kind: str,
                evidence_ref: dict[str, str],
                observed_at: str,
            ) -> dict[str, Any]:
                del run_id, evidence_kind, evidence_ref, observed_at
                return {
                    "projection": {
                        "state": "completed",
                        "scenario_assertion": {"status": "passed"},
                        "completed_at": completed_at,
                    },
                    "owner_receipt": owner_receipt(
                        fixture,
                        scenario,
                        "operator-orchestration-service",
                        completed_at,
                    ),
                }

            def cancel(
                self, *, run_id: str, scenario: dict[str, Any]
            ) -> dict[str, Any]:
                del run_id, scenario
                raise AssertionError("cancel is not used by restart execution")

            def restart_oos_worker(self) -> None:
                raise AssertionError("OOS restart is not used by Temporal restart")

            def restart_temporal(self) -> None:
                self.restart_count += 1

            def backup_restore(self) -> None:
                raise AssertionError("backup is not used by restart execution")

            def load_wgcf_receipt(
                self, oos_receipt: dict[str, Any]
            ) -> dict[str, Any]:
                del oos_receipt
                return owner_receipt(
                    fixture,
                    scenario,
                    "workspace-governance-control-fabric",
                    completed_at,
                )

            def restore_baseline(
                self, baseline: dict[str, Any]
            ) -> dict[str, str]:
                del baseline
                raise AssertionError("restore is not used by restart execution")

            def cleanup(self) -> None:
                raise AssertionError("cleanup is not used by one scenario execution")

        control = RecordingControl()
        driver = ControlledRuntimeDriver(
            authorization=fixture.authorization,
            authorization_digest=fixture.authorization_digest,
            contracts=fixture.contracts,
            control=control,
            output_root=self.root / "scenario",
        )
        result = driver.execute_scenario(scenario, fixture.contexts)
        self.assertEqual(result.status, "passed")
        self.assertEqual(control.restart_count, 1)

    def test_valid_permit_binds_approvals_baseline_and_current_source(self) -> None:
        fixture = ProofFixture(self.root)
        validate_authorization(
            fixture.authorization,
            contracts=fixture.contracts,
            baseline_path=fixture.baseline_path,
            baseline_evidence_root=fixture.evidence_root,
            source_resolver=fixture.source,
            operator_approval_path=fixture.operator_approval,
            security_approval_path=fixture.security_approval,
        )

    def test_security_authorization_must_match_its_source_controlled_artifact(
        self,
    ) -> None:
        fixture = ProofFixture(self.root / "valid")
        forged = read_bounded_json(fixture.security_approval)
        forged["approved_by"] = "self-declared-security-reviewer"
        forged_path = self.root / "forged-security-authorization.json"
        write_json_atomic(forged_path, forged)
        with self.assertRaisesRegex(
            ControlledProofError,
            "does not match its source-controlled artifact",
        ):
            issue_permit(
                claims=fixture.claims,
                operator_approval_path=fixture.operator_approval,
                security_approval_path=forged_path,
                baseline_path=fixture.baseline_path,
                baseline_evidence_root=fixture.evidence_root,
                source_resolver=fixture.source,
                contracts=fixture.contracts,
            )

    def test_security_authorization_is_loaded_from_permit_bound_source_revision(
        self,
    ) -> None:
        fixture = ProofFixture(self.root / "valid")
        source_key = (
            "security-architecture",
            SOURCE_REVISIONS["security-architecture"],
            fixture.security_source_path,
        )
        source_content = fixture.source.source_files.pop(source_key)
        fixture.source.source_files[
            (
                "security-architecture",
                "f" * 40,
                fixture.security_source_path,
            )
        ] = source_content
        with self.assertRaisesRegex(
            ControlledProofError,
            "source artifact is unavailable",
        ):
            issue_permit(
                claims=fixture.claims,
                operator_approval_path=fixture.operator_approval,
                security_approval_path=fixture.security_approval,
                baseline_path=fixture.baseline_path,
                baseline_evidence_root=fixture.evidence_root,
                source_resolver=fixture.source,
                contracts=fixture.contracts,
            )

    def test_real_git_security_approval_is_bound_after_claims_without_digest_cycle(
        self,
    ) -> None:
        root = self.root / "real-git-provenance"
        workspace_root = root / "workspace"
        platform_root = workspace_root / "platform-engineering"
        security_root = workspace_root / SECURITY_AUTHORIZATION_SOURCE_REPO
        platform_revision = initialize_git_repo(platform_root, "permit-issuer.txt")
        security_preapproval_revision = initialize_git_repo(
            security_root, "review-boundary.txt"
        )
        source = RealApprovalSourceResolver(workspace_root)
        contracts = load_contracts()
        baseline_path = root / "baseline.json"
        baseline_evidence_root = root / "baseline-evidence"
        baseline, baseline_digest = capture_baseline(
            baseline_id="artifact://controlled-proof/baselines/real-git-session",
            operator_id="alice",
            output_path=baseline_path,
            evidence_root=baseline_evidence_root,
            source_resolver=source,
            probe=FakeProbe(),
            contracts=contracts,
            captured_at=timestamp(timedelta(minutes=-10)),
        )
        claims, claims_digest = assemble_claims(
            authorization_id=(
                "platform-controlled-proof://authorizations/real-git-session"
            ),
            commissioning_session_id="real-git-session",
            review_packet_ref="artifact://review-packets/platform-825",
            issued_at=timestamp(timedelta(seconds=-30)),
            expires_at=timestamp(timedelta(hours=1)),
            baseline=baseline,
            baseline_digest=baseline_digest,
            baseline_evidence_root=baseline_evidence_root,
            owner_image_digests={
                image_ref: DIGEST for image_ref in OWNER_RUNTIME_IMAGES
            },
            source_resolver=source,
            contracts=contracts,
        )
        self.assertEqual(
            [
                item["repo"]
                for item in claims["scope"]["execution_source_revisions"]
            ],
            list(EXECUTION_SOURCE_REPOS),
        )
        self.assertNotIn(
            SECURITY_AUTHORIZATION_SOURCE_REPO,
            {
                item["repo"]
                for item in claims["scope"]["execution_source_revisions"]
            },
        )
        self.assertEqual(
            next(
                item["commit"]
                for item in claims["scope"]["execution_source_revisions"]
                if item["repo"] == "platform-engineering"
            ),
            platform_revision,
        )

        operator_approval = root / "operator-approval.json"
        security_source_path = (
            "records/controlled-proof-authorizations/real-git-session.json"
        )
        security_approval = security_root / security_source_path
        security_approval.parent.mkdir(parents=True)
        write_approval(
            operator_approval,
            role="operator-approval",
            claims=claims,
            claims_digest=claims_digest,
        )
        write_approval(
            security_approval,
            role="security-authorization",
            claims=claims,
            claims_digest=claims_digest,
            source_path=security_source_path,
        )

        with self.assertRaisesRegex(
            ControlledProofError,
            "source repo is dirty at permit issuance",
        ):
            issue_permit(
                claims=claims,
                operator_approval_path=operator_approval,
                security_approval_path=security_approval,
                baseline_path=baseline_path,
                baseline_evidence_root=baseline_evidence_root,
                source_resolver=source,
                contracts=contracts,
            )

        subprocess.run(
            [
                "git",
                "-C",
                str(security_root),
                "checkout",
                "--quiet",
                "-b",
                "security-approval-review",
            ],
            check=True,
        )
        commit_git_path(
            security_root,
            security_source_path,
            "approve exact controlled proof claims",
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(security_root),
                "push",
                "--quiet",
                "-u",
                "origin",
                "security-approval-review",
            ],
            check=True,
        )
        with self.assertRaisesRegex(
            ControlledProofError,
            "not contained in merged refs/remotes/origin/main",
        ):
            issue_permit(
                claims=claims,
                operator_approval_path=operator_approval,
                security_approval_path=security_approval,
                baseline_path=baseline_path,
                baseline_evidence_root=baseline_evidence_root,
                source_resolver=source,
                contracts=contracts,
            )

        security_revision = merge_git_branch_to_main(
            security_root,
            "security-approval-review",
        )
        authorization = issue_permit(
            claims=claims,
            operator_approval_path=operator_approval,
            security_approval_path=security_approval,
            baseline_path=baseline_path,
            baseline_evidence_root=baseline_evidence_root,
            source_resolver=source,
            contracts=contracts,
        )
        self.assertEqual(canonical_digest(claims), claims_digest)
        self.assertEqual(
            canonical_digest(authority_module.claims_projection(authorization)),
            claims_digest,
        )
        self.assertEqual(
            authorization["approvals"]["security_authorization_source_revision"],
            security_revision,
        )
        self.assertEqual(
            authorization["approvals"]["security_authorization_source_path"],
            security_source_path,
        )
        validate_authorization(
            authorization,
            contracts=contracts,
            baseline_path=baseline_path,
            baseline_evidence_root=baseline_evidence_root,
            source_resolver=source,
            operator_approval_path=operator_approval,
            security_approval_path=security_approval,
        )

        wrong_revision = copy.deepcopy(authorization)
        wrong_revision["approvals"][
            "security_authorization_source_revision"
        ] = security_preapproval_revision
        with self.assertRaisesRegex(ControlledProofError, "source artifact"):
            validate_authorization(
                wrong_revision,
                contracts=contracts,
                baseline_path=baseline_path,
                baseline_evidence_root=baseline_evidence_root,
                source_resolver=source,
                operator_approval_path=operator_approval,
                security_approval_path=security_approval,
            )

        wrong_path = copy.deepcopy(authorization)
        wrong_path["approvals"]["security_authorization_source_path"] = (
            "records/controlled-proof-authorizations/wrong.json"
        )
        with self.assertRaisesRegex(ControlledProofError, "source path"):
            validate_authorization(
                wrong_path,
                contracts=contracts,
                baseline_path=baseline_path,
                baseline_evidence_root=baseline_evidence_root,
                source_resolver=source,
                operator_approval_path=operator_approval,
                security_approval_path=security_approval,
            )

        (platform_root / "post-review-change.txt").write_text(
            "unreviewed change\n", encoding="utf-8"
        )
        commit_git_path(
            platform_root,
            "post-review-change.txt",
            "change permit issuer after review",
        )
        with self.assertRaisesRegex(
            ControlledProofError,
            "authorization source revision drifted: platform-engineering",
        ):
            validate_authorization(
                authorization,
                contracts=contracts,
                baseline_path=baseline_path,
                baseline_evidence_root=baseline_evidence_root,
                source_resolver=source,
                operator_approval_path=operator_approval,
                security_approval_path=security_approval,
            )

    def test_legacy_self_referential_source_shape_is_rejected(self) -> None:
        fixture = ProofFixture(self.root / "valid")
        legacy = copy.deepcopy(fixture.claims)
        legacy["scope"]["source_revisions"] = legacy["scope"].pop(
            "execution_source_revisions"
        )
        legacy["scope"]["source_revisions"].append(
            {
                "repo": SECURITY_AUTHORIZATION_SOURCE_REPO,
                "commit": SOURCE_REVISIONS[SECURITY_AUTHORIZATION_SOURCE_REPO],
            }
        )
        legacy["schema_version"] = 3
        with self.assertRaises(ControlledProofError):
            prepare_claims(legacy, contracts=fixture.contracts)

    def test_runtime_action_revalidates_consumed_authority_and_exact_scope(self) -> None:
        fixture = ProofFixture(self.root / "fixture", operator_id="alice.example")
        workspace_root = self.root / "workspace"
        platform_root = workspace_root / "platform-engineering"
        consumption, consumption_path, consumption_digest = consume_authorization(
            authorization=fixture.authorization,
            authorization_digest=fixture.authorization_digest,
            executor_source_revision=REVISION,
            consumption_root=(
                platform_root
                / ".platform-drills"
                / "_controlled-proof-consumptions"
            ),
            contracts=fixture.contracts,
        )
        output_root = (
            platform_root
            / ".platform-drills"
            / "temporal-component-commissioning-proof"
            / "session-001"
            / "controlled-proof-output"
        )
        _, execution_claim_path, execution_claim_digest = claim_execution(
            authorization=fixture.authorization,
            authorization_digest=fixture.authorization_digest,
            consumption_receipt=consumption,
            consumption_receipt_digest=consumption_digest,
            output_root=output_root,
            operator_id=fixture.baseline["operator_id"],
            execution_root=(
                platform_root / ".platform-drills" / "_controlled-proof-executions"
            ),
            contracts=fixture.contracts,
        )
        bindings = RuntimeArtifactBindings(
            authorization_path=fixture.authorization_path,
            authorization_digest=fixture.authorization_digest,
            operator_approval_path=fixture.operator_approval,
            security_approval_path=fixture.security_approval,
            baseline_path=fixture.baseline_path,
            baseline_evidence_root=fixture.evidence_root,
            consumption_receipt_path=consumption_path,
            consumption_receipt_digest=consumption_digest,
            execution_claim_path=execution_claim_path,
            execution_claim_digest=execution_claim_digest,
        )
        expected_temporal_namespace = fixture.authorization["scope"][
            "target_namespaces"
        ][0]
        validate_runtime_action_binding(
            action="prepare",
            workspace_root=workspace_root,
            bindings=bindings,
            output_root=output_root,
            kubernetes_namespace=operator_scoped_dns_label(
                "devint-temporal", "alice.example"
            ),
            temporal_namespace=expected_temporal_namespace,
            state_root=controlled_runtime_state_root(
                workspace_root, "alice.example"
            ),
            operator_scope=operator_scope_id("alice.example"),
            source_resolver=fixture.source,
        )
        with self.assertRaisesRegex(
            ControlledProofError,
            "runtime action scope does not match its authorization",
        ):
            validate_runtime_action_binding(
                action="prepare",
                workspace_root=workspace_root,
                bindings=bindings,
                output_root=output_root,
                kubernetes_namespace=operator_scoped_dns_label(
                    "devint-temporal", "alice.example"
                ),
                temporal_namespace="governance-alice-example",
                state_root=controlled_runtime_state_root(
                    workspace_root, "alice.example"
                ),
                operator_scope=operator_scope_id("alice.example"),
                source_resolver=fixture.source,
            )

        fixture.source.revisions["security-architecture"] = "f" * 40
        with self.assertRaisesRegex(
            ControlledProofError,
            "source artifact repo is not clean at its bound revision",
        ):
            validate_runtime_action_binding(
                action="prepare",
                workspace_root=workspace_root,
                bindings=bindings,
                output_root=output_root,
                kubernetes_namespace=operator_scoped_dns_label(
                    "devint-temporal", "alice.example"
                ),
                temporal_namespace=expected_temporal_namespace,
                state_root=controlled_runtime_state_root(
                    workspace_root, "alice.example"
                ),
                operator_scope=operator_scope_id("alice.example"),
                source_resolver=fixture.source,
            )
        validate_runtime_action_binding(
            action="cleanup",
            workspace_root=workspace_root,
            bindings=bindings,
            output_root=output_root,
            kubernetes_namespace=operator_scoped_dns_label(
                "devint-temporal", "alice.example"
            ),
            temporal_namespace=expected_temporal_namespace,
            state_root=controlled_runtime_state_root(
                workspace_root, "alice.example"
            ),
            operator_scope=operator_scope_id("alice.example"),
            source_resolver=fixture.source,
        )

    def test_terminal_baseline_verification_is_independent_of_checkout_state(
        self,
    ) -> None:
        fixture = ProofFixture(self.root / "fixture")
        output_root = self.root / "output"
        _claim, claim_path, claim_digest = fixture.claim_for(output_root)
        control = LocalK3sRuntimeControl(
            authorization=fixture.authorization,
            baseline=fixture.baseline,
            contexts=fixture.contexts,
            artifacts=RuntimeArtifactBindings(
                authorization_path=fixture.authorization_path,
                authorization_digest=fixture.authorization_digest,
                operator_approval_path=fixture.operator_approval,
                security_approval_path=fixture.security_approval,
                baseline_path=fixture.baseline_path,
                baseline_evidence_root=fixture.evidence_root,
                consumption_receipt_path=fixture.consumption_path,
                consumption_receipt_digest=fixture.consumption_digest,
                execution_claim_path=claim_path,
                execution_claim_digest=claim_digest,
            ),
            output_root=output_root,
            workspace_root=self.root / "workspace-without-source-checkouts",
        )
        with mock.patch(
            "controlled_proof.runtime.LocalBaselineProbe",
            return_value=FakeProbe(),
        ):
            restored = control._verify_baseline(fixture.baseline)
        self.assertEqual(
            [item["surface_id"] for item in restored], list(SURFACE_ORDER)
        )

    def test_claims_builder_derives_the_complete_reviewed_scope(self) -> None:
        fixture = ProofFixture(self.root)
        claims, digest = assemble_claims(
            authorization_id=fixture.claims["authorization_id"],
            commissioning_session_id=fixture.claims["commissioning_session"][
                "commissioning_session_id"
            ],
            review_packet_ref=fixture.claims["permit_issuer"][
                "review_packet_ref"
            ],
            issued_at=fixture.claims["window"]["issued_at"],
            expires_at=fixture.claims["window"]["expires_at"],
            baseline=fixture.baseline,
            baseline_digest=fixture.baseline_digest,
            baseline_evidence_root=fixture.evidence_root,
            owner_image_digests={
                image_ref: DIGEST for image_ref in OWNER_RUNTIME_IMAGES
            },
            source_resolver=fixture.source,
            contracts=fixture.contracts,
        )
        self.assertEqual(claims, fixture.claims)
        self.assertEqual(digest, fixture.claims_digest)

    def test_capture_rejects_dirty_source_before_writing_baseline(self) -> None:
        with self.assertRaisesRegex(ControlledProofError, "source repo is dirty"):
            capture_baseline(
                baseline_id="artifact://controlled-proof/baselines/dirty",
                operator_id="alice",
                output_path=self.root / "baseline.json",
                evidence_root=self.root / "evidence",
                source_resolver=FakeSourceResolver(dirty_repo="platform-engineering"),
                probe=FakeProbe(),
                contracts=load_contracts(),
            )
        self.assertFalse((self.root / "baseline.json").exists())

    def test_capture_writes_no_evidence_when_a_probe_fails(self) -> None:
        with self.assertRaisesRegex(ControlledProofError, "probe failed"):
            capture_baseline(
                baseline_id="artifact://controlled-proof/baselines/probe-failed",
                operator_id="alice",
                output_path=self.root / "baseline.json",
                evidence_root=self.root / "evidence",
                source_resolver=FakeSourceResolver(),
                probe=FailingProbe(),
                contracts=load_contracts(),
            )
        self.assertFalse((self.root / "baseline.json").exists())
        self.assertFalse((self.root / "evidence").exists())

    def test_local_baseline_probe_writes_canonical_safe_evidence(self) -> None:
        workspace_root = self.root / "workspace"
        (workspace_root / "platform-engineering").mkdir(parents=True)
        completed = subprocess.CompletedProcess(
            args=["k3s", "kubectl"],
            returncode=0,
            stdout="",
            stderr="warning one\nwarning two",
        )
        baseline_path = self.root / "baseline.json"
        evidence_root = self.root / "evidence"
        with (
            mock.patch.object(
                authority_module,
                "resolve_controlled_command",
                side_effect=lambda command, environment: command,
            ),
            mock.patch.object(
                authority_module.subprocess,
                "run",
                return_value=completed,
            ),
        ):
            baseline, _digest = capture_baseline(
                baseline_id="artifact://controlled-proof/baselines/local-probe",
                operator_id="alice",
                output_path=baseline_path,
                evidence_root=evidence_root,
                source_resolver=FakeSourceResolver(),
                probe=authority_module.LocalBaselineProbe(workspace_root, "alice"),
                contracts=load_contracts(),
            )

        temporal = read_bounded_json(evidence_root / "temporal-runtime.json")
        self.assertEqual(
            temporal["stdout"],
            "scoped runtime resource: absent; operator state: absent",
        )
        self.assertEqual(temporal["stderr"], "warning one warning two")
        self.assertEqual(
            [item["state"] for item in baseline["surface_observations"]],
            ["not-installed", "not-installed", "not-installed"],
        )

    def test_permit_rejects_approval_for_another_claims_digest(self) -> None:
        fixture = ProofFixture(self.root / "valid")
        wrong = read_bounded_json(fixture.operator_approval)
        wrong["canonical_claims_digest"] = "sha256:" + "d" * 64
        wrong_path = self.root / "wrong-approval.json"
        write_json_atomic(wrong_path, wrong)
        with self.assertRaisesRegex(ControlledProofError, "another claims digest"):
            issue_permit(
                claims=fixture.claims,
                operator_approval_path=wrong_path,
                security_approval_path=fixture.security_approval,
                baseline_path=fixture.baseline_path,
                baseline_evidence_root=fixture.evidence_root,
                source_resolver=fixture.source,
                contracts=fixture.contracts,
            )

    def test_permit_rejects_duplicate_runtime_binding(self) -> None:
        fixture = ProofFixture(self.root / "valid")
        duplicate = copy.deepcopy(fixture.claims)
        duplicate["scope"]["runtime_images"].append(
            {
                "image_ref": duplicate["scope"]["runtime_images"][0]["image_ref"],
                "digest": "sha256:" + "e" * 64,
            }
        )
        with self.assertRaisesRegex(ControlledProofError, "duplicate runtime image"):
            prepare_claims(duplicate, contracts=fixture.contracts)

    def test_claims_reject_duplicate_identity_role_and_queue_owner(self) -> None:
        fixture = ProofFixture(self.root / "valid")
        for collection, duplicate in (
            (
                "runtime_identities",
                {"role": "oos-api", "identity": "unexpected-second-identity"},
            ),
            (
                "task_queues",
                {
                    "owner_repo": "operator-orchestration-service",
                    "queue_name": "unexpected-second-queue",
                },
            ),
        ):
            claims = copy.deepcopy(fixture.claims)
            claims["scope"][collection].append(duplicate)
            with self.subTest(collection=collection):
                with self.assertRaisesRegex(ControlledProofError, "duplicate"):
                    prepare_claims(claims, contracts=fixture.contracts)

    def test_claims_reject_execution_id_outside_its_session(self) -> None:
        fixture = ProofFixture(self.root / "valid")
        claims = copy.deepcopy(fixture.claims)
        claims["commissioning_session"]["scenario_executions"][0][
            "scenario_execution_id"
        ] = "another-session:01:nominal-completion"
        with self.assertRaisesRegex(ControlledProofError, "does not match its session"):
            prepare_claims(claims, contracts=fixture.contracts)

    def test_claims_reject_source_outside_reviewed_contract_revision(self) -> None:
        fixture = ProofFixture(self.root / "valid")
        drifted = copy.deepcopy(fixture.claims)
        source = next(
            item
            for item in drifted["scope"]["execution_source_revisions"]
            if item["repo"] == "operator-orchestration-service"
        )
        source["commit"] = "f" * 40
        with self.assertRaisesRegex(
            ControlledProofError, "outside the reviewed contract set"
        ):
            prepare_claims(drifted, contracts=fixture.contracts)

    def test_authorization_rejects_approval_that_predates_baseline(self) -> None:
        fixture = ProofFixture(self.root / "valid")
        early_approval = read_bounded_json(fixture.operator_approval)
        early_approval["approved_at"] = timestamp(timedelta(minutes=-20))
        early_path = self.root / "early-operator-approval.json"
        early_digest = write_json_atomic(early_path, early_approval)
        authorization = copy.deepcopy(fixture.authorization)
        authorization["approvals"]["operator_approval_digest"] = early_digest
        with self.assertRaisesRegex(ControlledProofError, "predates the immutable baseline"):
            validate_authorization(
                authorization,
                contracts=fixture.contracts,
                baseline_path=fixture.baseline_path,
                baseline_evidence_root=fixture.evidence_root,
                source_resolver=fixture.source,
                operator_approval_path=early_path,
                security_approval_path=fixture.security_approval,
            )

    def test_authorization_rejects_expired_window(self) -> None:
        fixture = ProofFixture(self.root / "valid")
        with self.assertRaisesRegex(ControlledProofError, "not currently valid"):
            validate_authorization(
                fixture.authorization,
                contracts=fixture.contracts,
                baseline_path=fixture.baseline_path,
                baseline_evidence_root=fixture.evidence_root,
                source_resolver=fixture.source,
                operator_approval_path=fixture.operator_approval,
                security_approval_path=fixture.security_approval,
                at_time=datetime.now(timezone.utc) + timedelta(hours=2),
            )

    def test_artifact_loader_rejects_symbolic_links(self) -> None:
        target = self.root / "artifact.json"
        write_json_atomic(target, {"value": "stable"})
        link = self.root / "artifact-link.json"
        link.symlink_to(target)
        with self.assertRaisesRegex(ControlledProofError, "symbolic link"):
            read_bounded_json(link)

    def test_artifact_writers_reject_symbolic_link_destinations(self) -> None:
        target = self.root / "outside.json"
        link = self.root / "output-link.json"
        link.symlink_to(target)
        with self.assertRaisesRegex(ControlledProofError, "symbolic-link"):
            write_json_atomic(link, {"value": "stable"})
        with self.assertRaisesRegex(ControlledProofError, "symbolic-link"):
            create_json_exclusive(link, {"value": "stable"})
        self.assertFalse(target.exists())

    def test_artifact_writer_rejects_insecure_parent_without_changing_it(self) -> None:
        parent = self.root / "shared"
        parent.mkdir(mode=0o770)
        parent.chmod(0o770)
        with self.assertRaisesRegex(ControlledProofError, "group or world writable"):
            write_json_atomic(parent / "artifact.json", {"value": "stable"})
        self.assertEqual(parent.stat().st_mode & 0o777, 0o770)

    def test_local_api_endpoint_rejects_non_loopback_and_ambiguous_paths(self) -> None:
        self.assertEqual(
            _local_api_endpoint("http://127.0.0.1:32123", "/healthz"),
            "http://127.0.0.1:32123/healthz",
        )
        for api_url, path in (
            ("https://127.0.0.1:32123", "/healthz"),
            ("http://localhost:32123", "/healthz"),
            ("http://127.0.0.1:32123/base", "/healthz"),
            ("http://127.0.0.1:32123", "//external.example/path"),
        ):
            with self.subTest(api_url=api_url, path=path):
                with self.assertRaisesRegex(ControlledProofError, "loopback HTTP"):
                    _local_api_endpoint(api_url, path)

    def test_controlled_subprocess_environment_does_not_inherit_injection_hooks(self) -> None:
        environment = controlled_subprocess_environment(
            {"DEVINT_OPERATOR": "alice"}
        )
        self.assertEqual(environment["DEVINT_OPERATOR"], "alice")
        self.assertEqual(environment["PATH"], CONTROLLED_EXECUTABLE_PATH)
        for field in ("BASH_ENV", "ENV", "NODE_OPTIONS", "PYTHONPATH", "KUBECONFIG"):
            self.assertNotIn(field, environment)

    def test_atomic_writer_never_replaces_an_existing_artifact(self) -> None:
        target = self.root / "immutable.json"
        write_json_atomic(target, {"value": "original"})
        with self.assertRaisesRegex(ControlledProofError, "refusing to overwrite"):
            write_json_atomic(target, {"value": "replacement"})
        self.assertEqual(read_bounded_json(target), {"value": "original"})

    def test_exclusive_writer_never_exposes_a_partial_final_artifact(self) -> None:
        target = self.root / "exclusive.json"
        with mock.patch.object(
            model_module.os,
            "link",
            side_effect=OSError("injected atomic-link failure"),
        ):
            with self.assertRaisesRegex(OSError, "injected"):
                create_json_exclusive(target, {"value": "stable"})
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.glob(".exclusive.json.*")), [])

    def test_bounded_reader_returns_digest_of_the_validated_bytes(self) -> None:
        target = self.root / "bounded.json"
        write_json_atomic(target, {"value": "stable"})
        payload, digest = read_bounded_json_with_digest(target)
        self.assertEqual(payload, {"value": "stable"})
        self.assertEqual(digest, sha256_file(target))

    def test_cli_rejects_symbolic_link_claims_artifact(self) -> None:
        fixture = ProofFixture(self.root / "valid")
        claims_path = self.root / "claims.json"
        write_json_atomic(claims_path, fixture.claims)
        link = self.root / "claims-link.json"
        link.symlink_to(claims_path)
        with self.assertRaisesRegex(ControlledProofError, "symbolic link"):
            validate_claims_command(SimpleNamespace(claims=str(link)))

    def test_platform_snapshot_rejects_symbolic_link_authorization(self) -> None:
        fixture = ProofFixture(self.root / "valid")
        link = self.root / "authorization-link.json"
        link.symlink_to(fixture.authorization_path)
        args = SimpleNamespace(
            repo_root=REPO_ROOT,
            authorization_file=str(link),
            operator_approval_file=str(fixture.operator_approval),
            security_authorization_file=str(fixture.security_approval),
            baseline_file=str(fixture.baseline_path),
            baseline_evidence_root=str(fixture.evidence_root),
            authorization_digest=fixture.authorization_digest,
            authorization_ref=fixture.authorization["authorization_id"],
        )
        with self.assertRaisesRegex(ControlledProofError, "symbolic link"):
            platform_drill.prepare_controlled_proof_snapshot(args, {})

    def test_platform_snapshot_rejects_run_id_outside_authorized_session(self) -> None:
        fixture = ProofFixture(self.root / "valid")
        args = SimpleNamespace(
            repo_root=REPO_ROOT,
            authorization_file=str(fixture.authorization_path),
            operator_approval_file=str(fixture.operator_approval),
            security_authorization_file=str(fixture.security_approval),
            baseline_file=str(fixture.baseline_path),
            baseline_evidence_root=str(fixture.evidence_root),
            authorization_digest=fixture.authorization_digest,
            authorization_ref=fixture.authorization["authorization_id"],
            run_id="another-session",
            output_root="",
        )
        contract = {
            "id": "temporal-component-commissioning-proof",
            "authorization": {
                "targetProfileId": "temporal",
                "targetProfileLifecycle": "build-admitted",
            },
            "targetEnvironment": "dev-integration",
        }
        with self.assertRaisesRegex(SystemExit, "authorized commissioning session"):
            platform_drill.prepare_controlled_proof_snapshot(args, contract)

    def test_platform_snapshot_rejects_custom_controlled_ledger_root(self) -> None:
        fixture = ProofFixture(self.root / "valid")
        args = SimpleNamespace(
            repo_root=REPO_ROOT,
            authorization_file=str(fixture.authorization_path),
            operator_approval_file=str(fixture.operator_approval),
            security_authorization_file=str(fixture.security_approval),
            baseline_file=str(fixture.baseline_path),
            baseline_evidence_root=str(fixture.evidence_root),
            authorization_digest=fixture.authorization_digest,
            authorization_ref=fixture.authorization["authorization_id"],
            run_id="session-001",
            output_root=str(self.root / "elsewhere"),
        )
        contract = {
            "id": "temporal-component-commissioning-proof",
            "authorization": {
                "targetProfileId": "temporal",
                "targetProfileLifecycle": "build-admitted",
            },
            "targetEnvironment": "dev-integration",
        }
        with self.assertRaisesRegex(SystemExit, "canonical Platform drill-state root"):
            platform_drill.prepare_controlled_proof_snapshot(args, contract)

    def test_executor_cli_rejects_noncanonical_output_root(self) -> None:
        fixture = ProofFixture(self.root / "valid")
        workspace_root = self.root / "workspace"
        expected = (
            workspace_root
            / "platform-engineering"
            / ".platform-drills"
            / "temporal-component-commissioning-proof"
            / "session-001"
            / "controlled-proof-output"
        ).absolute()
        self.assertEqual(
            _canonical_execution_output_root(workspace_root, fixture.authorization),
            expected,
        )
        with self.assertRaisesRegex(ControlledProofError, "canonical Platform run"):
            _validate_execution_output_root(
                workspace_root,
                fixture.authorization,
                self.root / "unbound-output",
            )

    def test_wgcf_receipt_binding_rejects_unsafe_reference(self) -> None:
        oos_receipt = {
            "evidence_refs": [
                {
                    "artifact_ref": "wgcf-controlled-proof://receipts/../../secret",
                    "artifact_digest": DIGEST,
                }
            ]
        }
        with self.assertRaisesRegex(ControlledProofError, "fixed receipt key"):
            _wgcf_receipt_binding(oos_receipt)

    def test_loaded_wgcf_receipt_must_match_oos_digest_binding(self) -> None:
        receipt_key = "e" * 64
        receipt_ref = f"wgcf-controlled-proof://receipts/{receipt_key}"
        receipt = {"receipt_ref": receipt_ref, "receipt_digest": DIGEST}
        with self.assertRaisesRegex(ControlledProofError, "digest does not match"):
            _validate_loaded_wgcf_receipt(
                receipt,
                receipt_ref=receipt_ref,
                expected_digest="sha256:" + "f" * 64,
            )

    def test_authorization_consumption_is_single_use(self) -> None:
        fixture = ProofFixture(self.root)
        with self.assertRaisesRegex(ControlledProofError, "already consumed"):
            consume_authorization(
                authorization=fixture.authorization,
                authorization_digest=fixture.authorization_digest,
                executor_source_revision=REVISION,
                consumption_root=self.root / "consumptions",
                contracts=fixture.contracts,
            )

    def test_snapshot_can_resume_the_exact_canonical_consumption_receipt(self) -> None:
        fixture = ProofFixture(self.root)
        receipt, receipt_path, receipt_digest = (
            platform_drill.consume_or_resume_controlled_authorization(
                authorization=fixture.authorization,
                authorization_digest=fixture.authorization_digest,
                consumption_root=self.root / "consumptions",
                contracts=fixture.contracts,
            )
        )
        self.assertEqual(receipt, fixture.consumption)
        self.assertEqual(receipt_path, fixture.consumption_path)
        self.assertEqual(receipt_digest, fixture.consumption_digest)

    def test_controlled_snapshot_lock_serializes_one_authorization(self) -> None:
        authorization_ref = "platform-controlled-proof://authorizations/session-001"
        with platform_drill.controlled_snapshot_lock(
            self.root, authorization_ref
        ):
            with self.assertRaisesRegex(SystemExit, "already in progress"):
                with platform_drill.controlled_snapshot_lock(
                    self.root, authorization_ref
                ):
                    self.fail("a second snapshot lock must not be acquired")

    def test_incomplete_snapshot_is_rebuilt_only_before_execution_claim(self) -> None:
        run_dir = self.root / "run"
        execution_claim_path = self.root / "executions" / "claim.json"
        run_dir.mkdir()
        (run_dir / "baseline.yaml").write_text("partial: true\n", encoding="utf-8")
        platform_drill.recover_incomplete_controlled_run(
            run_dir, execution_claim_path
        )
        self.assertFalse(run_dir.exists())

        run_dir.mkdir()
        execution_claim_path.parent.mkdir()
        execution_claim_path.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "after execution was claimed"):
            platform_drill.recover_incomplete_controlled_run(
                run_dir, execution_claim_path
            )

    def test_snapshot_control_inputs_must_stay_outside_recovery_scope(self) -> None:
        run_dir = self.root / "run"
        with self.assertRaisesRegex(
            SystemExit,
            "inputs must remain outside the canonical run directory",
        ):
            platform_drill.reject_control_inputs_below_run_dir(
                run_dir,
                {
                    "--authorization-file": run_dir / "authorization.json",
                    "--baseline-file": self.root / "baseline.json",
                },
            )
        platform_drill.reject_control_inputs_below_run_dir(
            run_dir,
            {"--authorization-file": self.root / "authorization.json"},
        )
        run_dir.mkdir()
        linked_input = self.root / "linked-authorization.json"
        linked_input.symlink_to(run_dir / "authorization.json")
        with self.assertRaisesRegex(
            SystemExit,
            "inputs must remain outside the canonical run directory",
        ):
            platform_drill.reject_control_inputs_below_run_dir(
                run_dir,
                {"--authorization-file": linked_input},
            )

    def test_controlled_execution_claim_resumes_only_the_exact_binding(self) -> None:
        fixture = ProofFixture(self.root)
        output_root = self.root / "claimed-output"
        first_claim, first_path, first_digest = fixture.claim_for(output_root)
        resumed_claim, resumed_path, resumed_digest = fixture.claim_for(output_root)
        self.assertEqual(resumed_claim, first_claim)
        self.assertEqual(resumed_path, first_path)
        self.assertEqual(resumed_digest, first_digest)
        with self.assertRaisesRegex(ControlledProofError, "different bindings"):
            fixture.claim_for(self.root / "other-output")

    def test_owner_context_projection_resumes_after_partial_persistence(self) -> None:
        fixture = ProofFixture(self.root / "fixture")
        output_root = self.root / "resumable-owner-contexts"
        original_write = execution_module.write_json_atomic
        write_count = 0

        def fail_second_write(path, payload):
            nonlocal write_count
            write_count += 1
            if write_count == 2:
                raise OSError("injected context persistence failure")
            return original_write(path, payload)

        with mock.patch.object(
            execution_module,
            "write_json_atomic",
            side_effect=fail_second_write,
        ):
            with self.assertRaisesRegex(OSError, "injected"):
                project_owner_contexts(
                    authorization=fixture.authorization,
                    authorization_digest=fixture.authorization_digest,
                    consumption_receipt=fixture.consumption,
                    consumption_receipt_digest=fixture.consumption_digest,
                    baseline=fixture.baseline,
                    output_root=output_root,
                    contracts=fixture.contracts,
                )

        resumed = project_owner_contexts(
            authorization=fixture.authorization,
            authorization_digest=fixture.authorization_digest,
            consumption_receipt=fixture.consumption,
            consumption_receipt_digest=fixture.consumption_digest,
            baseline=fixture.baseline,
            output_root=output_root,
            contracts=fixture.contracts,
        )
        self.assertEqual(resumed.oos, read_bounded_json(resumed.oos_path))
        self.assertEqual(resumed.wgcf, read_bounded_json(resumed.wgcf_path))

    def test_execution_lock_serializes_exact_authorization_resume(self) -> None:
        platform_root = self.root / "platform-engineering"
        authorization_id = "platform-controlled-proof://authorizations/session-001"
        with _execution_lock(platform_root, authorization_id):
            with self.assertRaisesRegex(ControlledProofError, "already active"):
                with _execution_lock(platform_root, authorization_id):
                    self.fail("concurrent execution lock unexpectedly acquired")

    def test_operator_scope_lease_denies_a_second_authorization_until_release(
        self,
    ) -> None:
        fixture = ProofFixture(self.root)
        first_output = self.root / "first-output"
        first_claim, _first_path, first_digest = fixture.claim_for(first_output)

        second = copy.deepcopy(fixture.authorization)
        second["authorization_id"] = (
            "platform-controlled-proof://authorizations/session-002"
        )
        second["commissioning_session"]["commissioning_session_id"] = "session-002"
        for index, scenario in enumerate(
            second["commissioning_session"]["scenario_executions"], start=1
        ):
            scenario["scenario_execution_id"] = (
                f"session-002:{index:02d}:{scenario['scenario_id']}"
            )
        second["evidence"]["verification_pack_ref"] = (
            "artifact://controlled-proof/verification/session-002"
        )
        second_path = self.root / "second-authorization.json"
        second_digest = write_json_atomic(second_path, second)
        second_receipt, _second_receipt_path, second_receipt_digest = (
            consume_authorization(
                authorization=second,
                authorization_digest=second_digest,
                executor_source_revision=REVISION,
                consumption_root=self.root / "second-consumptions",
                contracts=fixture.contracts,
            )
        )
        second_output = self.root / "second-output"
        with self.assertRaisesRegex(ControlledProofError, "scope is already leased"):
            claim_execution(
                authorization=second,
                authorization_digest=second_digest,
                consumption_receipt=second_receipt,
                consumption_receipt_digest=second_receipt_digest,
                output_root=second_output,
                operator_id=fixture.baseline["operator_id"],
                execution_root=self.root / "execution-claims",
                contracts=fixture.contracts,
            )

        release_execution_scope_lease(
            authorization=fixture.authorization,
            authorization_digest=fixture.authorization_digest,
            consumption_receipt=fixture.consumption,
            consumption_receipt_digest=fixture.consumption_digest,
            execution_claim=first_claim,
            output_root=first_output,
            operator_scope=operator_scope_id(fixture.baseline["operator_id"]),
            lease_root=self.root / "_controlled-proof-scope-leases",
        )
        second_claim, _second_path, _second_digest = claim_execution(
            authorization=second,
            authorization_digest=second_digest,
            consumption_receipt=second_receipt,
            consumption_receipt_digest=second_receipt_digest,
            output_root=second_output,
            operator_id=fixture.baseline["operator_id"],
            execution_root=self.root / "execution-claims",
            contracts=fixture.contracts,
        )
        self.assertEqual(second_claim["authorization_id"], second["authorization_id"])

    def test_interrupted_execution_claim_resumes_its_exact_scope_lease(self) -> None:
        fixture = ProofFixture(self.root)
        output_root = self.root / "resumed-output"
        original_create = authority_module.create_json_exclusive
        call_count = 0

        def fail_after_lease(path, payload, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise OSError("injected claim persistence failure")
            return original_create(path, payload, **kwargs)

        with mock.patch.object(
            authority_module,
            "create_json_exclusive",
            side_effect=fail_after_lease,
        ):
            with self.assertRaisesRegex(OSError, "injected"):
                fixture.claim_for(output_root)

        lease_path = execution_scope_lease_path(
            operator_scope_id(fixture.baseline["operator_id"]),
            self.root / "_controlled-proof-scope-leases",
        )
        lease = read_bounded_json(lease_path)
        claim, _claim_path, _claim_digest = fixture.claim_for(output_root)
        self.assertEqual(claim["claimed_at"], lease["acquired_at"])

    def test_execution_claim_preserves_exact_restore_start_reserve(self) -> None:
        fixture = ProofFixture(self.root)
        expires_at = datetime.fromisoformat(
            fixture.authorization["window"]["expires_at"].replace("Z", "+00:00")
        )
        claimed_at = (
            expires_at - timedelta(seconds=TERMINAL_CLEANUP_START_RESERVE_SECONDS)
        ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        with self.assertRaisesRegex(ControlledProofError, "exact-restore start reserve"):
            claim_execution(
                authorization=fixture.authorization,
                authorization_digest=fixture.authorization_digest,
                consumption_receipt=fixture.consumption,
                consumption_receipt_digest=fixture.consumption_digest,
                output_root=self.root / "late-output",
                operator_id=fixture.baseline["operator_id"],
                execution_root=self.root / "late-execution",
                contracts=fixture.contracts,
                claimed_at=claimed_at,
            )

    def test_executor_rejects_output_root_outside_execution_claim(self) -> None:
        fixture = ProofFixture(self.root)
        bound_output = self.root / "bound-output"
        claim, _claim_path, claim_digest = fixture.claim_for(bound_output)
        executor = ControlledProofExecutor(
            authorization=fixture.authorization,
            authorization_digest=fixture.authorization_digest,
            consumption_receipt=fixture.consumption,
            consumption_receipt_digest=fixture.consumption_digest,
            execution_claim=claim,
            execution_claim_digest=claim_digest,
            baseline=fixture.baseline,
            contexts=fixture.contexts,
            contracts=fixture.contracts,
            driver=FakeDriver(fixture),
            output_root=self.root / "different-output",
        )
        with self.assertRaisesRegex(ControlledProofError, "output_root_digest"):
            executor.run()

    def test_executor_reserves_the_end_of_the_window_for_exact_restore(self) -> None:
        fixture = ProofFixture(self.root)
        executor = executor_for(fixture, FakeDriver(fixture), self.root / "result")
        executor.authorization["window"]["expires_at"] = timestamp(
            timedelta(seconds=TERMINAL_CLEANUP_START_RESERVE_SECONDS)
        )
        with self.assertRaisesRegex(ControlledProofError, "exact-restore start reserve"):
            executor._assert_proof_action_window()

    def test_executor_emits_complete_passing_result(self) -> None:
        fixture = ProofFixture(self.root)
        driver = FakeDriver(fixture)
        output = self.root / "result"
        result, digest = executor_for(fixture, driver, output).run()
        self.assertEqual(result["outcome"], "passed")
        self.assertEqual(
            [item["scenario_id"] for item in result["scenario_outcomes"]],
            list(SCENARIO_ORDER),
        )
        self.assertEqual(result["baseline_restore"]["status"], "exact-baseline-restored")
        self.assertEqual(digest, sha256_file(self.root / "result" / "controlled-proof-result.json"))
        self.assertTrue(driver.cleaned)

    def test_result_builder_rejects_receipt_outside_authorized_pairs(self) -> None:
        fixture = ProofFixture(self.root)
        result, _ = executor_for(
            fixture,
            FakeDriver(fixture),
            self.root / "valid-result",
        ).run()
        receipts = copy.deepcopy(result["owner_receipts"])
        receipts[0]["scenario_execution_id"] = "unbound-execution"
        with self.assertRaisesRegex(ControlledProofError, "unauthorized owner receipt"):
            build_result(
                authorization=fixture.authorization,
                authorization_digest=fixture.authorization_digest,
                consumption_receipt=fixture.consumption,
                scenario_outcomes=result["scenario_outcomes"],
                owner_receipts=receipts,
                restore_outcome=result["scenario_outcomes"][-1],
                outcome="passed",
                contracts=fixture.contracts,
                completed_at=result["completed_at"],
                session_started_at=result["commissioning_session"]["started_at"],
            )

    def test_scenario_failure_stops_new_work_but_restores_and_emits_failure(self) -> None:
        fixture = ProofFixture(self.root)
        driver = FakeDriver(fixture, fail_scenario="temporal-runtime-restart")
        result, _ = executor_for(
            fixture, driver, self.root / "failed-result"
        ).run()
        statuses = {
            item["scenario_id"]: item["status"]
            for item in result["scenario_outcomes"]
        }
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(statuses["temporal-runtime-restart"], "failed")
        self.assertEqual(statuses["deterministic-replay"], "not-run")
        self.assertEqual(statuses["exact-baseline-restore"], "passed")
        self.assertTrue(driver.cleaned)

    def test_receipt_outside_scenario_timeline_fails_closed(self) -> None:
        fixture = ProofFixture(self.root)
        result, _ = executor_for(
            fixture,
            FakeDriver(fixture, stale_receipt=True),
            self.root / "stale-receipt",
        ).run()
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(result["scenario_outcomes"][0]["status"], "failed")
        self.assertEqual(result["scenario_outcomes"][1]["status"], "not-run")

    def test_prepare_failure_restores_and_emits_failed_result(self) -> None:
        fixture = ProofFixture(self.root)
        driver = FakeDriver(fixture, fail_prepare=True)
        result, _ = executor_for(
            fixture, driver, self.root / "prepare-failure"
        ).run()
        statuses = [item["status"] for item in result["scenario_outcomes"]]
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(statuses[:-1], ["not-run"] * (len(SCENARIO_ORDER) - 1))
        self.assertEqual(statuses[-1], "passed")
        preparation_evidence_count = sum(
            evidence["artifact_ref"] == "artifact://test/runtime/prepare-failure"
            for outcome in result["scenario_outcomes"]
            for evidence in outcome["evidence_refs"]
        )
        self.assertEqual(preparation_evidence_count, 1)
        self.assertTrue(driver.cleaned)

    def test_generic_drill_commands_cannot_mutate_controlled_run(self) -> None:
        for action in (
            "baseline attestation",
            "activation",
            "verification",
            "supplemental evidence",
        ):
            with self.subTest(action=action):
                with self.assertRaisesRegex(SystemExit, "source-reviewed executor"):
                    platform_drill.deny_generic_mutation_for_controlled_proof(
                        {"controlledProof": {}}, action
                    )
        with self.assertRaisesRegex(SystemExit, "source-reviewed executor"):
            platform_drill.enforce_controlled_restore_record(
                {"controlledProof": {}}, "restored"
            )
        with self.assertRaisesRegex(SystemExit, "controlled-exception"):
            platform_drill.enforce_controlled_restore_record(
                {"controlledProof": {}}, "exception"
            )

    def test_restore_failure_requires_exception_then_emits_stopped_result(self) -> None:
        fixture = ProofFixture(self.root)
        driver = FakeDriver(fixture, fail_restore=True)
        output = self.root / "restore-failure"
        executor = executor_for(fixture, driver, output)
        with self.assertRaisesRegex(ControlledProofError, "stopped draft"):
            executor.run()
        self.assertFalse((output / STOPPED_RESULT_NAME).exists())
        draft_path = output / STOPPED_DRAFT_NAME
        draft = read_bounded_json(draft_path)
        draft_digest = sha256_file(draft_path)
        self.assertEqual(draft["failure_reason"], "exact-baseline-restore-failed")
        restore_receipt = next(
            receipt
            for receipt in draft["owner_receipts"]
            if receipt["scenario_id"] == "exact-baseline-restore"
        )
        self.assertEqual(restore_receipt["owner_result"], "failed")
        exception, exception_path, exception_digest = record_governed_exception(
            authorization=fixture.authorization,
            authorization_digest=fixture.authorization_digest,
            consumption_receipt=fixture.consumption,
            consumption_receipt_digest=fixture.consumption_digest,
            execution_claim=executor.execution_claim,
            execution_claim_digest=executor.execution_claim_digest,
            stopped_draft=draft,
            stopped_draft_digest=draft_digest,
            output_root=output,
            decision="defer",
            justification="Exact baseline restoration requires operator repair.",
            owner="platform-engineering",
            review_on="2026-08-10",
            actor="test-operator",
            note="Proof work remains stopped.",
            contracts=fixture.contracts,
        )
        self.assertEqual(exception_path, output / GOVERNED_EXCEPTION_NAME)
        result, result_digest = finalize_stopped_result(
            authorization=fixture.authorization,
            authorization_digest=fixture.authorization_digest,
            consumption_receipt=fixture.consumption,
            consumption_receipt_digest=fixture.consumption_digest,
            execution_claim=executor.execution_claim,
            execution_claim_digest=executor.execution_claim_digest,
            stopped_draft=draft,
            stopped_draft_digest=draft_digest,
            governed_exception=exception,
            governed_exception_digest=exception_digest,
            output_root=output,
            contracts=fixture.contracts,
        )
        self.assertEqual(result["outcome"], "stopped")
        self.assertEqual(
            result["baseline_restore"]["status"],
            "governed-exception-recorded",
        )
        self.assertEqual(result["exception"]["record_digest"], exception_digest)
        self.assertEqual(result_digest, sha256_file(output / STOPPED_RESULT_NAME))
        repeated, repeated_digest = finalize_stopped_result(
            authorization=fixture.authorization,
            authorization_digest=fixture.authorization_digest,
            consumption_receipt=fixture.consumption,
            consumption_receipt_digest=fixture.consumption_digest,
            execution_claim=executor.execution_claim,
            execution_claim_digest=executor.execution_claim_digest,
            stopped_draft=draft,
            stopped_draft_digest=draft_digest,
            governed_exception=exception,
            governed_exception_digest=exception_digest,
            output_root=output,
            contracts=fixture.contracts,
        )
        self.assertEqual(repeated, result)
        self.assertEqual(repeated_digest, result_digest)
        self.assertTrue(driver.cleaned)

    def test_cleanup_failure_is_a_stopped_draft_not_a_successful_restore(self) -> None:
        fixture = ProofFixture(self.root)
        output = self.root / "cleanup-failure"
        executor = executor_for(
            fixture,
            FakeDriver(fixture, fail_cleanup=True),
            output,
        )
        with self.assertRaisesRegex(ControlledProofError, "stopped draft"):
            executor.run()
        draft = read_bounded_json(output / STOPPED_DRAFT_NAME)
        self.assertEqual(draft["failure_reason"], "terminal-cleanup-failed")
        self.assertEqual(draft["scenario_outcomes"][-1]["status"], "failed")
        self.assertFalse((output / STOPPED_RESULT_NAME).exists())

    def test_platform_ledger_records_and_finalizes_stopped_result(self) -> None:
        run_dir = (
            self.root
            / "workspace"
            / "platform-engineering"
            / ".platform-drills"
            / "temporal-component-commissioning-proof"
            / "session-001"
        )
        output = run_dir / "controlled-proof-output"
        fixture = ProofFixture(self.root / "fixture")
        executor = executor_for(
            fixture,
            FakeDriver(fixture, fail_restore=True),
            output,
        )
        with self.assertRaisesRegex(ControlledProofError, "stopped draft"):
            executor.run()
        execution_claim_path = next(
            (fixture.root / "execution-claims").glob("*.json")
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        platform_drill.dump_yaml(
            run_dir / "run.yaml",
            {
                "schema_version": 1,
                "run_id": "session-001",
                "profile_id": "temporal-component-commissioning-proof",
                "phaseStatus": {
                    "baseline": "captured",
                    "activation": "pending",
                    "verification": "pending",
                    "restore": "pending",
                },
                "authorization": {"digest": fixture.authorization_digest},
                "controlledProof": {
                    "authorizationPath": str(fixture.authorization_path),
                    "operatorApprovalPath": str(fixture.operator_approval),
                    "securityAuthorizationPath": str(fixture.security_approval),
                    "baselinePath": str(fixture.baseline_path),
                    "baselineEvidenceRoot": str(fixture.evidence_root),
                    "consumptionReceiptPath": str(fixture.consumption_path),
                    "consumptionReceiptDigest": fixture.consumption_digest,
                    "executionClaimPath": str(execution_claim_path),
                    "outputRoot": str(output),
                },
            },
        )
        platform_drill.dump_yaml(run_dir / "contract.yaml", {"schema_version": 1})
        platform_drill.dump_yaml(run_dir / "baseline.yaml", {})
        platform_drill.dump_yaml(run_dir / "verification.yaml", {})
        surfaces = [
            {"id": surface_id, "status": "pending"}
            for surface_id in (
                "temporal-runtime",
                "oos-validation-readiness-worker",
                "wgcf-readiness-activity-worker",
            )
        ]
        platform_drill.dump_yaml(run_dir / "restore.yaml", {"surfaces": surfaces})
        platform_drill.dump_yaml(
            run_dir / "evidence.yaml",
            {
                "restoreAttestation": {"surfaces": copy.deepcopy(surfaces)},
                "exceptionRegister": {"entries": []},
            },
        )
        self.assertEqual(
            platform_drill.controlled_execution_status(
                run_dir,
                platform_drill.load_yaml(run_dir / "run.yaml"),
            ),
            "stopped-awaiting-exception",
        )
        restored_surfaces = [
            {
                "surface_id": surface_id,
                "state": "not-installed",
                "observation_digest": DIGEST,
            }
            for surface_id in (
                "temporal-runtime",
                "oos-validation-readiness-worker",
                "wgcf-readiness-activity-worker",
            )
        ]
        with mock.patch(
            "controlled_proof.runtime.LocalK3sRuntimeControl"
        ) as runtime_control:
            runtime_control.return_value.cleanup.return_value = restored_surfaces
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    platform_drill.cmd_controlled_cleanup(
                        SimpleNamespace(run=str(run_dir))
                    ),
                    0,
                )
        run_payload = platform_drill.load_yaml(run_dir / "run.yaml")
        self.assertEqual(
            run_payload["controlledProof"]["cleanupStatus"],
            "exact-baseline-restored",
        )
        self.assertTrue(
            (output / "restore" / "terminal-cleanup-retry.json").is_file()
        )
        exception_args = SimpleNamespace(
            run=str(run_dir),
            actor="test-operator",
            decision="defer",
            justification="Exact baseline restoration requires operator repair.",
            owner="platform-engineering",
            review_on="2026-08-10",
            note="Proof work remains stopped.",
        )
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                platform_drill.cmd_controlled_exception(exception_args),
                0,
            )
        run_payload = platform_drill.load_yaml(run_dir / "run.yaml")
        self.assertEqual(
            run_payload["controlledProof"]["executionStatus"],
            "stopped-awaiting-result",
        )
        self.assertTrue((output / GOVERNED_EXCEPTION_NAME).exists())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                platform_drill.cmd_controlled_finalize(
                    SimpleNamespace(run=str(run_dir))
                ),
                0,
            )
        run_payload = platform_drill.load_yaml(run_dir / "run.yaml")
        self.assertEqual(
            run_payload["controlledProof"]["executionStatus"],
            "stopped-result-emitted",
        )
        self.assertEqual(
            read_bounded_json(output / STOPPED_RESULT_NAME)["outcome"],
            "stopped",
        )
        self.assertEqual(
            platform_drill.controlled_execution_status(
                run_dir,
                platform_drill.load_yaml(run_dir / "run.yaml"),
            ),
            "result-emitted",
        )

    def test_runtime_manifest_uses_only_permit_bound_images_and_identities(self) -> None:
        fixture = ProofFixture(self.root)
        resources = _owner_runtime_manifest(
            authorization=fixture.authorization,
            contexts=fixture.contexts,
            kubernetes_namespace="devint-temporal-alice",
            workspace_governance_source=(
                self.root / "runtime-source" / "workspace-governance"
            ),
        )
        deployments = {
            item["metadata"]["name"]: item
            for item in resources
            if item["kind"] == "Deployment"
        }
        self.assertEqual(
            set(deployments),
            {
                "controlled-proof-oos-api",
                "controlled-proof-oos-worker",
                "controlled-proof-wgcf-worker",
            },
        )
        for deployment in deployments.values():
            image = deployment["spec"]["template"]["spec"]["containers"][0]["image"]
            self.assertIn("@sha256:", image)
            self.assertFalse(
                deployment["spec"]["template"]["spec"][
                    "automountServiceAccountToken"
                ]
            )
        wgcf_volumes = deployments["controlled-proof-wgcf-worker"]["spec"][
            "template"
        ]["spec"]["volumes"]
        source_volume = next(
            item for item in wgcf_volumes if item["name"] == "workspace-governance-source"
        )
        self.assertEqual(
            source_volume["hostPath"]["path"],
            str(self.root / "runtime-source" / "workspace-governance"),
        )

    def test_internal_runtime_script_denies_direct_invocation(self) -> None:
        completed = subprocess.run(
            [
                "bash",
                str(PROFILE_ROOT / "scripts" / "controlled-proof-runtime.sh"),
                "prepare",
            ],
            check=False,
            capture_output=True,
            text=True,
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": str(self.root),
                "USER": "tester",
                "CONTROLLED_PROOF_EXECUTOR": "true",
                "CONTROLLED_PROOF_AUTHORIZATION_ID": (
                    "platform-controlled-proof://authorizations/forged"
                ),
                "CONTROLLED_PROOF_CONSUMPTION_RECEIPT_DIGEST": DIGEST,
                "CONTROLLED_PROOF_EXECUTOR_SOURCE_REVISION": REVISION,
            },
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("missing a permit-bound artifact", completed.stderr)


if __name__ == "__main__":
    unittest.main()
