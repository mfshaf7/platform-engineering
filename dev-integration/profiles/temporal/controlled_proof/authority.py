from __future__ import annotations

import copy
import hashlib
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Protocol

import yaml

from .model import (
    MAX_ARTIFACT_BYTES,
    PERMITTED_ACTIONS,
    REQUIRED_SCENARIO_OWNERS,
    REQUIRED_STOP_CONDITIONS,
    REVISION_RE,
    SCENARIO_ORDER,
    TEMPORAL_NAMESPACE_MAX_LENGTH,
    TERMINAL_CLEANUP_START_RESERVE_SECONDS,
    ControlledProofError,
    canonical_digest,
    controlled_subprocess_environment,
    create_json_exclusive,
    decode_bounded_json,
    load_schema,
    normalize_digest,
    now_utc,
    operator_scope_id,
    operator_scoped_dns_label,
    parse_timestamp,
    read_bounded_json,
    read_bounded_json_with_digest,
    require_exact_keys,
    require_identifier,
    resolve_controlled_command,
    sha256_bytes,
    sha256_file,
    validate_schema,
    write_json_atomic,
)

PROFILE_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = Path(__file__).resolve().parent / "contracts"
EXECUTION_SOURCE_REPOS = (
    "platform-engineering",
    "operator-orchestration-service",
    "workspace-governance",
    "workspace-governance-control-fabric",
)
SECURITY_AUTHORIZATION_SOURCE_REPO = "security-architecture"
SECURITY_AUTHORIZATION_MERGED_REF = "refs/remotes/origin/main"
CONTROLLED_SOURCE_REPOS = (
    *EXECUTION_SOURCE_REPOS,
    SECURITY_AUTHORIZATION_SOURCE_REPO,
)
SURFACE_ORDER = (
    "temporal-runtime",
    "oos-validation-readiness-worker",
    "wgcf-readiness-activity-worker",
)
PROBE_IDS = {
    "temporal-runtime": "temporal-runtime-status-v1",
    "oos-validation-readiness-worker": "oos-controlled-proof-status-v1",
    "wgcf-readiness-activity-worker": "wgcf-controlled-proof-status-v1",
}
PLACEHOLDER_DIGEST = "sha256:" + "0" * 64
REVIEW_WORK_ITEM_REF = "openproject://work_packages/825"
EXPECTED_BASELINE_STATES = {
    "temporal-runtime": "not-installed",
    "oos-validation-readiness-worker": "not-installed",
    "wgcf-readiness-activity-worker": "not-installed",
}
EXPECTED_RUNTIME_IDENTITIES = {
    "oos-api": "operator-orchestration-service-api",
    "oos-workflow-worker": "oos-workflow-worker",
    "wgcf-activity-worker": "wgcf-controlled-proof-activity-worker",
}
EXPECTED_TASK_QUEUES = {
    "operator-orchestration-service": "oos.controlled-proof.validation-readiness.v1",
    "workspace-governance-control-fabric": "wgcf.controlled-proof.validation-readiness.v1",
}
OWNER_RUNTIME_IMAGES = {
    "ghcr.io/mfshaf7/operator-orchestration-service",
    "ghcr.io/mfshaf7/operator-orchestration-service-worker",
    "ghcr.io/mfshaf7/workspace-governance-control-fabric-worker",
}
RuntimeImageValidator = Callable[[list[dict[str, str]], dict[str, str]], None]
VENDORED_CONTRACT_SOURCES = {
    "workspace-governance": {
        "controlled-runtime-proof-authorization.schema.json": (
            "contracts/schemas/controlled-runtime-proof-authorization.schema.json"
        ),
        "controlled-runtime-proof-result.schema.json": (
            "contracts/schemas/controlled-runtime-proof-result.schema.json"
        ),
    },
    "operator-orchestration-service": {
        "oos-execution-context.schema.json": (
            "contracts/orchestration/controlled-proof-execution-context.schema.json"
        ),
        "oos-owner-receipt.schema.json": (
            "contracts/orchestration/controlled-proof-owner-receipt.schema.json"
        ),
        "oos-run-projection.schema.json": (
            "contracts/orchestration/controlled-proof-run-projection.schema.json"
        ),
    },
    "workspace-governance-control-fabric": {
        "wgcf-owner-context.schema.json": (
            "schemas/controlled-proof-owner-context.schema.json"
        ),
        "wgcf-owner-receipt.schema.json": (
            "schemas/controlled-proof-owner-receipt.schema.json"
        ),
    },
}
LOCAL_CONTRACT_FILES = {
    "approval-binding.schema.json",
    "baseline.schema.json",
    "consumption-receipt.schema.json",
    "platform-owner-receipt.schema.json",
}


@dataclass(frozen=True)
class ContractSet:
    authorization: dict[str, Any]
    result: dict[str, Any]
    approval: dict[str, Any]
    baseline: dict[str, Any]
    consumption: dict[str, Any]
    platform_receipt: dict[str, Any]
    oos_context: dict[str, Any]
    oos_receipt: dict[str, Any]
    oos_projection: dict[str, Any]
    wgcf_context: dict[str, Any]
    wgcf_receipt: dict[str, Any]


def load_contracts() -> ContractSet:
    validate_vendored_contracts()
    return ContractSet(
        authorization=load_schema(
            CONTRACT_ROOT / "controlled-runtime-proof-authorization.schema.json"
        ),
        result=load_schema(CONTRACT_ROOT / "controlled-runtime-proof-result.schema.json"),
        approval=load_schema(CONTRACT_ROOT / "approval-binding.schema.json"),
        baseline=load_schema(CONTRACT_ROOT / "baseline.schema.json"),
        consumption=load_schema(CONTRACT_ROOT / "consumption-receipt.schema.json"),
        platform_receipt=load_schema(CONTRACT_ROOT / "platform-owner-receipt.schema.json"),
        oos_context=load_schema(CONTRACT_ROOT / "oos-execution-context.schema.json"),
        oos_receipt=load_schema(CONTRACT_ROOT / "oos-owner-receipt.schema.json"),
        oos_projection=load_schema(CONTRACT_ROOT / "oos-run-projection.schema.json"),
        wgcf_context=load_schema(CONTRACT_ROOT / "wgcf-owner-context.schema.json"),
        wgcf_receipt=load_schema(CONTRACT_ROOT / "wgcf-owner-receipt.schema.json"),
    )


def validate_vendored_contracts() -> dict[str, Any]:
    manifest = _source_manifest()
    if set(manifest) != {"schema_version", "sources", "local_files"} or (
        manifest.get("schema_version") != 1
        or not isinstance(manifest.get("sources"), dict)
        or not isinstance(manifest.get("local_files"), dict)
    ):
        raise ControlledProofError("controlled-proof source manifest is invalid")
    if set(manifest["sources"]) != set(VENDORED_CONTRACT_SOURCES):
        raise ControlledProofError("controlled-proof source manifest owner set is invalid")
    declared_files: set[str] = set()
    for repo, source in manifest["sources"].items():
        revision = source.get("revision")
        if not isinstance(revision, str) or REVISION_RE.fullmatch(revision) is None:
            raise ControlledProofError(f"{repo} source manifest revision is invalid")
        files = source.get("files")
        expected_sources = VENDORED_CONTRACT_SOURCES[repo]
        if not isinstance(files, dict) or set(files) != set(expected_sources):
            raise ControlledProofError(f"{repo} source manifest contract set is invalid")
        for filename, binding in files.items():
            if filename in declared_files:
                raise ControlledProofError(f"vendored contract is declared twice: {filename}")
            declared_files.add(filename)
            if not isinstance(binding, dict) or set(binding) != {"source_path", "digest"}:
                raise ControlledProofError(f"{filename} source binding is invalid")
            if binding["source_path"] != expected_sources[filename]:
                raise ControlledProofError(f"{filename} source path is invalid")
            path = CONTRACT_ROOT / filename
            if not path.is_file():
                raise ControlledProofError(f"vendored contract is missing: {filename}")
            if sha256_file(path) != normalize_digest(
                binding["digest"], f"{filename} source digest"
            ):
                raise ControlledProofError(f"vendored contract digest drifted: {filename}")

    local_files = manifest["local_files"]
    if set(local_files) != LOCAL_CONTRACT_FILES:
        raise ControlledProofError("controlled-proof local contract set is invalid")
    for filename, expected_digest in local_files.items():
        path = CONTRACT_ROOT / filename
        if not path.is_file() or sha256_file(path) != normalize_digest(
            expected_digest, f"{filename} local digest"
        ):
            raise ControlledProofError(f"local controlled-proof contract drifted: {filename}")

    expected_json_files = declared_files | LOCAL_CONTRACT_FILES
    actual_json_files = {path.name for path in CONTRACT_ROOT.glob("*.json")}
    if actual_json_files != expected_json_files:
        raise ControlledProofError("controlled-proof contract directory is not fully declared")
    return manifest


