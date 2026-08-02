from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import subprocess
from typing import Any, Protocol

import yaml

from .model import (
    MAX_ARTIFACT_BYTES,
    ControlledProofError,
    PERMITTED_ACTIONS,
    REQUIRED_SCENARIO_OWNERS,
    REQUIRED_STOP_CONDITIONS,
    REVISION_RE,
    SCENARIO_ORDER,
    TERMINAL_CLEANUP_START_RESERVE_SECONDS,
    canonical_digest,
    controlled_subprocess_environment,
    create_json_exclusive,
    decode_bounded_json,
    load_schema,
    normalize_digest,
    now_utc,
    operator_scoped_dns_label,
    parse_timestamp,
    read_bounded_json,
    read_bounded_json_with_digest,
    resolve_controlled_command,
    require_identifier,
    sha256_bytes,
    sha256_file,
    validate_schema,
    write_json_atomic,
)


PROFILE_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = Path(__file__).resolve().parent / "contracts"
WORKSPACE_REPOS = (
    "platform-engineering",
    "operator-orchestration-service",
    "workspace-governance",
    "workspace-governance-control-fabric",
    "security-architecture",
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
REVIEW_WORK_ITEM_REF = "openproject://work_packages/792"
EXPECTED_BASELINE_STATES = {
    "temporal-runtime": "not-installed",
    "oos-validation-readiness-worker": "source-ready-disabled",
    "wgcf-readiness-activity-worker": "source-ready-disabled",
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


class LocalBaselineProbe:
    """Read-only fixed probes for the three commissioning surfaces."""

    def __init__(self, workspace_root: Path, operator_id: str):
        self.workspace_root = workspace_root.resolve()
        self.operator_id = require_identifier(operator_id, "operator_id")

    def capture(self, surface_id: str) -> tuple[str, dict[str, Any]]:
        env = controlled_subprocess_environment()
        if surface_id == "temporal-runtime":
            command = [
                "bash",
                "-c",
                (
                    'source "$1"; '
                    'printf "runtime state: %s\\n" "$(runtime_state)"; '
                    'if [[ -e "$STATE_ROOT" ]]; then '
                    'printf "operator state: present\\n"; '
                    'else printf "operator state: absent\\n"; fi'
                ),
                "controlled-proof-baseline-probe",
                str(PROFILE_ROOT / "scripts" / "common.sh"),
            ]
            cwd = self.workspace_root / "platform-engineering"
            env.update(
                {
                    "DEVINT_PROFILE_ID": "temporal",
                    "DEVINT_OPERATOR": self.operator_id,
                    "DEVINT_PROFILE_LIFECYCLE": "build-admitted",
                    "DEVINT_KUBECONFIG": "/etc/rancher/k3s/k3s.yaml",
                    "DEVINT_KUBECTL": "k3s kubectl",
                }
            )
        elif surface_id == "oos-validation-readiness-worker":
            command = ["node", "src/orchestration-worker.js", "controlled-proof-status"]
            cwd = self.workspace_root / "operator-orchestration-service"
        elif surface_id == "wgcf-readiness-activity-worker":
            python = self.workspace_root / "workspace-governance-control-fabric" / ".venv" / "bin" / "python"
            command = [
                str(python if python.is_file() else Path("python3")),
                "-m",
                "wgcf_worker",
                "controlled-proof",
                "status",
                "--repo-root",
                ".",
                "--json",
            ]
            cwd = self.workspace_root / "workspace-governance-control-fabric"
            env["PYTHONPATH"] = "packages/control_fabric_core/src:apps/worker/src"
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
        observation = {
            "schema_version": 1,
            "surface_id": surface_id,
            "probe_id": PROBE_IDS[surface_id],
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
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
    if surface_id == "temporal-runtime":
        state = None
        operator_state = None
        for line in stdout.splitlines():
            if line.startswith("runtime state:"):
                state = line.split(":", 1)[1].strip()
            elif line.startswith("operator state:"):
                operator_state = line.split(":", 1)[1].strip()
        state = require_identifier(state, "Temporal runtime state")
        if operator_state != "absent":
            raise ControlledProofError(
                "Temporal baseline requires absent operator-local runtime state"
            )
        return state
    payload = decode_bounded_json(
        stdout.encode("utf-8"), label=f"{surface_id} baseline probe"
    )
    activation = payload.get("activation") or {}
    authorized = bool(activation.get("authorized")) if isinstance(activation, dict) else False
    if authorized:
        raise ControlledProofError(f"{surface_id} is unexpectedly authorized before issuance")
    return "source-ready-disabled" if payload.get("ready") else "source-incomplete-disabled"


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
    source_revisions = []
    for repo in WORKSPACE_REPOS:
        revision, dirty = source_resolver.revision(repo)
        if dirty:
            raise ControlledProofError(f"baseline source repo is dirty: {repo}")
        source_revisions.append({"repo": repo, "commit": revision, "dirty": False})

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
        "schema_version": 1,
        "baseline_id": baseline_id,
        "profile": {
            "profile_id": "temporal",
            "profile_lifecycle": "build-admitted",
            "environment": "dev-integration",
        },
        "operator_id": require_identifier(operator_id, "operator_id"),
        "captured_at": captured_timestamp,
        "source_revisions": source_revisions,
        "surface_observations": observations,
        "restore_scope": list(SURFACE_ORDER),
    }
    validate_schema(baseline, contracts.baseline, "baseline")
    validate_baseline_semantics(baseline)
    return baseline, write_json_atomic(output_path, baseline)


def validate_baseline_semantics(
    baseline: dict[str, Any], *, evidence_root: Path | None = None
) -> None:
    repos = [item["repo"] for item in baseline["source_revisions"]]
    if repos != list(WORKSPACE_REPOS):
        raise ControlledProofError("baseline source revisions do not preserve the exact owner order")
    surfaces = [item["surface_id"] for item in baseline["surface_observations"]]
    if surfaces != list(SURFACE_ORDER):
        raise ControlledProofError("baseline observations do not preserve the exact surface order")
    if any(item["dirty"] for item in baseline["source_revisions"]):
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

    source_revisions: list[dict[str, str]] = []
    for repo in WORKSPACE_REPOS:
        revision, dirty = source_resolver.revision(repo)
        if dirty:
            raise ControlledProofError(f"claims source repo is dirty: {repo}")
        source_revisions.append({"repo": repo, "commit": revision})

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
            for item in source_revisions
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
        "schema_version": 3,
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
            "source_revisions": source_revisions,
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
    issued_at: datetime | None = None,
) -> dict[str, Any]:
    claims, claims_digest = prepare_claims(claims, contracts=contracts)
    operator, operator_digest = read_bounded_json_with_digest(operator_approval_path)
    security, security_digest = read_bounded_json_with_digest(security_approval_path)
    validate_approval(operator, "operator-approval", claims, claims_digest, contracts)
    validate_approval(security, "security-authorization", claims, claims_digest, contracts)
    authorization = {
        **claims,
        "approvals": {
            "issued_by": "platform-engineering",
            "canonicalization": "rfc8785",
            "canonical_claims_projection": "all-authorization-fields-except-approvals",
            "canonical_claims_digest": claims_digest,
            "operator_approval_ref": operator["approval_id"],
            "operator_approval_digest": operator_digest,
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
    return authorization


def validate_approval(
    approval: dict[str, Any],
    expected_role: str,
    claims: dict[str, Any],
    claims_digest: str,
    contracts: ContractSet,
) -> None:
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
    validate_approval(operator, "operator-approval", claims, claims_digest, contracts)
    validate_approval(security, "security-authorization", claims, claims_digest, contracts)
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

    expected_sources = {item["repo"]: item["commit"] for item in authorization["scope"]["source_revisions"]}
    baseline_sources = {item["repo"]: item["commit"] for item in baseline["source_revisions"]}
    for repo in WORKSPACE_REPOS:
        current_revision, dirty = source_resolver.revision(repo)
        if dirty:
            raise ControlledProofError(f"authorization source repo is dirty: {repo}")
        if expected_sources.get(repo) != current_revision:
            raise ControlledProofError(f"authorization source revision drifted: {repo}")
        if baseline_sources.get(repo) != current_revision:
            raise ControlledProofError(f"baseline source revision drifted: {repo}")

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
    if current < issued_at or current >= expires_at:
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
    _require_unique_key(authorization["scope"]["source_revisions"], "repo", "source revision")
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
    source_repos = [item["repo"] for item in authorization["scope"]["source_revisions"]]
    if source_repos != list(WORKSPACE_REPOS):
        raise ControlledProofError(
            "authorization source revisions do not preserve the exact reviewed owner order"
        )
    source_revisions = {
        item["repo"]: item["commit"]
        for item in authorization["scope"]["source_revisions"]
    }
    for repo, reviewed_revision in reviewed_contract_source_revisions().items():
        if source_revisions.get(repo) != reviewed_revision:
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
                f"authorization {source_role} does not bind Platform source review #792"
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
            "permit issuer and executor must bind the same #792 Review Packet"
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
    ):
        raise ControlledProofError("Temporal artifact lock is invalid")
    chart = lock["chart"]
    images = lock["images"]
    if not isinstance(chart.get("sha256"), str) or not images:
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
    return operator_scoped_dns_label("governance", operator_id)


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


def claim_execution(
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    consumption_receipt: dict[str, Any],
    consumption_receipt_digest: str,
    output_root: Path,
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

    authorization_key = authorization_storage_key(authorization["authorization_id"])
    claim = {
        "schema_version": 1,
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
        "output_root_digest": sha256_bytes(
            str(output_root.expanduser().resolve()).encode("utf-8")
        ),
        "claimed_at": claimed_timestamp,
    }
    claim_path = execution_root.expanduser().resolve() / f"{authorization_key}.json"
    claim_digest = create_json_exclusive(
        claim_path,
        claim,
        conflict_message=(
            "controlled proof execution was already claimed for authorization "
            f"{authorization['authorization_id']}"
        ),
    )
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