def reviewed_contract_source_revisions() -> dict[str, str]:
    """Return owner revisions whose exact contracts were reviewed and vendored."""

    manifest = validate_vendored_contracts()
    return {
        repo: source["revision"]
        for repo, source in manifest["sources"].items()
    }


def _source_manifest() -> dict[str, Any]:
    manifest_path = CONTRACT_ROOT / "source-manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(manifest, dict):
        raise ControlledProofError("controlled-proof source manifest is invalid")
    return manifest


class BaselineProbe(Protocol):
    def capture(self, surface_id: str) -> tuple[str, dict[str, Any]]: ...


class SourceResolver(Protocol):
    def revision(self, repo: str) -> tuple[str, bool]: ...

    def revision_is_ancestor_of(
        self, repo: str, revision: str, ref: str
    ) -> bool: ...

    def read_file(
        self,
        repo: str,
        revision: str,
        relative_path: str,
        *,
        require_current_checkout: bool = True,
    ) -> bytes: ...


class GitSourceResolver:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()

    def revision(self, repo: str) -> tuple[str, bool]:
        repo_root = self.workspace_root / repo
        if not (repo_root / ".git").exists():
            raise ControlledProofError(f"source repo is unavailable: {repo}")
        commit = _run_checked(["git", "-C", str(repo_root), "rev-parse", "HEAD"])
        if REVISION_RE.fullmatch(commit) is None:
            raise ControlledProofError(f"source repo returned an invalid revision: {repo}")
        dirty = bool(
            _run_checked(["git", "-C", str(repo_root), "status", "--short"])
        )
        return commit, dirty

    def revision_is_ancestor_of(
        self, repo: str, revision: str, ref: str
    ) -> bool:
        if repo not in CONTROLLED_SOURCE_REPOS:
            raise ControlledProofError(
                f"source repo is outside the proof boundary: {repo}"
            )
        if REVISION_RE.fullmatch(revision) is None:
            raise ControlledProofError(f"source revision is invalid: {repo}")
        repo_root = self.workspace_root / repo
        if not (repo_root / ".git").exists():
            raise ControlledProofError(f"source repo is unavailable: {repo}")
        target_revision = _run_checked(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", ref]
        )
        try:
            _run_checked(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "merge-base",
                    "--is-ancestor",
                    revision,
                    target_revision,
                ]
            )
        except ControlledProofError:
            return False
        return True

    def read_file(
        self,
        repo: str,
        revision: str,
        relative_path: str,
        *,
        require_current_checkout: bool = True,
    ) -> bytes:
        if repo not in CONTROLLED_SOURCE_REPOS:
            raise ControlledProofError(f"source repo is outside the proof boundary: {repo}")
        if REVISION_RE.fullmatch(revision) is None:
            raise ControlledProofError(f"source revision is invalid: {repo}")
        source_path = _source_relative_path(relative_path)
        repo_root = self.workspace_root / repo
        if not (repo_root / ".git").exists():
            raise ControlledProofError(f"source repo is unavailable: {repo}")
        if require_current_checkout:
            current_revision, dirty = self.revision(repo)
            if dirty or current_revision != revision:
                raise ControlledProofError(
                    f"source artifact repo is not clean at its bound revision: {repo}"
                )
        object_ref = f"{revision}:{source_path}"
        size_text = _run_checked(
            ["git", "-C", str(repo_root), "cat-file", "-s", object_ref]
        )
        try:
            size = int(size_text)
        except ValueError as exc:
            raise ControlledProofError(
                f"source artifact size is invalid: {repo}:{source_path}"
            ) from exc
        if size <= 0 or size > MAX_ARTIFACT_BYTES:
            raise ControlledProofError(
                f"source artifact exceeds its boundary: {repo}:{source_path}"
            )
        content = _run_checked_bytes(
            ["git", "-C", str(repo_root), "cat-file", "blob", object_ref]
        )
        if len(content) != size:
            raise ControlledProofError(
                f"source artifact size changed while reading: {repo}:{source_path}"
            )
        return content


class LocalBaselineProbe:
    """Read-only fixed probes for the three commissioning surfaces."""

    def __init__(self, workspace_root: Path, operator_id: str):
        self.workspace_root = workspace_root.resolve()
        self.operator_id = require_identifier(operator_id, "operator_id")

    def capture(self, surface_id: str) -> tuple[str, dict[str, Any]]:
        env = controlled_subprocess_environment()
        namespace = operator_scoped_dns_label(
            "devint-temporal", self.operator_id
        )
        if surface_id == "temporal-runtime":
            command = [
                "k3s",
                "kubectl",
                "get",
                "namespace",
                namespace,
                "--ignore-not-found=true",
                "-o",
                "name",
            ]
            cwd = self.workspace_root / "platform-engineering"
        elif surface_id == "oos-validation-readiness-worker":
            command = [
                "k3s",
                "kubectl",
                "-n",
                namespace,
                "get",
                "deployment/controlled-proof-oos-worker",
                "--ignore-not-found=true",
                "-o",
                "name",
            ]
            cwd = self.workspace_root / "platform-engineering"
        elif surface_id == "wgcf-readiness-activity-worker":
            command = [
                "k3s",
                "kubectl",
                "-n",
                namespace,
                "get",
                "deployment/controlled-proof-wgcf-worker",
                "--ignore-not-found=true",
                "-o",
                "name",
            ]
            cwd = self.workspace_root / "platform-engineering"
        else:
            raise ControlledProofError(f"unsupported baseline surface: {surface_id}")

        try:
            completed = subprocess.run(
                resolve_controlled_command(command, environment=env),
                cwd=cwd,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ControlledProofError(
                f"baseline probe could not run for {surface_id}"
            ) from exc
        resource_state = "present" if completed.stdout.strip() else "absent"
        observation_stdout = f"scoped runtime resource: {resource_state}"
        if surface_id == "temporal-runtime":
            state_root = controlled_runtime_state_root(
                self.workspace_root, self.operator_id
            )
            local_state = "present" if state_root.exists() else "absent"
            observation_stdout += f"; operator state: {local_state}"
        observation = {
            "schema_version": 1,
            "surface_id": surface_id,
            "probe_id": PROBE_IDS[surface_id],
            "exit_code": completed.returncode,
            "stdout": observation_stdout,
            "stderr": " ".join(completed.stderr.split()),
        }
        encoded_output = (
            observation["stdout"].encode("utf-8")
            + observation["stderr"].encode("utf-8")
        )
        if len(encoded_output) > MAX_ARTIFACT_BYTES:
            raise ControlledProofError(
                f"baseline probe output exceeds its boundary for {surface_id}"
            )
        state = _surface_state(surface_id, observation)
        return state, observation


def _surface_state(surface_id: str, observation: dict[str, Any]) -> str:
    if observation.get("exit_code") != 0:
        raise ControlledProofError(f"baseline probe failed for {surface_id}")
    stdout = str(observation.get("stdout") or "")
    lines = dict(
        segment.strip().split(":", 1)
        for segment in stdout.split(";")
        if ":" in segment
    )
    if lines.get("scoped runtime resource", "").strip() != "absent":
        raise ControlledProofError(
            f"{surface_id} baseline requires an absent scoped runtime resource"
        )
    if surface_id == "temporal-runtime" and lines.get("operator state", "").strip() != "absent":
        raise ControlledProofError(
            "Temporal baseline requires absent operator-local runtime state"
        )
    return "not-installed"


def capture_baseline(
    *,
    baseline_id: str,
    operator_id: str,
    output_path: Path,
    evidence_root: Path,
    source_resolver: SourceResolver,
    probe: BaselineProbe,
    contracts: ContractSet,
    captured_at: str | None = None,
) -> tuple[dict[str, Any], str]:
    captured_timestamp = captured_at or now_utc()
    if output_path.expanduser().exists() or output_path.expanduser().is_symlink():
        raise ControlledProofError(f"refusing to overwrite artifact: {output_path}")
    if evidence_root.expanduser().exists() or evidence_root.expanduser().is_symlink():
        raise ControlledProofError(
            f"baseline evidence root must not already exist: {evidence_root}"
        )
    execution_source_revisions = []
    for repo in EXECUTION_SOURCE_REPOS:
        revision, dirty = source_resolver.revision(repo)
        if dirty:
            raise ControlledProofError(f"baseline source repo is dirty: {repo}")
        execution_source_revisions.append(
            {"repo": repo, "commit": revision, "dirty": False}
        )

    captured_observations = []
    for surface_id in SURFACE_ORDER:
        state, observation = probe.capture(surface_id)
        expected_state = EXPECTED_BASELINE_STATES[surface_id]
        if state != expected_state:
            raise ControlledProofError(
                f"baseline surface {surface_id} must be {expected_state}, got {state}"
            )
        captured_observations.append(
            (surface_id, state, observation, canonical_digest(observation))
        )

    evidence_root = evidence_root.resolve()
    evidence_root.mkdir(parents=True, exist_ok=False, mode=0o700)
    observations = []
    for surface_id, state, observation, observation_digest in captured_observations:
        evidence_payload = {**observation, "captured_at": captured_timestamp}
        evidence_path = evidence_root / f"{surface_id}.json"
        evidence_digest = write_json_atomic(evidence_path, evidence_payload)
        observations.append(
            {
                "surface_id": surface_id,
                "state": state,
                "probe_id": PROBE_IDS[surface_id],
                "evidence_ref": f"artifact://controlled-proof/baselines/{baseline_id.rsplit('/', 1)[-1]}/{surface_id}",
                "evidence_digest": evidence_digest,
                "observation_digest": observation_digest,
            }
        )

    baseline = {
        "schema_version": 2,
        "baseline_id": baseline_id,
        "profile": {
            "profile_id": "temporal",
            "profile_lifecycle": "build-admitted",
            "environment": "dev-integration",
        },
        "operator_id": require_identifier(operator_id, "operator_id"),
        "captured_at": captured_timestamp,
        "execution_source_revisions": execution_source_revisions,
        "surface_observations": observations,
        "restore_scope": list(SURFACE_ORDER),
    }
    validate_schema(baseline, contracts.baseline, "baseline")
    validate_baseline_semantics(baseline)
    return baseline, write_json_atomic(output_path, baseline)


def validate_baseline_semantics(
    baseline: dict[str, Any], *, evidence_root: Path | None = None
) -> None:
    repos = [item["repo"] for item in baseline["execution_source_revisions"]]
    if repos != list(EXECUTION_SOURCE_REPOS):
        raise ControlledProofError(
            "baseline execution source revisions do not preserve the exact owner order"
        )
    surfaces = [item["surface_id"] for item in baseline["surface_observations"]]
    if surfaces != list(SURFACE_ORDER):
        raise ControlledProofError("baseline observations do not preserve the exact surface order")
    if any(item["dirty"] for item in baseline["execution_source_revisions"]):
        raise ControlledProofError("baseline cannot bind dirty source")
    states = {item["surface_id"]: item["state"] for item in baseline["surface_observations"]}
    if states != EXPECTED_BASELINE_STATES:
        raise ControlledProofError(
            "baseline must capture the exact absent and source-disabled commissioning posture"
        )
    if evidence_root is not None:
        _validate_baseline_evidence(baseline, evidence_root)


def _validate_baseline_evidence(baseline: dict[str, Any], evidence_root: Path) -> None:
    root = evidence_root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ControlledProofError("baseline evidence root is not a directory")
    baseline_key = baseline["baseline_id"].rsplit("/", 1)[-1]
    for item in baseline["surface_observations"]:
        surface_id = item["surface_id"]
        expected_ref = (
            f"artifact://controlled-proof/baselines/{baseline_key}/{surface_id}"
        )
        if item["evidence_ref"] != expected_ref:
            raise ControlledProofError(
                f"baseline evidence reference does not match {surface_id}"
            )
        evidence = read_bounded_json(
            root / f"{surface_id}.json",
            expected_digest=item["evidence_digest"],
        )
        captured_at = evidence.pop("captured_at", None)
        if captured_at != baseline["captured_at"]:
            raise ControlledProofError(
                f"baseline evidence timestamp does not match {surface_id}"
            )
        expected_observation = {
            "schema_version": 1,
            "surface_id": surface_id,
            "probe_id": item["probe_id"],
            "exit_code": evidence.get("exit_code"),
            "stdout": evidence.get("stdout"),
            "stderr": evidence.get("stderr"),
        }
        if evidence != expected_observation:
            raise ControlledProofError(
                f"baseline evidence fields do not match {surface_id}"
            )
        if evidence["exit_code"] != 0:
            raise ControlledProofError(f"baseline probe failed for {surface_id}")
        if canonical_digest(evidence) != item["observation_digest"]:
            raise ControlledProofError(
                f"baseline observation digest does not match {surface_id}"
            )


def assemble_claims(
    *,
    authorization_id: str,
    commissioning_session_id: str,
    review_packet_ref: str,
    issued_at: str,
    expires_at: str,
    baseline: dict[str, Any],
    baseline_digest: str,
    baseline_evidence_root: Path,
    owner_image_digests: dict[str, str],
    source_resolver: SourceResolver,
    contracts: ContractSet,
) -> tuple[dict[str, Any], str]:
    """Build the closed claims set from reviewed source and fixed proof grammar."""

    validate_schema(baseline, contracts.baseline, "baseline")
    validate_baseline_semantics(baseline, evidence_root=baseline_evidence_root)
    normalize_digest(baseline_digest, "baseline digest")
    require_identifier(commissioning_session_id, "commissioning_session_id")
    if not review_packet_ref.startswith("artifact://review-packets/"):
        raise ControlledProofError(
            "claims require a finalized Review Packet artifact reference"
        )

    execution_source_revisions: list[dict[str, str]] = []
    for repo in EXECUTION_SOURCE_REPOS:
        revision, dirty = source_resolver.revision(repo)
        if dirty:
            raise ControlledProofError(f"claims source repo is dirty: {repo}")
        execution_source_revisions.append({"repo": repo, "commit": revision})

    if set(owner_image_digests) != OWNER_RUNTIME_IMAGES:
        raise ControlledProofError(
            "claims require the exact OOS API, OOS worker, and WGCF worker image set"
        )
    runtime_images = _temporal_runtime_images()
    runtime_images.extend(
        {
            "image_ref": image_ref,
            "digest": normalize_digest(
                owner_image_digests[image_ref], f"{image_ref} image digest"
            ),
        }
        for image_ref in sorted(OWNER_RUNTIME_IMAGES)
    )

    reviewed_source = {
        "owner_repo": "platform-engineering",
        "implementation_ref": REVIEW_WORK_ITEM_REF,
        "source_revision": next(
            item["commit"]
            for item in execution_source_revisions
            if item["repo"] == "platform-engineering"
        ),
        "review_packet_ref": review_packet_ref,
    }
    scenarios = [
        {
            "scenario_id": scenario_id,
            "scenario_execution_id": (
                f"{commissioning_session_id}:{index:02d}:{scenario_id}"
            ),
            "required_receipt_owners": list(
                REQUIRED_SCENARIO_OWNERS[scenario_id]
            ),
        }
        for index, scenario_id in enumerate(SCENARIO_ORDER, start=1)
    ]
    claims = {
        "schema_version": 4,
        "authorization_id": authorization_id,
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
            "runtime_artifacts": _platform_runtime_artifacts(),
            "runtime_images": runtime_images,
            "target_namespaces": [_controlled_namespace(baseline["operator_id"])],
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
            "commissioning_session_id": commissioning_session_id,
            "consumption_mode": "atomic-single-use",
            "consume_before_first_mutation": True,
            "duplicate_consumption_denied": True,
            "scenario_executions": scenarios,
        },
        "permit_issuer": copy.deepcopy(reviewed_source),
        "executor": copy.deepcopy(reviewed_source),
        "window": {"issued_at": issued_at, "expires_at": expires_at},
        "evidence": {
            "owner_repo": "platform-engineering",
            "verification_pack_ref": (
                "artifact://controlled-proof/verification/"
                f"{commissioning_session_id}"
            ),
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
    return prepare_claims(claims, contracts=contracts)


def claims_projection(authorization: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in authorization.items() if key != "approvals"}


def _placeholder_approvals() -> dict[str, Any]:
    return {
        "issued_by": "platform-engineering",
        "canonicalization": "rfc8785",
        "canonical_claims_projection": "all-authorization-fields-except-approvals",
        "canonical_claims_digest": PLACEHOLDER_DIGEST,
        "operator_approval_ref": "artifact://controlled-proof/approvals/operator-placeholder",
        "operator_approval_digest": PLACEHOLDER_DIGEST,
        "security_authorization_source_repo": SECURITY_AUTHORIZATION_SOURCE_REPO,
        "security_authorization_source_revision": "0" * 40,
        "security_authorization_source_path": (
            "records/controlled-proof-authorizations/security-placeholder.json"
        ),
        "security_authorization_ref": "artifact://controlled-proof/approvals/security-placeholder",
        "security_authorization_digest": PLACEHOLDER_DIGEST,
    }


def prepare_claims(
    claims: dict[str, Any],
    *,
    contracts: ContractSet,
) -> tuple[dict[str, Any], str]:
    if "approvals" in claims:
        raise ControlledProofError("claims input must exclude the approval envelope")
    candidate = {**copy.deepcopy(claims), "approvals": _placeholder_approvals()}
    validate_schema(candidate, contracts.authorization, "authorization claims")
    validate_authorization_semantics(candidate, allow_placeholder_approvals=True)
    digest = canonical_digest(claims)
    return copy.deepcopy(claims), digest


def issue_permit(
    *,
    claims: dict[str, Any],
    operator_approval_path: Path,
    security_approval_path: Path,
    baseline_path: Path,
    baseline_evidence_root: Path,
    source_resolver: SourceResolver,
    contracts: ContractSet,
    runtime_image_validator: RuntimeImageValidator,
    issued_at: datetime | None = None,
) -> dict[str, Any]:
    claims, claims_digest = prepare_claims(claims, contracts=contracts)
    operator, operator_digest = read_bounded_json_with_digest(operator_approval_path)
    security, security_digest = read_bounded_json_with_digest(security_approval_path)
    validate_approval(
        operator,
        "operator-approval",
        claims,
        claims_digest,
        contracts,
        source_resolver=source_resolver,
    )
    security_source_binding = validate_approval(
        security,
        "security-authorization",
        claims,
        claims_digest,
        contracts,
        source_resolver=source_resolver,
    )
    if security_source_binding is None:
        raise ControlledProofError(
            "security authorization did not produce a source binding"
        )
    authorization = {
        **claims,
        "approvals": {
            "issued_by": "platform-engineering",
            "canonicalization": "rfc8785",
            "canonical_claims_projection": "all-authorization-fields-except-approvals",
            "canonical_claims_digest": claims_digest,
            "operator_approval_ref": operator["approval_id"],
            "operator_approval_digest": operator_digest,
            **security_source_binding,
            "security_authorization_ref": security["approval_id"],
            "security_authorization_digest": security_digest,
        },
    }
    validate_authorization(
        authorization,
        contracts=contracts,
        baseline_path=baseline_path,
        baseline_evidence_root=baseline_evidence_root,
        source_resolver=source_resolver,
        operator_approval_path=operator_approval_path,
        security_approval_path=security_approval_path,
        at_time=issued_at,
    )
    runtime_image_validator(
        copy.deepcopy(authorization["scope"]["runtime_images"]),
        runtime_platform(),
    )
    return authorization


def validate_approval(
    approval: dict[str, Any],
    expected_role: str,
    claims: dict[str, Any],
    claims_digest: str,
    contracts: ContractSet,
    *,
    source_resolver: SourceResolver,
    security_source_binding: dict[str, Any] | None = None,
    allow_source_checkout_drift: bool = False,
) -> dict[str, str] | None:
    validate_schema(approval, contracts.approval, f"{expected_role} artifact")
    if approval["approval_role"] != expected_role:
        raise ControlledProofError(f"approval role mismatch: expected {expected_role}")
    if approval["authorization_id"] != claims["authorization_id"]:
        raise ControlledProofError(f"{expected_role} binds another authorization")
    if approval["canonical_claims_digest"] != claims_digest:
        raise ControlledProofError(f"{expected_role} binds another claims digest")
    approved_at = parse_timestamp(approval["approved_at"], f"{expected_role}.approved_at")
    issued_at = parse_timestamp(claims["window"]["issued_at"], "window.issued_at")
    expires_at = parse_timestamp(claims["window"]["expires_at"], "window.expires_at")
    if approved_at > issued_at:
        raise ControlledProofError(
            f"{expected_role} was recorded after the declared permit issue time"
        )
    if approved_at >= expires_at:
        raise ControlledProofError(f"{expected_role} was recorded after authorization expiry")
    if expected_role == "security-authorization":
        return _validate_security_approval_provenance(
            approval,
            source_resolver=source_resolver,
            source_binding=security_source_binding,
            allow_source_checkout_drift=allow_source_checkout_drift,
        )
    return None


def _validate_security_approval_provenance(
    approval: dict[str, Any],
    *,
    source_resolver: SourceResolver,
    source_binding: dict[str, Any] | None,
    allow_source_checkout_drift: bool,
) -> dict[str, str]:
    provenance = approval.get("source_provenance")
    if not isinstance(provenance, dict):
        raise ControlledProofError(
            "security authorization requires source-controlled provenance"
        )
    if provenance.get("owner_repo") != SECURITY_AUTHORIZATION_SOURCE_REPO:
        raise ControlledProofError(
            "security authorization provenance is not owned by Security Architecture"
        )
    source_path = _source_relative_path(provenance.get("source_path"))
    if source_binding is None:
        expected_revision, dirty = source_resolver.revision(
            SECURITY_AUTHORIZATION_SOURCE_REPO
        )
        if dirty:
            raise ControlledProofError(
                "security authorization source repo is dirty at permit issuance"
            )
    else:
        if (
            source_binding.get("security_authorization_source_repo")
            != SECURITY_AUTHORIZATION_SOURCE_REPO
        ):
            raise ControlledProofError(
                "security authorization source binding is not owned by Security Architecture"
            )
        expected_revision = source_binding.get(
            "security_authorization_source_revision"
        )
        bound_path = _source_relative_path(
            source_binding.get("security_authorization_source_path")
        )
        if bound_path != source_path:
            raise ControlledProofError(
                "security authorization source path does not match its approval artifact"
            )
    if (
        not isinstance(expected_revision, str)
        or REVISION_RE.fullmatch(expected_revision) is None
    ):
        raise ControlledProofError(
            "security authorization has no valid permit-bound source revision"
        )
    if not source_resolver.revision_is_ancestor_of(
        SECURITY_AUTHORIZATION_SOURCE_REPO,
        expected_revision,
        SECURITY_AUTHORIZATION_MERGED_REF,
    ):
        raise ControlledProofError(
            "security authorization source revision is not contained in merged "
            f"{SECURITY_AUTHORIZATION_MERGED_REF}"
        )
    source_artifact = decode_bounded_json(
        source_resolver.read_file(
            SECURITY_AUTHORIZATION_SOURCE_REPO,
            expected_revision,
            source_path,
            require_current_checkout=not allow_source_checkout_drift,
        ),
        label="source-controlled security authorization",
    )
    if source_artifact != approval:
        raise ControlledProofError(
            "security authorization does not match its source-controlled artifact"
        )
    return {
        "security_authorization_source_repo": SECURITY_AUTHORIZATION_SOURCE_REPO,
        "security_authorization_source_revision": expected_revision,
        "security_authorization_source_path": source_path,
    }


def validate_authorization(
    authorization: dict[str, Any],
    *,
    contracts: ContractSet,
    baseline_path: Path,
    baseline_evidence_root: Path,
    source_resolver: SourceResolver,
    operator_approval_path: Path,
    security_approval_path: Path,
    at_time: datetime | None = None,
    allow_terminal_cleanup: bool = False,
) -> None:
    validate_schema(authorization, contracts.authorization, "authorization")
    validate_authorization_semantics(authorization)
    claims = claims_projection(authorization)
    claims_digest = canonical_digest(claims)
    approvals = authorization["approvals"]
    if approvals["canonical_claims_digest"] != claims_digest:
        raise ControlledProofError("authorization canonical claims digest does not match")

    operator = read_bounded_json(
        operator_approval_path,
        expected_digest=approvals["operator_approval_digest"],
    )
    security = read_bounded_json(
        security_approval_path,
        expected_digest=approvals["security_authorization_digest"],
    )
    validate_approval(
        operator,
        "operator-approval",
        claims,
        claims_digest,
        contracts,
        source_resolver=source_resolver,
        allow_source_checkout_drift=allow_terminal_cleanup,
    )
    validate_approval(
        security,
        "security-authorization",
        claims,
        claims_digest,
        contracts,
        source_resolver=source_resolver,
        security_source_binding=approvals,
        allow_source_checkout_drift=allow_terminal_cleanup,
    )
    if operator["approval_id"] != approvals["operator_approval_ref"]:
        raise ControlledProofError("operator approval reference does not match its artifact")
    if security["approval_id"] != approvals["security_authorization_ref"]:
        raise ControlledProofError("security authorization reference does not match its artifact")

    baseline = read_bounded_json(
        baseline_path,
        expected_digest=authorization["baseline_and_restore"]["baseline_snapshot_digest"],
    )
    validate_schema(baseline, contracts.baseline, "baseline")
    validate_baseline_semantics(baseline, evidence_root=baseline_evidence_root)
    if baseline["baseline_id"] != authorization["baseline_and_restore"]["baseline_snapshot_ref"]:
        raise ControlledProofError("authorization baseline reference does not match its artifact")

    expected_namespace = _controlled_namespace(baseline["operator_id"])
    if authorization["scope"]["target_namespaces"] != [expected_namespace]:
        raise ControlledProofError(
            "authorization namespace does not match the baseline operator scope"
        )

    expected_sources = {
        item["repo"]: item["commit"]
        for item in authorization["scope"]["execution_source_revisions"]
    }
    baseline_sources = {
        item["repo"]: item["commit"]
        for item in baseline["execution_source_revisions"]
    }
    for repo in EXECUTION_SOURCE_REPOS:
        if baseline_sources.get(repo) != expected_sources.get(repo):
            raise ControlledProofError(
                f"baseline source revision does not match authorization: {repo}"
            )
        if not allow_terminal_cleanup:
            current_revision, dirty = source_resolver.revision(repo)
            if dirty:
                raise ControlledProofError(f"authorization source repo is dirty: {repo}")
            if expected_sources.get(repo) != current_revision:
                raise ControlledProofError(f"authorization source revision drifted: {repo}")

    permit_revision = authorization["permit_issuer"]["source_revision"]
    executor_revision = authorization["executor"]["source_revision"]
    if permit_revision != expected_sources["platform-engineering"]:
        raise ControlledProofError("permit issuer does not bind the Platform source revision")
    if executor_revision != expected_sources["platform-engineering"]:
        raise ControlledProofError("executor does not bind the Platform source revision")

    validate_runtime_bindings(authorization)

    current = (at_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
    issued_at = parse_timestamp(authorization["window"]["issued_at"], "window.issued_at")
    expires_at = parse_timestamp(authorization["window"]["expires_at"], "window.expires_at")
    baseline_captured_at = parse_timestamp(
        baseline["captured_at"], "baseline.captured_at"
    )
    approval_times = {
        "operator approval": parse_timestamp(
            operator["approved_at"], "operator approval approved_at"
        ),
        "security authorization": parse_timestamp(
            security["approved_at"], "security authorization approved_at"
        ),
    }
    if baseline_captured_at > issued_at:
        raise ControlledProofError("authorization was issued before baseline capture")
    for label, approved_at in approval_times.items():
        if approved_at < baseline_captured_at:
            raise ControlledProofError(f"{label} predates the immutable baseline")
        if approved_at > current:
            raise ControlledProofError(f"{label} is future-dated")
    if issued_at >= expires_at:
        raise ControlledProofError("authorization issue time does not precede expiry")
    if current < issued_at or (current >= expires_at and not allow_terminal_cleanup):
        raise ControlledProofError("authorization is not currently valid")


def validate_authorization_semantics(
    authorization: dict[str, Any], *, allow_placeholder_approvals: bool = False
) -> None:
    issued_at = parse_timestamp(authorization["window"]["issued_at"], "window.issued_at")
    expires_at = parse_timestamp(
        authorization["window"]["expires_at"], "window.expires_at"
    )
    if issued_at >= expires_at:
        raise ControlledProofError("authorization issue time does not precede expiry")
    if authorization["target"] != {
        "profile_id": "temporal",
        "profile_lifecycle": "build-admitted",
        "environment": "dev-integration",
    }:
        raise ControlledProofError("authorization target is not the Temporal build-admitted profile")
    definitions = authorization["scope"]["allowed_definitions"]
    if definitions != [{"definition_id": "validation-readiness-run", "definition_version": 1}]:
        raise ControlledProofError("authorization must bind only validation-readiness-run version 1")
    _require_unique_key(
        authorization["scope"]["execution_source_revisions"],
        "repo",
        "execution source revision",
    )
    _require_unique_key(authorization["scope"]["runtime_artifacts"], "artifact_id", "runtime artifact")
    _require_unique_key(authorization["scope"]["runtime_images"], "image_ref", "runtime image")
    _require_unique_key(
        authorization["scope"]["runtime_identities"],
        "role",
        "runtime identity",
    )
    _require_unique_key(
        authorization["scope"]["task_queues"],
        "owner_repo",
        "task queue",
    )
    if set(authorization["scope"]["permitted_actions"]) != set(PERMITTED_ACTIONS):
        raise ControlledProofError("authorization permitted actions do not match the reviewed executor")
    source_repos = [
        item["repo"]
        for item in authorization["scope"]["execution_source_revisions"]
    ]
    if source_repos != list(EXECUTION_SOURCE_REPOS):
        raise ControlledProofError(
            "authorization execution source revisions do not preserve the exact reviewed owner order"
        )
    execution_source_revisions = {
        item["repo"]: item["commit"]
        for item in authorization["scope"]["execution_source_revisions"]
    }
    for repo, reviewed_revision in reviewed_contract_source_revisions().items():
        if execution_source_revisions.get(repo) != reviewed_revision:
            raise ControlledProofError(
                f"authorization source revision is outside the reviewed contract set: {repo}"
            )
    identities = {
        item["role"]: item["identity"]
        for item in authorization["scope"]["runtime_identities"]
    }
    if identities != EXPECTED_RUNTIME_IDENTITIES:
        raise ControlledProofError(
            "authorization runtime identities do not match the reviewed owner boundary"
        )
    task_queues = {
        item["owner_repo"]: item["queue_name"]
        for item in authorization["scope"]["task_queues"]
    }
    if task_queues != EXPECTED_TASK_QUEUES:
        raise ControlledProofError(
            "authorization task queues do not match the reviewed owner boundary"
        )
    namespaces = authorization["scope"]["target_namespaces"]
    if len(namespaces) != 1:
        raise ControlledProofError("authorization must bind exactly one Temporal namespace")
    scenarios = authorization["commissioning_session"]["scenario_executions"]
    if [scenario["scenario_id"] for scenario in scenarios] != list(SCENARIO_ORDER):
        raise ControlledProofError("authorization scenario order does not match the controlled proof")
    execution_ids = [scenario["scenario_execution_id"] for scenario in scenarios]
    if len(execution_ids) != len(set(execution_ids)):
        raise ControlledProofError("authorization scenario execution ids are not unique")
    session_id = authorization["commissioning_session"]["commissioning_session_id"]
    for index, scenario in enumerate(scenarios, start=1):
        expected_execution_id = f"{session_id}:{index:02d}:{scenario['scenario_id']}"
        if scenario["scenario_execution_id"] != expected_execution_id:
            raise ControlledProofError(
                f"{scenario['scenario_id']} execution id does not match its session"
            )
        expected_owners = list(REQUIRED_SCENARIO_OWNERS[scenario["scenario_id"]])
        if scenario["required_receipt_owners"] != expected_owners:
            raise ControlledProofError(
                f"{scenario['scenario_id']} receipt owners do not match the owner boundary"
            )
    expected_verification_ref = (
        f"artifact://controlled-proof/verification/{session_id}"
    )
    if authorization["evidence"]["verification_pack_ref"] != expected_verification_ref:
        raise ControlledProofError(
            "authorization verification pack does not match its session"
        )
    if set(authorization["stop_conditions"]) != set(REQUIRED_STOP_CONDITIONS):
        raise ControlledProofError("authorization stop conditions do not match the reviewed boundary")
    cleanup = authorization["baseline_and_restore"]["terminal_cleanup_authority"]
    if cleanup["permitted_actions"] != [
        "remove-scoped-runtime",
        "restore-exact-baseline",
        "record-restore-evidence",
        "record-governed-exception",
    ]:
        raise ControlledProofError("terminal cleanup actions do not match the fixed cleanup path")
    if not allow_placeholder_approvals and authorization["approvals"]["issued_by"] != "platform-engineering":
        raise ControlledProofError("authorization was not issued by Platform")
    for source_role in ("permit_issuer", "executor"):
        binding = authorization[source_role]
        if binding["implementation_ref"] != REVIEW_WORK_ITEM_REF:
            raise ControlledProofError(
                f"authorization {source_role} does not bind Platform source review #825"
            )
        if not binding["review_packet_ref"].startswith(
            "artifact://review-packets/"
        ):
            raise ControlledProofError(
                f"authorization {source_role} does not bind a finalized Review Packet"
            )
    if (
        authorization["permit_issuer"]["review_packet_ref"]
        != authorization["executor"]["review_packet_ref"]
    ):
        raise ControlledProofError(
            "permit issuer and executor must bind the same #825 Review Packet"
        )


def validate_runtime_bindings(authorization: dict[str, Any]) -> None:
    expected_artifacts = {
        item["artifact_id"]: item["digest"]
        for item in _platform_runtime_artifacts()
    }
    actual_artifacts = {
        item["artifact_id"]: item["digest"]
        for item in authorization["scope"]["runtime_artifacts"]
    }
    if actual_artifacts != expected_artifacts:
        raise ControlledProofError(
            "authorization runtime artifacts do not match the reviewed Platform source"
        )

    expected_temporal_images = {
        item["image_ref"]: item["digest"] for item in _temporal_runtime_images()
    }
    actual_images = {
        item["image_ref"]: item["digest"]
        for item in authorization["scope"]["runtime_images"]
    }
    if set(actual_images) != set(expected_temporal_images) | OWNER_RUNTIME_IMAGES:
        raise ControlledProofError(
            "authorization runtime image set does not match the controlled proof"
        )
    for image_ref, digest in expected_temporal_images.items():
        if actual_images[image_ref] != digest:
            raise ControlledProofError(
                f"authorization image digest does not match the Temporal lock: {image_ref}"
            )
    for image_ref in OWNER_RUNTIME_IMAGES:
        normalize_digest(actual_images[image_ref], f"{image_ref} image digest")


def _platform_runtime_artifacts() -> list[dict[str, str]]:
    lock = _artifact_lock()
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
            "digest": sha256_file(PROFILE_ROOT / "runtime" / "boundary-contract.yaml"),
        },
        {
            "artifact_id": "platform:controlled-proof-contract-set",
            "digest": sha256_file(CONTRACT_ROOT / "source-manifest.yaml"),
        },
        {
            "artifact_id": "platform:temporal-chart",
            "digest": normalize_digest(
                f"sha256:{lock['chart']['sha256']}", "Temporal chart digest"
            ),
        },
    ]


def _temporal_runtime_images() -> list[dict[str, str]]:
    lock = _artifact_lock()
    return [
        {
            "image_ref": f"{entry['repository']}:{entry['tag']}",
            "digest": normalize_digest(
                entry["digest"], f"{image_name} image digest"
            ),
        }
        for image_name, entry in lock["images"].items()
    ]


def runtime_platform() -> dict[str, str]:
    lock = _artifact_lock()
    return copy.deepcopy(lock["runtime_platform"])


def _artifact_lock() -> dict[str, Any]:
    lock = yaml.safe_load(
        (PROFILE_ROOT / "runtime" / "artifact-lock.yaml").read_text(
            encoding="utf-8"
        )
    )
    if (
        not isinstance(lock, dict)
        or not isinstance(lock.get("chart"), dict)
        or not isinstance(lock.get("images"), dict)
        or not isinstance(lock.get("runtime_platform"), dict)
    ):
        raise ControlledProofError("Temporal artifact lock is invalid")
    chart = lock["chart"]
    images = lock["images"]
    platform = lock["runtime_platform"]
    if (
        not isinstance(chart.get("sha256"), str)
        or not images
        or platform.get("os") != "linux"
        or platform.get("architecture") != "amd64"
    ):
        raise ControlledProofError("Temporal artifact lock is incomplete")
    for image_name, entry in images.items():
        if (
            not isinstance(image_name, str)
            or not isinstance(entry, dict)
            or not all(
                isinstance(entry.get(field), str)
                for field in ("repository", "tag", "digest")
            )
        ):
            raise ControlledProofError("Temporal image lock entry is invalid")
    return lock


def _controlled_namespace(operator_id: str) -> str:
    return operator_scoped_dns_label(
        "governance",
        operator_id,
        max_length=TEMPORAL_NAMESPACE_MAX_LENGTH,
    )


def controlled_runtime_state_root(workspace_root: Path, operator_id: str) -> Path:
    return (
        workspace_root.expanduser().resolve()
        / "platform-engineering"
        / ".dev-integration"
        / "temporal"
        / operator_scope_id(operator_id)
    )


def _require_unique_key(items: list[dict[str, Any]], key: str, label: str) -> None:
    values = [item[key] for item in items]
    if len(values) != len(set(values)):
        raise ControlledProofError(f"authorization contains duplicate {label} bindings")


def consume_authorization(
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    executor_source_revision: str,
    consumption_root: Path,
    contracts: ContractSet,
    consumed_at: str | None = None,
) -> tuple[dict[str, Any], Path, str]:
    normalize_digest(authorization_digest, "authorization digest")
    validate_schema(authorization, contracts.authorization, "authorization")
    validate_authorization_semantics(authorization)
    if REVISION_RE.fullmatch(executor_source_revision) is None:
        raise ControlledProofError("executor source revision is invalid")
    if executor_source_revision != authorization["executor"]["source_revision"]:
        raise ControlledProofError("consumption executor revision does not match authorization")
    consumed_timestamp = consumed_at or now_utc()
    consumed_time = parse_timestamp(consumed_timestamp, "consumed_at")
    issued_time = parse_timestamp(authorization["window"]["issued_at"], "issued_at")
    expires_time = parse_timestamp(authorization["window"]["expires_at"], "expires_at")
    if consumed_time < issued_time or consumed_time >= expires_time:
        raise ControlledProofError("authorization cannot be consumed outside its validity window")
    authorization_key = authorization_storage_key(authorization["authorization_id"])
    receipt_path = consumption_receipt_path(
        authorization["authorization_id"], consumption_root
    )
    receipt = {
        "schema_version": 1,
        "receipt_id": f"platform-controlled-proof://consumptions/{authorization_key}",
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "canonical_claims_digest": authorization["approvals"]["canonical_claims_digest"],
        "commissioning_session_id": authorization["commissioning_session"]["commissioning_session_id"],
        "executor_source_revision": executor_source_revision,
        "consumed_at": consumed_timestamp,
    }
    validate_schema(receipt, contracts.consumption, "consumption receipt")
    receipt_digest = create_json_exclusive(receipt_path, receipt)
    return receipt, receipt_path, receipt_digest


def authorization_storage_key(authorization_id: str) -> str:
    if (
        not isinstance(authorization_id, str)
        or "://" not in authorization_id
        or any(character.isspace() for character in authorization_id)
    ):
        raise ControlledProofError("authorization_id is not a valid URI")
    return hashlib.sha256(authorization_id.encode("utf-8")).hexdigest()


def consumption_receipt_path(authorization_id: str, consumption_root: Path) -> Path:
    return (
        consumption_root.expanduser().resolve()
        / f"{authorization_storage_key(authorization_id)}.json"
    )


def execution_scope_lease_ref(operator_scope: str) -> str:
    scope = require_identifier(operator_scope, "operator_scope")
    scope_key = hashlib.sha256(scope.encode("utf-8")).hexdigest()
    return f"platform-controlled-proof://scope-leases/{scope_key}"


def execution_scope_lease_path(operator_scope: str, lease_root: Path) -> Path:
    lease_key = execution_scope_lease_ref(operator_scope).rsplit("/", 1)[-1]
    return lease_root.expanduser().resolve() / f"{lease_key}.json"


def validate_execution_scope_lease(
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    consumption_receipt: dict[str, Any],
    consumption_receipt_digest: str,
    execution_claim: dict[str, Any],
    output_root: Path,
    operator_scope: str,
    lease_root: Path,
) -> tuple[dict[str, Any], Path, str]:
    """Validate the active lease that owns one operator-scoped runtime."""

    lease_path = execution_scope_lease_path(operator_scope, lease_root)
    lease, lease_digest = read_bounded_json_with_digest(
        lease_path,
        expected_digest=execution_claim["scope_lease_digest"],
    )
    require_exact_keys(
        lease,
        {
            "schema_version",
            "lease_id",
            "operator_scope",
            "authorization_id",
            "authorization_digest",
            "consumption_receipt_ref",
            "consumption_receipt_digest",
            "commissioning_session_id",
            "executor_source_revision",
            "output_root_digest",
            "acquired_at",
        },
        "execution scope lease",
    )
    if lease["schema_version"] != 1:
        raise ControlledProofError("execution scope lease schema version is unsupported")
    expected = {
        "lease_id": execution_scope_lease_ref(operator_scope),
        "operator_scope": operator_scope,
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
        "acquired_at": execution_claim["claimed_at"],
    }
    mismatched = [
        field for field, expected_value in expected.items()
        if lease.get(field) != expected_value
    ]
    if mismatched:
        raise ControlledProofError(
            "execution scope lease does not match the controlled session: "
            + ", ".join(mismatched)
        )
    if execution_claim["scope_lease_ref"] != lease["lease_id"]:
        raise ControlledProofError("execution claim scope lease reference does not match")
    normalize_digest(lease_digest, "execution scope lease digest")
    return lease, lease_path, lease_digest


def release_execution_scope_lease(
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    consumption_receipt: dict[str, Any],
    consumption_receipt_digest: str,
    execution_claim: dict[str, Any],
    output_root: Path,
    operator_scope: str,
    lease_root: Path,
) -> None:
    """Release only the lease owned by the successfully restored session."""

    _lease, lease_path, _lease_digest = validate_execution_scope_lease(
        authorization=authorization,
        authorization_digest=authorization_digest,
        consumption_receipt=consumption_receipt,
        consumption_receipt_digest=consumption_receipt_digest,
        execution_claim=execution_claim,
        output_root=output_root,
        operator_scope=operator_scope,
        lease_root=lease_root,
    )
    try:
        lease_path.unlink()
    except OSError as exc:
        raise ControlledProofError("execution scope lease could not be released") from exc
    directory_fd = os.open(lease_path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def claim_execution(
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    consumption_receipt: dict[str, Any],
    consumption_receipt_digest: str,
    output_root: Path,
    operator_id: str,
    execution_root: Path,
    contracts: ContractSet,
    claimed_at: str | None = None,
) -> tuple[dict[str, Any], Path, str]:
    normalize_digest(authorization_digest, "authorization digest")
    normalize_digest(consumption_receipt_digest, "consumption receipt digest")
    validate_schema(authorization, contracts.authorization, "authorization")
    validate_authorization_semantics(authorization)
    validate_schema(consumption_receipt, contracts.consumption, "consumption receipt")
    expected_receipt = {
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "canonical_claims_digest": authorization["approvals"][
            "canonical_claims_digest"
        ],
        "commissioning_session_id": authorization["commissioning_session"][
            "commissioning_session_id"
        ],
        "executor_source_revision": authorization["executor"]["source_revision"],
    }
    mismatched = [
        field
        for field, expected in expected_receipt.items()
        if consumption_receipt.get(field) != expected
    ]
    if mismatched:
        raise ControlledProofError(
            "execution claim receipt binding mismatch: " + ", ".join(mismatched)
        )

    claimed_timestamp = claimed_at or now_utc()
    claimed_time = parse_timestamp(claimed_timestamp, "execution claimed_at")
    consumed_time = parse_timestamp(
        consumption_receipt["consumed_at"], "consumption consumed_at"
    )
    expires_time = parse_timestamp(
        authorization["window"]["expires_at"], "authorization expires_at"
    )
    if (
        claimed_time < consumed_time
        or (
            expires_time - claimed_time
        ).total_seconds() <= TERMINAL_CLEANUP_START_RESERVE_SECONDS
    ):
        raise ControlledProofError(
            "execution must follow permit consumption and preserve the exact-restore "
            "start reserve"
        )

    operator_id = require_identifier(operator_id, "operator_id")
    operator_scope = operator_scope_id(operator_id)
    if authorization["scope"]["target_namespaces"] != [
        _controlled_namespace(operator_id)
    ]:
        raise ControlledProofError(
            "execution operator does not match the authorized runtime namespace"
        )
    authorization_key = authorization_storage_key(authorization["authorization_id"])
    execution_root = execution_root.expanduser().resolve()
    claim_path = execution_root / f"{authorization_key}.json"
    lease_root = execution_root.parent / "_controlled-proof-scope-leases"
    output_root_digest = sha256_bytes(
        str(output_root.expanduser().resolve()).encode("utf-8")
    )
    lease_path = execution_scope_lease_path(operator_scope, lease_root)
    expected_claim_fields = {
        "schema_version": 2,
        "execution_claim_id": (
            f"platform-controlled-proof://execution-claims/{authorization_key}"
        ),
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "consumption_receipt_ref": consumption_receipt["receipt_id"],
        "consumption_receipt_digest": consumption_receipt_digest,
        "commissioning_session_id": authorization["commissioning_session"][
            "commissioning_session_id"
        ],
        "executor_source_revision": authorization["executor"]["source_revision"],
        "output_root_digest": output_root_digest,
        "operator_scope": operator_scope,
        "scope_lease_ref": execution_scope_lease_ref(operator_scope),
    }

    def resume_existing_claim() -> tuple[dict[str, Any], Path, str]:
        existing_claim, existing_digest = read_bounded_json_with_digest(claim_path)
        require_exact_keys(
            existing_claim,
            {
                *expected_claim_fields,
                "scope_lease_digest",
                "claimed_at",
            },
            "execution claim",
        )
        mismatched_claim = [
            field
            for field, expected_value in expected_claim_fields.items()
            if existing_claim.get(field) != expected_value
        ]
        if mismatched_claim:
            raise ControlledProofError(
                "controlled proof execution was already claimed with different bindings: "
                + ", ".join(mismatched_claim)
            )
        existing_claimed_time = parse_timestamp(
            existing_claim["claimed_at"], "execution claimed_at"
        )
        if (
            existing_claimed_time < consumed_time
            or (
                expires_time - existing_claimed_time
            ).total_seconds() <= TERMINAL_CLEANUP_START_RESERVE_SECONDS
        ):
            raise ControlledProofError(
                "existing execution claim is outside permit authority"
            )
        normalize_digest(existing_claim["scope_lease_digest"], "scope lease digest")
        validate_execution_scope_lease(
            authorization=authorization,
            authorization_digest=authorization_digest,
            consumption_receipt=consumption_receipt,
            consumption_receipt_digest=consumption_receipt_digest,
            execution_claim=existing_claim,
            output_root=output_root,
            operator_scope=operator_scope,
            lease_root=lease_root,
        )
        return existing_claim, claim_path, existing_digest

    if claim_path.exists() or claim_path.is_symlink():
        return resume_existing_claim()

    lease = {
        "schema_version": 1,
        "lease_id": execution_scope_lease_ref(operator_scope),
        "operator_scope": operator_scope,
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "consumption_receipt_ref": consumption_receipt["receipt_id"],
        "consumption_receipt_digest": consumption_receipt_digest,
        "commissioning_session_id": authorization["commissioning_session"][
            "commissioning_session_id"
        ],
        "executor_source_revision": authorization["executor"]["source_revision"],
        "output_root_digest": output_root_digest,
        "acquired_at": claimed_timestamp,
    }
    try:
        lease_digest = create_json_exclusive(
            lease_path,
            lease,
            conflict_message=(
                "controlled proof operator scope is already leased: "
                f"{operator_scope}"
            ),
        )
    except ControlledProofError:
        if not lease_path.is_file() or lease_path.is_symlink():
            raise
        existing_lease, lease_digest = read_bounded_json_with_digest(lease_path)
        expected_resume = {key: value for key, value in lease.items() if key != "acquired_at"}
        actual_resume = {
            key: value for key, value in existing_lease.items() if key != "acquired_at"
        }
        if expected_resume != actual_resume or not isinstance(
            existing_lease.get("acquired_at"), str
        ):
            raise ControlledProofError(
                f"controlled proof operator scope is already leased: {operator_scope}"
            )
        claimed_timestamp = existing_lease["acquired_at"]
        lease = existing_lease
        claimed_time = parse_timestamp(claimed_timestamp, "execution scope acquired_at")
        if claimed_time < consumed_time or claimed_time >= expires_time:
            raise ControlledProofError(
                "existing execution scope lease is outside permit authority"
            )

    claim = {
        "schema_version": 2,
        "execution_claim_id": (
            f"platform-controlled-proof://execution-claims/{authorization_key}"
        ),
        "authorization_id": authorization["authorization_id"],
        "authorization_digest": authorization_digest,
        "consumption_receipt_ref": consumption_receipt["receipt_id"],
        "consumption_receipt_digest": consumption_receipt_digest,
        "commissioning_session_id": authorization["commissioning_session"][
            "commissioning_session_id"
        ],
        "executor_source_revision": authorization["executor"]["source_revision"],
        "output_root_digest": output_root_digest,
        "operator_scope": operator_scope,
        "scope_lease_ref": lease["lease_id"],
        "scope_lease_digest": lease_digest,
        "claimed_at": claimed_timestamp,
    }
    try:
        claim_digest = create_json_exclusive(
            claim_path,
            claim,
            conflict_message=(
                "controlled proof execution was already claimed for authorization "
                f"{authorization['authorization_id']}"
            ),
        )
    except ControlledProofError:
        if not claim_path.is_file() or claim_path.is_symlink():
            raise
        return resume_existing_claim()
    return claim, claim_path, claim_digest


def _run_checked(command: list[str]) -> str:
    environment = controlled_subprocess_environment()
    completed = subprocess.run(
        resolve_controlled_command(command, environment=environment),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise ControlledProofError(f"command failed: {' '.join(command)}: {detail}")
    return completed.stdout.strip()


def _run_checked_bytes(command: list[str]) -> bytes:
    environment = controlled_subprocess_environment()
    completed = subprocess.run(
        resolve_controlled_command(command, environment=environment),
        check=False,
        capture_output=True,
        env=environment,
        timeout=30,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout)[:4096].decode(
            "utf-8", errors="replace"
        )
        raise ControlledProofError(
            f"command failed: {' '.join(command)}: {detail.strip()}"
        )
    if len(completed.stdout) > MAX_ARTIFACT_BYTES:
        raise ControlledProofError("source artifact command exceeded its output boundary")
    return completed.stdout


def _source_relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ControlledProofError("source artifact path is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ControlledProofError("source artifact path is outside its repository")
    normalized = path.as_posix()
    if normalized != value or not normalized.endswith(".json"):
        raise ControlledProofError("source artifact path must be a normalized JSON path")
    return normalized
