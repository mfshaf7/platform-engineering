#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import yaml


CHECK_STATUSES = {"pending", "passed", "failed", "blocked", "not_applicable"}
DECISIONS = {"remove", "workaround", "accept-risk", "defer"}
RESTORE_STATUSES = {"pending", "restored", "exception"}
PHASES = {"baseline", "activation", "verification", "restore", "general"}
PROFILE_ALIASES = {
    "full-platform-runtime-drill": "environment-complete-runtime-drill",
}
CONTROLLED_PROOF_CLEANUP_ACTIONS = [
    "remove-scoped-runtime",
    "restore-exact-baseline",
    "record-restore-evidence",
    "record-governed-exception",
]
CONTROLLED_PROOF_CLEANUP_TERMINATION_CONDITIONS = [
    "exact-baseline-restored",
    "governed-exception-recorded",
]
CONTROLLED_PROOF_SOURCE_ENABLEMENT = {
    "status": "source-reviewed",
    "implementationWorkItemRef": "openproject://work_packages/825",
    "snapshotAllowed": True,
    "requiredControls": [
        "capture-preauthorization-baseline-artifact",
        "validate-authorization-artifact-and-digest",
        "enforce-semantic-binding-uniqueness",
        "verify-rfc8785-claims-approval-bindings",
        "consume-authorization-atomically",
        "resume-only-exact-uncommitted-snapshot",
        "lease-operator-scope-before-execution-claim",
        "execute-runtime-actions-from-permit-bound-source",
        "verify-immutable-baseline-digest",
        "verify-runtime-scoped-restore",
        "emit-controlled-proof-result",
    ],
}
CONTROLLED_PROOF_RESULT_ARTIFACT = {
    "required": True,
    "artifactType": "controlled-runtime-proof-result",
    "schemaRef": "https://github.com/mfshaf7/workspace-governance/blob/main/contracts/schemas/controlled-runtime-proof-result.schema.json",
    "schemaVersion": 2,
}


def now_utc() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", value.lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "platform-drill"


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise SystemExit(f"{path} must contain a YAML object")
    return payload


def dump_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def dump_yaml_exclusive(path: Path, payload: dict[str, Any]) -> None:
    """Commit a YAML artifact without exposing a partial destination file."""

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    rendered = yaml.safe_dump(payload, sort_keys=False).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError as exc:
            raise SystemExit(f"snapshot commit already exists: {path}") from exc
        temporary_path.unlink()
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary_path.unlink(missing_ok=True)


@contextmanager
def controlled_snapshot_lock(repo_root: Path, authorization_ref: str):
    """Serialize one controlled snapshot transaction per authorization."""

    lock_key = hashlib.sha256(authorization_ref.encode("utf-8")).hexdigest()
    lock_root = (
        repo_root / ".platform-drills" / "_controlled-proof-snapshot-locks"
    ).resolve()
    lock_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = lock_root / f"{lock_key}.lock"
    try:
        descriptor = os.open(
            lock_path,
            os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except OSError as exc:
        raise SystemExit("controlled snapshot lock is unavailable") from exc
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SystemExit(
                "controlled snapshot is already in progress for this authorization"
            ) from exc
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def resolve_repo_path(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root / candidate).resolve()


def default_profile_path(repo_root: Path, profile: str) -> Path:
    profile = PROFILE_ALIASES.get(profile, profile)
    return repo_root / "environments" / "shared" / "runtime-drills" / f"{profile}.yaml"


def resolve_profile(repo_root: Path, profile: str, profile_path: str | None) -> Path:
    if profile_path:
        return Path(profile_path).expanduser().resolve()
    return default_profile_path(repo_root, profile)


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        capture_output=True,
    )
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    return stdout or stderr


def git_state(repo_root: Path) -> dict[str, Any]:
    branch = run(["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"])
    head_sha = run(["git", "-C", str(repo_root), "rev-parse", "HEAD"])
    dirty = bool(run(["git", "-C", str(repo_root), "status", "--short"], check=False))
    try:
        upstream = run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]
        )
    except subprocess.CalledProcessError:
        upstream = None
    return {
        "path": str(repo_root),
        "branch": branch,
        "head_sha": head_sha,
        "dirty": dirty,
        "upstream": upstream,
    }


def validate_contract(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    required_top_level = {
        "schema_version",
        "id",
        "title",
        "authorityType",
        "drillType",
        "targetEnvironment",
        "scope",
        "preconditions",
        "verificationPack",
        "exceptionHandling",
        "evidenceModel",
        "restoreMode",
        "restoreScope",
        "evidenceOwner",
    }
    missing = sorted(required_top_level - payload.keys())
    if missing:
        raise SystemExit(f"{path} is missing required keys: {', '.join(missing)}")

    authorization = payload.get("authorization")
    if payload.get("drillType") == "component-commissioning-proof":
        source_enablement = payload.get("sourceEnablement")
        required_source_enablement_fields = {
            "status",
            "implementationWorkItemRef",
            "snapshotAllowed",
            "requiredControls",
        }
        if not isinstance(source_enablement, dict):
            raise SystemExit(
                f"{path} component-commissioning-proof requires sourceEnablement"
            )
        source_enablement_fields = set(source_enablement)
        if source_enablement_fields != required_source_enablement_fields:
            raise SystemExit(
                f"{path} sourceEnablement keys must exactly be: "
                + ", ".join(sorted(required_source_enablement_fields))
            )
        if source_enablement.get("status") not in {"contract-only", "source-reviewed"}:
            raise SystemExit(
                f"{path} sourceEnablement.status must be contract-only or source-reviewed"
            )
        if not str(source_enablement.get("implementationWorkItemRef") or "").strip():
            raise SystemExit(
                f"{path} sourceEnablement.implementationWorkItemRef must not be empty"
            )
        if not isinstance(source_enablement.get("snapshotAllowed"), bool):
            raise SystemExit(f"{path} sourceEnablement.snapshotAllowed must be boolean")
        if source_enablement.get("status") == "contract-only" and source_enablement.get(
            "snapshotAllowed"
        ) is not False:
            raise SystemExit(
                f"{path} contract-only commissioning snapshots must remain disabled"
            )
        if source_enablement.get("status") == "source-reviewed" and source_enablement.get(
            "snapshotAllowed"
        ) is not True:
            raise SystemExit(
                f"{path} source-reviewed commissioning must explicitly enable its permit-consuming snapshot"
            )
        required_controls = source_enablement.get("requiredControls")
        if (
            not isinstance(required_controls, list)
            or not required_controls
            or any(
                not isinstance(control, str) or not control.strip()
                for control in required_controls
            )
            or len(required_controls) != len(set(required_controls))
        ):
            raise SystemExit(
                f"{path} sourceEnablement.requiredControls must be a unique non-empty list"
            )

        result_artifact = payload.get("resultArtifact")
        if not isinstance(result_artifact, dict):
            raise SystemExit(
                f"{path} component-commissioning-proof requires resultArtifact"
            )
        if set(result_artifact) != {
            "required",
            "artifactType",
            "schemaRef",
            "schemaVersion",
        } or (
            result_artifact.get("required") is not True
            or not str(result_artifact.get("artifactType") or "").strip()
            or not str(result_artifact.get("schemaRef") or "").strip()
            or not isinstance(result_artifact.get("schemaVersion"), int)
            or result_artifact.get("schemaVersion", 0) < 1
        ):
            raise SystemExit(
                f"{path} resultArtifact must bind a required versioned result schema"
            )

        is_temporal_commissioning_profile = (
            payload.get("id") == "temporal-component-commissioning-proof"
        )
        if is_temporal_commissioning_profile:
            if source_enablement != CONTROLLED_PROOF_SOURCE_ENABLEMENT:
                raise SystemExit(
                    f"{path} sourceEnablement must bind the reviewed Platform #825 control path"
                )
            if result_artifact != CONTROLLED_PROOF_RESULT_ARTIFACT:
                raise SystemExit(
                    f"{path} resultArtifact must bind the controlled-runtime-proof-result schema"
                )
        required_authorization_fields = {
            "required",
            "artifactType",
            "schemaRef",
            "policyRef",
            "securityReviewRef",
            "targetProfileId",
            "targetProfileLifecycle",
            "maxRuns",
            "permitIssuer",
            "executor",
            "terminalCleanupAuthority",
        }
        if not isinstance(authorization, dict):
            raise SystemExit(
                f"{path} component-commissioning-proof requires an authorization object"
            )
        missing_authorization = sorted(
            required_authorization_fields - authorization.keys()
        )
        if missing_authorization:
            raise SystemExit(
                f"{path} authorization is missing required keys: "
                + ", ".join(missing_authorization)
            )
        expected_authorization = {
            "required": True,
            "artifactType": "controlled-runtime-proof-authorization",
            "targetProfileLifecycle": "build-admitted",
            "maxRuns": 1,
        }
        for key, expected in expected_authorization.items():
            if authorization.get(key) != expected:
                raise SystemExit(f"{path} authorization.{key} must be {expected!r}")
        for key in ("schemaRef", "policyRef", "securityReviewRef", "targetProfileId"):
            if not str(authorization.get(key) or "").strip():
                raise SystemExit(f"{path} authorization.{key} must not be empty")
        for source_role in ("permitIssuer", "executor"):
            source_binding = authorization.get(source_role)
            if not isinstance(source_binding, dict):
                raise SystemExit(
                    f"{path} authorization.{source_role} must bind reviewed source"
                )
            if set(source_binding) != {
                "ownerRepo",
                "sourceReviewWorkItemRef",
                "mergedSourceRequiredBeforeSecurityAuthorization",
            } or (
                not str(source_binding.get("ownerRepo") or "").strip()
                or not str(source_binding.get("sourceReviewWorkItemRef") or "").strip()
                or source_binding.get("mergedSourceRequiredBeforeSecurityAuthorization")
                is not True
            ):
                raise SystemExit(
                    f"{path} authorization.{source_role} must bind owner, source review work, and pre-authorization merge"
                )
        if is_temporal_commissioning_profile:
            expected_reviewed_source = {
                "ownerRepo": "platform-engineering",
                "sourceReviewWorkItemRef": "openproject://work_packages/825",
                "mergedSourceRequiredBeforeSecurityAuthorization": True,
            }
            for source_role in ("permitIssuer", "executor"):
                if authorization.get(source_role) != expected_reviewed_source:
                    raise SystemExit(
                        f"{path} authorization.{source_role} must bind Platform source review #825"
                    )
            expected_security_authorization = {
                "ownerRepo": "security-architecture",
                "excludedFromExecutionSourceClaims": True,
                "approvalEnvelopeBinds": [
                    "source-revision",
                    "normalized-source-path",
                    "artifact-reference",
                    "artifact-digest",
                ],
            }
            if (
                authorization.get("securityAuthorization")
                != expected_security_authorization
            ):
                raise SystemExit(
                    f"{path} authorization.securityAuthorization must preserve the separate Security approval-provenance boundary"
                )
        terminal_cleanup = authorization.get("terminalCleanupAuthority") or {}
        expected_terminal_cleanup = {
            "mode": "exact-baseline-restore-only",
            "appliesTo": "already-started-run",
            "triggerScope": "any-triggered-stop-condition",
            "scopeBinding": "exact-captured-restore-scope",
            "newProofActionsDenied": True,
            "scopeExpansionDenied": True,
            "runtimeRetentionDenied": True,
            "permittedActions": CONTROLLED_PROOF_CLEANUP_ACTIONS,
            "terminationConditions": CONTROLLED_PROOF_CLEANUP_TERMINATION_CONDITIONS,
        }
        if terminal_cleanup != expected_terminal_cleanup:
            raise SystemExit(
                f"{path} authorization.terminalCleanupAuthority must preserve the fixed restore-only boundary for every stop condition"
            )

    scope = payload["scope"]
    if not isinstance(scope, dict):
        raise SystemExit(f"{path} field scope must be an object")
    source_repos = scope.get("sourceRepos") or []
    surfaces = scope.get("surfaces") or []
    if not isinstance(source_repos, list) or not source_repos:
        raise SystemExit(f"{path} scope.sourceRepos must be a non-empty list")
    if payload.get("id") == "temporal-component-commissioning-proof" and source_repos != [
        "platform-engineering",
        "operator-orchestration-service",
        "workspace-governance",
        "workspace-governance-control-fabric",
    ]:
        raise SystemExit(
            f"{path} scope.sourceRepos must contain only the ordered execution source set"
        )
    if not isinstance(surfaces, list) or not surfaces:
        raise SystemExit(f"{path} scope.surfaces must be a non-empty list")

    surface_ids: set[str] = set()
    for surface in surfaces:
        if not isinstance(surface, dict):
            raise SystemExit(f"{path} scope.surfaces entries must be objects")
        surface_id = str(surface.get("id") or "").strip()
        if not surface_id:
            raise SystemExit(f"{path} scope surface is missing id")
        if surface_id in surface_ids:
            raise SystemExit(f"{path} defines duplicate scope surface id {surface_id!r}")
        surface_ids.add(surface_id)
        for key in ("ownerRepo", "lane", "kind", "summary"):
            if not str(surface.get(key) or "").strip():
                raise SystemExit(f"{path} scope surface {surface_id!r} is missing {key}")

    checks = ((payload.get("verificationPack") or {}).get("checks")) or []
    if not isinstance(checks, list) or not checks:
        raise SystemExit(f"{path} verificationPack.checks must be a non-empty list")
    check_ids: set[str] = set()
    for check in checks:
        if not isinstance(check, dict):
            raise SystemExit(f"{path} verificationPack.checks entries must be objects")
        check_id = str(check.get("id") or "").strip()
        if not check_id:
            raise SystemExit(f"{path} verification check is missing id")
        if check_id in check_ids:
            raise SystemExit(f"{path} defines duplicate verification check id {check_id!r}")
        check_ids.add(check_id)
        accepted_statuses = check.get("acceptedStatuses") or []
        if not isinstance(accepted_statuses, list) or not accepted_statuses:
            raise SystemExit(f"{path} verification check {check_id!r} must declare acceptedStatuses")
        if not set(accepted_statuses).issubset(CHECK_STATUSES - {"pending"}):
            invalid = sorted(set(accepted_statuses) - (CHECK_STATUSES - {"pending"}))
            raise SystemExit(
                f"{path} verification check {check_id!r} uses invalid accepted statuses: {', '.join(invalid)}"
            )
        for key in ("category", "summary"):
            if not str(check.get(key) or "").strip():
                raise SystemExit(f"{path} verification check {check_id!r} is missing {key}")

    decisions = ((payload.get("exceptionHandling") or {}).get("decisions")) or []
    if not isinstance(decisions, list) or not decisions:
        raise SystemExit(f"{path} exceptionHandling.decisions must be a non-empty list")
    if set(decisions) != DECISIONS:
        raise SystemExit(
            f"{path} exceptionHandling.decisions must exactly be: {', '.join(sorted(DECISIONS))}"
        )

    evidence_model = payload.get("evidenceModel") or {}
    if not isinstance(evidence_model, dict):
        raise SystemExit(f"{path} evidenceModel must be an object")
    template_path = str(evidence_model.get("templatePath") or "").strip()
    if not template_path:
        raise SystemExit(f"{path} evidenceModel.templatePath is required")
    required_sections = evidence_model.get("requiredSections") or []
    if not isinstance(required_sections, list) or not required_sections:
        raise SystemExit(f"{path} evidenceModel.requiredSections must be a non-empty list")

    if payload.get("restoreMode") != "exact-baseline":
        raise SystemExit(f"{path} restoreMode must be 'exact-baseline'")

    restore_surfaces = ((payload.get("restoreScope") or {}).get("surfaces")) or []
    if not isinstance(restore_surfaces, list) or not restore_surfaces:
        raise SystemExit(f"{path} restoreScope.surfaces must be a non-empty list")
    restore_ids = {str(surface.get("id") or "").strip() for surface in restore_surfaces}
    if "" in restore_ids:
        raise SystemExit(f"{path} restoreScope contains a surface without id")
    missing_restore = surface_ids - restore_ids
    if missing_restore:
        raise SystemExit(
            f"{path} restoreScope is missing surfaces declared in scope: {', '.join(sorted(missing_restore))}"
        )
    return payload


def validate_evidence_template(path: Path, payload: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    required_top_level = {
        "schema_version",
        "id",
        "title",
        "run",
        "authoritativeArtifacts",
        "baselineAttestation",
        "activationSummary",
        "verificationResults",
        "exceptionRegister",
        "supplementalRecords",
        "restoreAttestation",
        "finalAssessment",
    }
    missing = sorted(required_top_level - payload.keys())
    if missing:
        raise SystemExit(f"{path} is missing required keys: {', '.join(missing)}")

    required_sections = set((contract.get("evidenceModel") or {}).get("requiredSections") or [])
    if not required_sections.issubset(payload.keys()):
        missing_sections = sorted(required_sections - set(payload.keys()))
        raise SystemExit(
            f"{path} is missing required evidence sections from contract: {', '.join(missing_sections)}"
        )

    artifacts = payload.get("authoritativeArtifacts") or {}
    expected_artifacts = {
        "runManifest": "run.yaml",
        "baselineSnapshot": "baseline.yaml",
        "verificationLedger": "verification.yaml",
        "restoreLedger": "restore.yaml",
        "evidencePack": "evidence.yaml",
    }
    if artifacts != expected_artifacts:
        raise SystemExit(
            f"{path} authoritativeArtifacts must exactly match the shared drill run files"
        )

    baseline = payload.get("baselineAttestation") or {}
    if str(baseline.get("captureStatus") or "").strip() != "pending":
        raise SystemExit(f"{path} baselineAttestation.captureStatus must start as pending")
    surface_attestations = baseline.get("surfaceAttestations") or []
    expected_surface_ids = {surface["id"] for surface in contract["scope"]["surfaces"]}
    actual_surface_ids = {str(surface.get("id") or "").strip() for surface in surface_attestations}
    if actual_surface_ids != expected_surface_ids:
        raise SystemExit(
            f"{path} baselineAttestation.surfaceAttestations must match the contract surfaces exactly"
        )
    for surface in surface_attestations:
        surface_id = str(surface.get("id") or "").strip()
        if str(surface.get("status") or "pending").strip() != "pending":
            raise SystemExit(
                f"{path} baseline surface {surface_id!r} status must start as pending"
            )
        if str(surface.get("evidenceRef") or "").strip():
            raise SystemExit(
                f"{path} baseline surface {surface_id!r} evidenceRef must start empty"
            )

    activation = payload.get("activationSummary") or {}
    if str(activation.get("status") or "").strip() != "pending":
        raise SystemExit(f"{path} activationSummary.status must start as pending")
    if not isinstance(activation.get("records") or [], list):
        raise SystemExit(f"{path} activationSummary.records must be a list")

    verification = payload.get("verificationResults") or {}
    checks = verification.get("checks") or []
    expected_check_ids = {check["id"] for check in contract["verificationPack"]["checks"]}
    actual_check_ids = {str(check.get("id") or "").strip() for check in checks}
    if actual_check_ids != expected_check_ids:
        raise SystemExit(
            f"{path} verificationResults.checks must match the contract verification checks exactly"
        )

    restore = payload.get("restoreAttestation") or {}
    if restore.get("restoreMode") != contract["restoreMode"]:
        raise SystemExit(f"{path} restoreAttestation.restoreMode must match the contract restoreMode")
    restore_surfaces = restore.get("surfaces") or []
    actual_restore_ids = {str(surface.get("id") or "").strip() for surface in restore_surfaces}
    expected_restore_ids = {surface["id"] for surface in contract["restoreScope"]["surfaces"]}
    if actual_restore_ids != expected_restore_ids:
        raise SystemExit(
            f"{path} restoreAttestation.surfaces must match the contract restore surfaces exactly"
        )

    exception_register = payload.get("exceptionRegister") or {}
    if not isinstance(exception_register.get("entries") or [], list):
        raise SystemExit(f"{path} exceptionRegister.entries must be a list")
    if not isinstance(payload.get("supplementalRecords") or [], list):
        raise SystemExit(f"{path} supplementalRecords must be a list")

    final_assessment = payload.get("finalAssessment") or {}
    if str(final_assessment.get("outcome") or "").strip() != "pending":
        raise SystemExit(f"{path} finalAssessment.outcome must start as pending")
    if (contract.get("authorization") or {}).get("required"):
        run_template = payload.get("run") or {}
        for field in ("authorizationRef", "authorizationDigest"):
            if field not in run_template:
                raise SystemExit(
                    f"{path} run template must include {field} for an authorized drill"
                )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="platform-engineering repository root",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_profile_args(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--profile", default="active-stack-runtime-drill")
        command_parser.add_argument("--profile-path", default="", help="optional explicit contract path")

    plan = subparsers.add_parser("plan")
    add_profile_args(plan)
    plan.add_argument("--format", choices=("text", "json"), default="text")

    snapshot = subparsers.add_parser("snapshot")
    add_profile_args(snapshot)
    snapshot.add_argument("--run-id", default="", help="optional stable run identifier")
    snapshot.add_argument("--operator", default="", help="operator running the drill")
    snapshot.add_argument("--note", default="", help="optional note for the snapshot record")
    snapshot.add_argument(
        "--authorization-ref",
        default="",
        help="durable reference to the exact authorization artifact",
    )
    snapshot.add_argument(
        "--authorization-digest",
        default="",
        help="sha256 digest of the exact authorization artifact",
    )
    snapshot.add_argument(
        "--authorization-file",
        default="",
        help="local immutable authorization artifact to validate before consumption",
    )
    snapshot.add_argument("--operator-approval-file", default="")
    snapshot.add_argument("--security-authorization-file", default="")
    snapshot.add_argument("--baseline-file", default="")
    snapshot.add_argument("--baseline-evidence-root", default="")
    snapshot.add_argument(
        "--output-root",
        default="",
        help="optional drill-state root; defaults to <repo>/.platform-drills",
    )

    activate = subparsers.add_parser("activate")
    activate.add_argument("--run", required=True, help="run directory created by snapshot")
    activate.add_argument("--actor", required=True, help="operator or automation actor")
    activate.add_argument("--note", default="", help="activation note")
    activate.add_argument(
        "--surface",
        action="append",
        default=[],
        help="optional surface ids activated by this note; defaults to all scoped surfaces",
    )

    attest_baseline = subparsers.add_parser("attest-baseline")
    attest_baseline.add_argument("--run", required=True, help="run directory created by snapshot")
    attest_baseline.add_argument("--surface", required=True, help="scoped surface id")
    attest_baseline.add_argument("--actor", required=True, help="operator or automation actor")
    attest_baseline.add_argument(
        "--evidence-ref",
        required=True,
        help="operator-reviewable evidence for the exact pre-run state",
    )
    attest_baseline.add_argument("--note", default="", help="baseline attestation note")

    verify = subparsers.add_parser("verify")
    verify.add_argument("--run", required=True, help="run directory created by snapshot")
    verify.add_argument("--check", required=True, help="verification check id")
    verify.add_argument("--status", required=True, choices=sorted(CHECK_STATUSES - {'pending'}))
    verify.add_argument("--actor", required=True, help="operator or automation actor")
    verify.add_argument("--evidence-ref", default="", help="operator-reviewable evidence reference")
    verify.add_argument("--note", default="", help="verification note")
    verify.add_argument("--decision", default="", choices=sorted(DECISIONS))
    verify.add_argument("--justification", default="")
    verify.add_argument("--owner", default="")
    verify.add_argument("--review-on", default="")

    record = subparsers.add_parser("record")
    record.add_argument("--run", required=True, help="run directory created by snapshot")
    record.add_argument("--phase", required=True, choices=sorted(PHASES))
    record.add_argument("--actor", required=True, help="operator or automation actor")
    record.add_argument("--evidence-ref", required=True, help="operator-reviewable evidence reference")
    record.add_argument("--note", default="", help="optional note")

    restore = subparsers.add_parser("restore")
    restore.add_argument("--run", required=True, help="run directory created by snapshot")
    restore.add_argument("--surface", required=True, help="restore surface id")
    restore.add_argument("--status", required=True, choices=sorted(RESTORE_STATUSES - {'pending'}))
    restore.add_argument("--actor", required=True, help="operator or automation actor")
    restore.add_argument("--note", default="", help="restore note")
    restore.add_argument("--decision", default="", choices=sorted(DECISIONS))
    restore.add_argument("--justification", default="")
    restore.add_argument("--owner", default="")
    restore.add_argument("--review-on", default="")

    controlled_exception = subparsers.add_parser("controlled-exception")
    controlled_exception.add_argument(
        "--run", required=True, help="controlled proof run directory"
    )
    controlled_exception.add_argument(
        "--actor", required=True, help="operator recording the exception"
    )
    controlled_exception.add_argument(
        "--decision", required=True, choices=sorted(DECISIONS)
    )
    controlled_exception.add_argument("--justification", required=True)
    controlled_exception.add_argument("--owner", required=True)
    controlled_exception.add_argument("--review-on", required=True)
    controlled_exception.add_argument("--note", default="")

    controlled_finalize = subparsers.add_parser("controlled-finalize")
    controlled_finalize.add_argument(
        "--run", required=True, help="controlled proof run directory"
    )

    status = subparsers.add_parser("status")
    status.add_argument("--run", default="", help="optional run directory created by snapshot")
    add_profile_args(status)
    status.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args()


def profile_payload(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    path = resolve_profile(args.repo_root, args.profile, args.profile_path or None)
    payload = validate_contract(path, load_yaml(path))
    return path, payload


def evidence_template_payload(
    repo_root: Path, profile_path: Path, contract: dict[str, Any]
) -> tuple[Path, dict[str, Any]]:
    raw_template_path = str((contract.get("evidenceModel") or {}).get("templatePath") or "").strip()
    template_path = resolve_repo_path(repo_root, raw_template_path)
    payload = validate_evidence_template(template_path, load_yaml(template_path), contract)
    return template_path, payload


def output_root(repo_root: Path, raw: str) -> Path:
    return Path(raw).expanduser().resolve() if raw else (repo_root / ".platform-drills").resolve()


def input_artifact_path(raw: str) -> Path:
    """Return an absolute input path without resolving its final symlink."""

    return Path(raw).expanduser().absolute()


def consume_or_resume_controlled_authorization(
    *,
    authorization: dict[str, Any],
    authorization_digest: str,
    consumption_root: Path,
    contracts: Any,
) -> tuple[dict[str, Any], Path, str]:
    """Resume only the exact receipt created by an interrupted snapshot."""

    from controlled_proof.authority import (  # noqa: PLC0415
        consume_authorization,
        consumption_receipt_path,
    )
    from controlled_proof.execution import validate_consumption_binding  # noqa: PLC0415
    from controlled_proof.model import read_bounded_json_with_digest  # noqa: PLC0415

    receipt_path = consumption_receipt_path(
        authorization["authorization_id"], consumption_root
    )
    if receipt_path.exists() or receipt_path.is_symlink():
        receipt, receipt_digest = read_bounded_json_with_digest(receipt_path)
        validate_consumption_binding(
            authorization,
            authorization_digest,
            receipt,
            receipt_digest,
            contracts,
        )
        return receipt, receipt_path, receipt_digest
    return consume_authorization(
        authorization=authorization,
        authorization_digest=authorization_digest,
        executor_source_revision=authorization["executor"]["source_revision"],
        consumption_root=consumption_root,
        contracts=contracts,
    )


def recover_incomplete_controlled_run(
    run_dir: Path,
    execution_claim_path: Path,
) -> None:
    """Remove an uncommitted snapshot only before execution ownership exists."""

    if not run_dir.exists() and not run_dir.is_symlink():
        return
    if (run_dir / "run.yaml").exists():
        raise SystemExit(f"run directory already exists: {run_dir}")
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise SystemExit(f"incomplete run path is not a directory: {run_dir}")
    if execution_claim_path.exists() or execution_claim_path.is_symlink():
        raise SystemExit(
            "incomplete snapshot cannot be rebuilt after execution was claimed"
        )
    shutil.rmtree(run_dir)


def prepare_controlled_proof_snapshot(
    args: argparse.Namespace,
    contract: dict[str, Any],
) -> dict[str, Any]:
    profile_root = (
        args.repo_root / "dev-integration" / "profiles" / "temporal"
    ).resolve()
    if str(profile_root) not in sys.path:
        sys.path.insert(0, str(profile_root))

    from controlled_proof.authority import (  # noqa: PLC0415
        GitSourceResolver,
        load_contracts,
        validate_authorization,
    )
    from controlled_proof.model import read_bounded_json  # noqa: PLC0415

    required_paths = {
        "--authorization-file": args.authorization_file,
        "--operator-approval-file": args.operator_approval_file,
        "--security-authorization-file": args.security_authorization_file,
        "--baseline-file": args.baseline_file,
        "--baseline-evidence-root": args.baseline_evidence_root,
    }
    missing = [option for option, value in required_paths.items() if not value.strip()]
    if missing:
        raise SystemExit(
            "controlled commissioning snapshot requires " + ", ".join(missing)
        )

    authorization_path = input_artifact_path(args.authorization_file)
    operator_approval_path = input_artifact_path(args.operator_approval_file)
    security_approval_path = input_artifact_path(args.security_authorization_file)
    baseline_path = input_artifact_path(args.baseline_file)
    baseline_evidence_root = Path(
        args.baseline_evidence_root
    ).expanduser().resolve()
    contracts = load_contracts()
    authorization = read_bounded_json(
        authorization_path,
        expected_digest=args.authorization_digest,
    )
    if args.authorization_ref != authorization["authorization_id"]:
        raise SystemExit(
            "--authorization-ref must equal the authorization artifact id"
        )
    if authorization["target"] != {
        "profile_id": contract["authorization"]["targetProfileId"],
        "profile_lifecycle": contract["authorization"]["targetProfileLifecycle"],
        "environment": contract["targetEnvironment"],
    }:
        raise SystemExit("authorization target does not match the drill profile")

    commissioning_session_id = authorization["commissioning_session"][
        "commissioning_session_id"
    ]
    requested_run_id = str(getattr(args, "run_id", "")).strip()
    if requested_run_id and requested_run_id != commissioning_session_id:
        raise SystemExit(
            "controlled commissioning run id must equal the authorized "
            "commissioning session id"
        )
    if str(getattr(args, "output_root", "")).strip():
        raise SystemExit(
            "controlled commissioning uses the canonical Platform drill-state root; "
            "--output-root is not allowed"
        )
    canonical_run_dir = (
        args.repo_root
        / ".platform-drills"
        / contract["id"]
        / commissioning_session_id
    ).absolute()
    if canonical_run_dir.is_symlink():
        raise SystemExit(f"run directory must not be a symbolic link: {canonical_run_dir}")
    if (canonical_run_dir / "run.yaml").exists():
        raise SystemExit(f"run directory already exists: {canonical_run_dir}")

    workspace_root = args.repo_root.resolve().parent
    validate_authorization(
        authorization,
        contracts=contracts,
        baseline_path=baseline_path,
        baseline_evidence_root=baseline_evidence_root,
        source_resolver=GitSourceResolver(workspace_root),
        operator_approval_path=operator_approval_path,
        security_approval_path=security_approval_path,
    )
    baseline = read_bounded_json(
        baseline_path,
        expected_digest=authorization["baseline_and_restore"][
            "baseline_snapshot_digest"
        ],
    )
    consumption_root = (
        args.repo_root / ".platform-drills" / "_controlled-proof-consumptions"
    ).resolve()
    receipt, receipt_path, receipt_digest = consume_or_resume_controlled_authorization(
        authorization=authorization,
        authorization_digest=args.authorization_digest,
        consumption_root=consumption_root,
        contracts=contracts,
    )
    return {
        "authorization_id": authorization["authorization_id"],
        "commissioning_session_id": commissioning_session_id,
        "authorization_path": str(authorization_path),
        "operator_approval_path": str(operator_approval_path),
        "security_authorization_path": str(security_approval_path),
        "baseline_path": str(baseline_path),
        "baseline_evidence_root": str(baseline_evidence_root),
        "baseline": baseline,
        "consumption_receipt": receipt,
        "consumption_receipt_path": str(receipt_path),
        "consumption_receipt_digest": receipt_digest,
    }


def default_run_id(contract_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{slugify(contract_id)}-{stamp}"


def run_paths(run_dir: Path) -> dict[str, Path]:
    return {
        "run": run_dir / "run.yaml",
        "contract": run_dir / "contract.yaml",
        "baseline": run_dir / "baseline.yaml",
        "verification": run_dir / "verification.yaml",
        "restore": run_dir / "restore.yaml",
        "evidence": run_dir / "evidence.yaml",
    }


def ensure_run_dir(path: Path) -> dict[str, Path]:
    run_dir = path.expanduser().resolve()
    paths = run_paths(run_dir)
    missing = [label for label, file_path in paths.items() if not file_path.exists()]
    if missing:
        raise SystemExit(f"{run_dir} is missing required drill files: {', '.join(sorted(missing))}")
    return paths


def build_baseline(contract: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    source_states = {}
    for repo_name in contract["scope"]["sourceRepos"]:
        source_states[repo_name] = git_state(repo_root.parent / repo_name)
    runtime_surfaces = []
    for surface in contract["scope"]["surfaces"]:
        runtime_surfaces.append(
            {
                "id": surface["id"],
                "lane": surface["lane"],
                "kind": surface["kind"],
                "ownerRepo": surface["ownerRepo"],
                "summary": surface["summary"],
                "baselineState": "record-required",
                "evidenceRef": "",
                "note": "",
            }
        )
    return {
        "schema_version": 1,
        "capturedAt": now_utc(),
        "sourceRepos": source_states,
        "runtimeSurfaces": runtime_surfaces,
    }


def build_verification(contract: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for check in contract["verificationPack"]["checks"]:
        checks.append(
            {
                "id": check["id"],
                "category": check["category"],
                "summary": check["summary"],
                "requiredByDefault": bool(check["requiredByDefault"]),
                "acceptedStatuses": list(check["acceptedStatuses"]),
                "status": "pending",
                "decision": None,
                "justification": "",
                "owner": "",
                "reviewOn": "",
                "evidenceRef": "",
                "note": "",
                "updatedAt": "",
                "updatedBy": "",
            }
        )
    return {
        "schema_version": 1,
        "checks": checks,
    }


def build_restore(contract: dict[str, Any]) -> dict[str, Any]:
    surfaces = []
    for surface in contract["restoreScope"]["surfaces"]:
        surfaces.append(
            {
                "id": surface["id"],
                "summary": surface["summary"],
                "status": "pending",
                "decision": None,
                "justification": "",
                "owner": "",
                "reviewOn": "",
                "note": "",
                "updatedAt": "",
                "updatedBy": "",
            }
        )
    return {
        "schema_version": 1,
        "restoreMode": contract["restoreMode"],
        "surfaces": surfaces,
    }


def build_evidence(
    contract: dict[str, Any],
    template_payload: dict[str, Any],
    run_manifest: dict[str, Any],
    run_dir: Path,
    baseline_payload: dict[str, Any],
) -> dict[str, Any]:
    evidence = copy.deepcopy(template_payload)
    evidence["run"] = {
        "runId": run_manifest["run_id"],
        "profileId": run_manifest["profile_id"],
        "title": run_manifest["title"],
        "authorityType": run_manifest["authorityType"],
        "drillType": run_manifest["drillType"],
        "createdAt": run_manifest["createdAt"],
        "createdBy": run_manifest["createdBy"],
        "runDir": str(run_dir),
        "contractPath": "contract.yaml",
        "evidenceOwner": contract["evidenceOwner"],
    }
    authorization = run_manifest.get("authorization") or {}
    if authorization:
        evidence["run"]["authorizationRef"] = authorization["ref"]
        evidence["run"]["authorizationDigest"] = authorization["digest"]
    evidence["baselineAttestation"]["sourceRepos"] = [
        {
            "repo": repo_name,
            "branch": state["branch"],
            "headSha": state["head_sha"],
            "dirty": bool(state["dirty"]),
            "upstream": state["upstream"],
        }
        for repo_name, state in sorted((baseline_payload.get("sourceRepos") or {}).items())
    ]
    return evidence


def remove_exception_entry(evidence: dict[str, Any], *, scope_type: str, scope_id: str) -> None:
    entries = (evidence.get("exceptionRegister") or {}).get("entries") or []
    evidence["exceptionRegister"]["entries"] = [
        entry
        for entry in entries
        if not (
            str(entry.get("scopeType")) == scope_type
            and str(entry.get("scopeId")) == scope_id
        )
    ]


def upsert_exception_entry(
    evidence: dict[str, Any],
    *,
    scope_type: str,
    scope_id: str,
    status: str,
    decision: str,
    justification: str,
    owner: str,
    review_on: str,
    actor: str,
    note: str,
) -> None:
    entries = (evidence.get("exceptionRegister") or {}).get("entries") or []
    updated_at = now_utc()
    entry = next(
        (
            current
            for current in entries
            if str(current.get("scopeType")) == scope_type
            and str(current.get("scopeId")) == scope_id
        ),
        None,
    )
    if entry is None:
        entry = {
            "scopeType": scope_type,
            "scopeId": scope_id,
        }
        entries.append(entry)
    entry["status"] = status
    entry["decision"] = decision
    entry["justification"] = justification
    entry["owner"] = owner
    entry["reviewOn"] = review_on
    entry["updatedAt"] = updated_at
    entry["updatedBy"] = actor
    entry["note"] = note
    evidence["exceptionRegister"]["entries"] = entries


def cmd_plan(args: argparse.Namespace) -> int:
    profile_path, contract = profile_payload(args)
    evidence_template_path_value, _ = evidence_template_payload(args.repo_root, profile_path, contract)
    summary = {
        "profile": contract["id"],
        "title": contract["title"],
        "authorityType": contract["authorityType"],
        "drillType": contract["drillType"],
        "targetEnvironment": contract["targetEnvironment"],
        "targetLanes": contract.get("targetLanes", []),
        "evidenceOwner": contract["evidenceOwner"],
        "sourceRepos": contract["scope"]["sourceRepos"],
        "surfaceCount": len(contract["scope"]["surfaces"]),
        "checkCount": len(contract["verificationPack"]["checks"]),
        "restoreMode": contract["restoreMode"],
        "profilePath": str(profile_path),
        "evidenceTemplatePath": str(evidence_template_path_value),
        "availability": (contract.get("sourceEnablement") or {}).get("status", "available"),
        "snapshotAllowed": (contract.get("sourceEnablement") or {}).get(
            "snapshotAllowed", True
        ),
    }
    if args.format == "json":
        print(json.dumps(summary, indent=2))
        return 0

    print(f"profile={summary['profile']} title={summary['title']}")
    print(
        f"authority_type={summary['authorityType']} "
        f"drill_type={summary['drillType']} "
        f"target_environment={summary['targetEnvironment']}"
    )
    print(f"target_lanes={', '.join(summary['targetLanes'])}")
    print(f"source_repos={', '.join(summary['sourceRepos'])}")
    print(f"surface_count={summary['surfaceCount']} check_count={summary['checkCount']}")
    print(f"restore_mode={summary['restoreMode']} evidence_owner={summary['evidenceOwner']}")
    print(
        f"availability={summary['availability']} "
        f"snapshot_allowed={str(bool(summary['snapshotAllowed'])).lower()}"
    )
    print(f"profile_path={summary['profilePath']}")
    print(f"evidence_template_path={summary['evidenceTemplatePath']}")
    print("preconditions:")
    for item in contract["preconditions"]:
        print(f"- {item['id']}: {item['summary']}")
    print("surfaces:")
    for surface in contract["scope"]["surfaces"]:
        print(
            f"- {surface['id']} lane={surface['lane']} "
            f"owner={surface['ownerRepo']} kind={surface['kind']} summary={surface['summary']}"
        )
    print("verification_checks:")
    for check in contract["verificationPack"]["checks"]:
        accepted = ",".join(check["acceptedStatuses"])
        print(
            f"- {check['id']} category={check['category']} "
            f"required_by_default={str(bool(check['requiredByDefault'])).lower()} "
            f"accepted_statuses={accepted}"
        )
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    profile_path, contract = profile_payload(args)
    if contract.get("id") == "temporal-component-commissioning-proof":
        authorization_ref = str(args.authorization_ref).strip()
        if not authorization_ref:
            raise SystemExit("--authorization-ref is required for this drill profile")
        with controlled_snapshot_lock(args.repo_root, authorization_ref):
            return _cmd_snapshot(args, profile_path, contract)
    return _cmd_snapshot(args, profile_path, contract)


def _cmd_snapshot(
    args: argparse.Namespace,
    profile_path: Path,
    contract: dict[str, Any],
) -> int:
    source_enablement = contract.get("sourceEnablement") or {}
    if contract.get("drillType") == "component-commissioning-proof":
        implementation_ref = str(
            source_enablement.get("implementationWorkItemRef") or "reviewed implementation"
        )
        implementation_label = implementation_ref.replace(
            "openproject://work_packages/", "ART #"
        )
        if (
            contract.get("id") != "temporal-component-commissioning-proof"
            or source_enablement.get("status") != "source-reviewed"
            or source_enablement.get("snapshotAllowed") is not True
        ):
            raise SystemExit(
                "commissioning snapshot denied: permit artifact validation and atomic "
                f"consumption are not source-reviewed for {implementation_label}"
            )
    evidence_template_path_value, evidence_template = evidence_template_payload(
        args.repo_root, profile_path, contract
    )
    controlled_proof = None
    if contract.get("id") == "temporal-component-commissioning-proof":
        controlled_proof = prepare_controlled_proof_snapshot(
            args,
            contract,
        )
        run_id = controlled_proof["commissioning_session_id"]
    else:
        run_id = args.run_id.strip() or default_run_id(contract["id"])
    authorization_contract = contract.get("authorization") or {}
    authorization_ref = args.authorization_ref.strip()
    authorization_digest = args.authorization_digest.strip()
    if authorization_contract.get("required"):
        if not authorization_ref:
            raise SystemExit("--authorization-ref is required for this drill profile")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", authorization_digest):
            raise SystemExit(
                "--authorization-digest must be a lowercase sha256:<64-hex> digest"
            )
    run_state_root = output_root(args.repo_root, args.output_root)
    run_dir = run_state_root / contract["id"] / run_id
    if run_dir.exists():
        if controlled_proof is None or (run_dir / "run.yaml").exists():
            raise SystemExit(f"run directory already exists: {run_dir}")
        from controlled_proof.authority import authorization_storage_key  # noqa: PLC0415

        authorization_key = authorization_storage_key(
            controlled_proof["authorization_id"]
        )
        execution_claim_path = (
            args.repo_root
            / ".platform-drills"
            / "_controlled-proof-executions"
            / f"{authorization_key}.json"
        )
        recover_incomplete_controlled_run(run_dir, execution_claim_path)
    run_dir.mkdir(parents=True, exist_ok=False)
    paths = run_paths(run_dir)
    shutil.copy2(profile_path, paths["contract"])

    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "profile_id": contract["id"],
        "title": contract["title"],
        "authorityType": contract["authorityType"],
        "drillType": contract["drillType"],
        "targetEnvironment": contract["targetEnvironment"],
        "restoreMode": contract["restoreMode"],
        "createdAt": now_utc(),
        "createdBy": args.operator.strip() or "unknown",
        "note": args.note.strip(),
        "profilePath": str(profile_path),
        "evidenceTemplatePath": str(evidence_template_path_value),
        "phaseStatus": {
            "baseline": "pending",
            "activation": "pending",
            "verification": "pending",
            "restore": "pending",
        },
        "evidenceRecords": [],
    }
    if authorization_contract.get("required"):
        manifest["authorization"] = {
            "artifactType": authorization_contract["artifactType"],
            "ref": authorization_ref,
            "digest": authorization_digest,
            "targetProfileId": authorization_contract["targetProfileId"],
            "targetProfileLifecycle": authorization_contract[
                "targetProfileLifecycle"
            ],
            "maxRuns": authorization_contract["maxRuns"],
            "securityReviewRef": authorization_contract["securityReviewRef"],
            "permitIssuer": copy.deepcopy(authorization_contract["permitIssuer"]),
            "executor": copy.deepcopy(authorization_contract["executor"]),
            "terminalCleanupAuthority": copy.deepcopy(
                authorization_contract["terminalCleanupAuthority"]
            ),
        }
    if controlled_proof is not None:
        receipt = controlled_proof["consumption_receipt"]
        from controlled_proof.authority import authorization_storage_key  # noqa: PLC0415

        authorization_key = authorization_storage_key(
            controlled_proof["authorization_id"]
        )
        manifest["phaseStatus"]["baseline"] = "captured"
        manifest["controlledProof"] = {
            "authorizationPath": controlled_proof["authorization_path"],
            "operatorApprovalPath": controlled_proof["operator_approval_path"],
            "securityAuthorizationPath": controlled_proof[
                "security_authorization_path"
            ],
            "baselinePath": controlled_proof["baseline_path"],
            "baselineEvidenceRoot": controlled_proof["baseline_evidence_root"],
            "consumptionReceiptRef": receipt["receipt_id"],
            "consumptionReceiptPath": controlled_proof[
                "consumption_receipt_path"
            ],
            "consumptionReceiptDigest": controlled_proof[
                "consumption_receipt_digest"
            ],
            "consumedAt": receipt["consumed_at"],
            "executionClaimPath": str(
                args.repo_root
                / ".platform-drills"
                / "_controlled-proof-executions"
                / f"{authorization_key}.json"
            ),
            "outputRoot": str(run_dir / "controlled-proof-output"),
        }
    baseline_payload = build_baseline(contract, args.repo_root)
    if controlled_proof is not None:
        imported_surfaces = {
            item["surface_id"]: item
            for item in controlled_proof["baseline"]["surface_observations"]
        }
        for surface in baseline_payload["runtimeSurfaces"]:
            imported = imported_surfaces[surface["id"]]
            surface["baselineState"] = "attested"
            surface["evidenceRef"] = imported["evidence_ref"]
            surface["note"] = f"immutable state: {imported['state']}"
    dump_yaml(paths["baseline"], baseline_payload)
    dump_yaml(paths["verification"], build_verification(contract))
    dump_yaml(paths["restore"], build_restore(contract))
    evidence_payload = build_evidence(
        contract, evidence_template, manifest, run_dir, baseline_payload
    )
    if controlled_proof is not None:
        imported_surfaces = {
            item["surface_id"]: item
            for item in controlled_proof["baseline"]["surface_observations"]
        }
        evidence_payload["baselineAttestation"]["captureStatus"] = "captured"
        for surface in evidence_payload["baselineAttestation"][
            "surfaceAttestations"
        ]:
            imported = imported_surfaces[surface["id"]]
            surface["status"] = "attested"
            surface["evidenceRef"] = imported["evidence_ref"]
            surface["note"] = f"immutable state: {imported['state']}"
    dump_yaml(paths["evidence"], evidence_payload)
    dump_yaml_exclusive(paths["run"], manifest)
    print(f"run_id={run_id}")
    print(f"run_dir={run_dir}")
    print(f"profile={contract['id']}")
    print(f"evidence_file={paths['evidence']}")
    return 0


def load_run(
    run_dir: str,
) -> tuple[
    Path,
    dict[str, Path],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    directory = Path(run_dir).expanduser().resolve()
    paths = ensure_run_dir(directory)
    run_payload = load_yaml(paths["run"])
    baseline = load_yaml(paths["baseline"])
    verification = load_yaml(paths["verification"])
    restore = load_yaml(paths["restore"])
    evidence = load_yaml(paths["evidence"])
    return directory, paths, run_payload, baseline, verification, restore, evidence


def write_run(
    paths: dict[str, Path],
    run_payload: dict[str, Any],
    baseline: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
    restore: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
) -> None:
    dump_yaml(paths["run"], run_payload)
    if baseline is not None:
        dump_yaml(paths["baseline"], baseline)
    if verification is not None:
        dump_yaml(paths["verification"], verification)
    if restore is not None:
        dump_yaml(paths["restore"], restore)
    if evidence is not None:
        dump_yaml(paths["evidence"], evidence)


def baseline_attestation_complete(
    baseline: dict[str, Any], evidence: dict[str, Any]
) -> bool:
    baseline_surfaces = baseline.get("runtimeSurfaces") or []
    evidence_surfaces = (evidence.get("baselineAttestation") or {}).get(
        "surfaceAttestations"
    ) or []
    if not baseline_surfaces or not evidence_surfaces:
        return False
    baseline_by_id = {
        str(surface.get("id") or "").strip(): surface for surface in baseline_surfaces
    }
    evidence_by_id = {
        str(surface.get("id") or "").strip(): surface for surface in evidence_surfaces
    }
    if "" in baseline_by_id or "" in evidence_by_id:
        return False
    if set(baseline_by_id) != set(evidence_by_id):
        return False
    return all(
        baseline_by_id[surface_id].get("baselineState") == "attested"
        and bool(str(baseline_by_id[surface_id].get("evidenceRef") or "").strip())
        and evidence_by_id[surface_id].get("status") == "attested"
        and bool(str(evidence_by_id[surface_id].get("evidenceRef") or "").strip())
        for surface_id in baseline_by_id
    )


def deny_generic_mutation_for_controlled_proof(
    run_payload: dict[str, Any], action: str
) -> None:
    if "controlledProof" in run_payload:
        raise SystemExit(
            f"{action} denied: permit-bound controlled proof runs may be mutated only "
            "by the source-reviewed executor"
        )


def enforce_controlled_restore_record(
    run_payload: dict[str, Any], status: str
) -> None:
    if "controlledProof" in run_payload:
        raise SystemExit(
            "restore mutation denied: permit-bound controlled proof restoration is "
            "recorded only by the source-reviewed executor; use controlled-exception "
            "after a stopped draft is emitted"
        )


def load_controlled_proof_artifacts(
    run_dir: Path,
    run_payload: dict[str, Any],
) -> dict[str, Any]:
    controlled = run_payload.get("controlledProof")
    if not isinstance(controlled, dict):
        raise SystemExit("run is not a permit-bound controlled proof")
    required = {
        "authorizationPath",
        "consumptionReceiptPath",
        "consumptionReceiptDigest",
        "executionClaimPath",
        "outputRoot",
    }
    missing = sorted(required - set(controlled))
    if missing:
        raise SystemExit(
            "controlled proof run is missing artifact bindings: " + ", ".join(missing)
        )

    profile_root = (
        Path(__file__).resolve().parents[1]
        / "dev-integration"
        / "profiles"
        / "temporal"
    )
    if str(profile_root) not in sys.path:
        sys.path.insert(0, str(profile_root))
    from controlled_proof.authority import load_contracts  # noqa: PLC0415
    from controlled_proof.execution import STOPPED_DRAFT_NAME  # noqa: PLC0415
    from controlled_proof.model import (  # noqa: PLC0415
        read_bounded_json,
        read_bounded_json_with_digest,
    )

    output_root_path = input_artifact_path(str(controlled["outputRoot"]))
    expected_output_root = (run_dir / "controlled-proof-output").absolute()
    if output_root_path != expected_output_root or output_root_path.is_symlink():
        raise SystemExit("controlled proof output root does not match its run")
    authorization_digest = str(
        (run_payload.get("authorization") or {}).get("digest") or ""
    )
    authorization = read_bounded_json(
        input_artifact_path(str(controlled["authorizationPath"])),
        expected_digest=authorization_digest,
    )
    consumption_receipt = read_bounded_json(
        input_artifact_path(str(controlled["consumptionReceiptPath"])),
        expected_digest=str(controlled["consumptionReceiptDigest"]),
    )
    execution_claim_path = input_artifact_path(str(controlled["executionClaimPath"]))
    execution_claim, execution_claim_digest = read_bounded_json_with_digest(
        execution_claim_path
    )
    stopped_draft_path = output_root_path / STOPPED_DRAFT_NAME
    stopped_draft, stopped_draft_digest = read_bounded_json_with_digest(
        stopped_draft_path
    )
    if run_payload.get("run_id") != authorization["commissioning_session"][
        "commissioning_session_id"
    ]:
        raise SystemExit("controlled proof run id does not match its authorization")
    return {
        "controlled": controlled,
        "contracts": load_contracts(),
        "authorization": authorization,
        "authorization_digest": authorization_digest,
        "consumption_receipt": consumption_receipt,
        "consumption_receipt_digest": str(controlled["consumptionReceiptDigest"]),
        "execution_claim": execution_claim,
        "execution_claim_digest": execution_claim_digest,
        "stopped_draft": stopped_draft,
        "stopped_draft_path": stopped_draft_path,
        "stopped_draft_digest": stopped_draft_digest,
        "output_root": output_root_path,
    }


def cmd_attest_baseline(args: argparse.Namespace) -> int:
    _, paths, run_payload, baseline, _, _, evidence = load_run(args.run)
    deny_generic_mutation_for_controlled_proof(run_payload, "baseline attestation")
    if run_payload.get("phaseStatus", {}).get("activation") != "pending":
        raise SystemExit("baseline attestation denied after activation has been recorded")
    actor = args.actor.strip()
    if not actor:
        raise SystemExit("--actor must not be blank")
    surfaces = baseline.get("runtimeSurfaces") or []
    target = next((surface for surface in surfaces if surface.get("id") == args.surface), None)
    if target is None:
        raise SystemExit(f"unknown baseline surface id {args.surface!r}")

    evidence_ref = args.evidence_ref.strip()
    if not evidence_ref:
        raise SystemExit("--evidence-ref must not be blank")
    updated_at = now_utc()
    target["baselineState"] = "attested"
    target["evidenceRef"] = evidence_ref
    target["note"] = args.note.strip()
    target["updatedAt"] = updated_at
    target["updatedBy"] = actor

    baseline_attestation = evidence.get("baselineAttestation") or {}
    evidence_surfaces = baseline_attestation.get("surfaceAttestations") or []
    evidence_target = next(
        (surface for surface in evidence_surfaces if surface.get("id") == args.surface),
        None,
    )
    if evidence_target is None:
        raise SystemExit(f"evidence file is missing baseline surface {args.surface!r}")
    evidence_target["status"] = "attested"
    evidence_target["evidenceRef"] = evidence_ref
    evidence_target["note"] = args.note.strip()
    evidence_target["updatedAt"] = updated_at
    evidence_target["updatedBy"] = actor

    if baseline_attestation_complete(baseline, evidence):
        run_payload["phaseStatus"]["baseline"] = "captured"
        baseline_attestation["captureStatus"] = "captured"
    else:
        run_payload["phaseStatus"]["baseline"] = "in-progress"
        baseline_attestation["captureStatus"] = "in-progress"
    evidence["baselineAttestation"] = baseline_attestation
    write_run(paths, run_payload, baseline=baseline, evidence=evidence)
    print(
        f"run_id={run_payload['run_id']} baseline_surface={args.surface} "
        f"status={target['baselineState']}"
    )
    return 0


def cmd_activate(args: argparse.Namespace) -> int:
    _, paths, run_payload, baseline, _, _, evidence = load_run(args.run)
    deny_generic_mutation_for_controlled_proof(run_payload, "activation")
    actor = args.actor.strip()
    if not actor:
        raise SystemExit("--actor must not be blank")
    baseline_surfaces = baseline.get("runtimeSurfaces") or []
    if (
        run_payload.get("phaseStatus", {}).get("baseline") != "captured"
        or (evidence.get("baselineAttestation") or {}).get("captureStatus") != "captured"
        or not baseline_attestation_complete(baseline, evidence)
    ):
        raise SystemExit(
            "activation denied: attest every scoped baseline surface with evidence first"
        )
    known_surface_ids = {
        str(surface.get("id"))
        for surface in baseline_surfaces
        if str(surface.get("id") or "").strip()
    }
    scoped_surfaces = args.surface or [
        str(surface.get("id"))
        for surface in baseline_surfaces
        if str(surface.get("id") or "").strip()
    ]
    unknown_surface_ids = set(scoped_surfaces) - known_surface_ids
    if unknown_surface_ids:
        raise SystemExit(
            "activation contains unknown scoped surfaces: "
            + ", ".join(sorted(unknown_surface_ids))
        )
    run_payload.setdefault("activation", {})
    run_payload["activation"] = {
        "status": "recorded",
        "actor": actor,
        "surfaces": scoped_surfaces,
        "note": args.note.strip(),
        "recordedAt": now_utc(),
    }
    run_payload["phaseStatus"]["activation"] = "recorded"
    activation_summary = evidence.get("activationSummary") or {}
    activation_summary["status"] = "recorded"
    activation_summary.setdefault("records", [])
    activation_summary["records"].append(
        {
            "actor": actor,
            "surfaces": scoped_surfaces,
            "note": args.note.strip(),
            "recordedAt": now_utc(),
        }
    )
    evidence["activationSummary"] = activation_summary
    write_run(paths, run_payload, evidence=evidence)
    print(f"run_id={run_payload['run_id']} activation=recorded")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    _, paths, run_payload, _, verification, _, evidence = load_run(args.run)
    deny_generic_mutation_for_controlled_proof(run_payload, "verification")
    checks = verification.get("checks") or []
    target = next((check for check in checks if check.get("id") == args.check), None)
    if target is None:
        raise SystemExit(f"unknown check id {args.check!r}")
    if args.status == "blocked":
        for field_name, value in {
            "--decision": args.decision,
            "--justification": args.justification,
            "--owner": args.owner,
            "--review-on": args.review_on,
        }.items():
            if not value.strip():
                raise SystemExit(f"{field_name} is required when --status=blocked")
    target["status"] = args.status
    target["decision"] = args.decision or None
    target["justification"] = args.justification.strip()
    target["owner"] = args.owner.strip()
    target["reviewOn"] = args.review_on.strip()
    target["evidenceRef"] = args.evidence_ref.strip()
    target["note"] = args.note.strip()
    target["updatedAt"] = now_utc()
    target["updatedBy"] = args.actor.strip()
    evidence_checks = (evidence.get("verificationResults") or {}).get("checks") or []
    evidence_target = next((check for check in evidence_checks if check.get("id") == args.check), None)
    if evidence_target is None:
        raise SystemExit(f"evidence file is missing verification check {args.check!r}")
    evidence_target["status"] = args.status
    evidence_target["decision"] = args.decision or None
    evidence_target["justification"] = args.justification.strip()
    evidence_target["owner"] = args.owner.strip()
    evidence_target["reviewOn"] = args.review_on.strip()
    evidence_target["evidenceRef"] = args.evidence_ref.strip()
    evidence_target["note"] = args.note.strip()
    evidence_target["updatedAt"] = target["updatedAt"]
    evidence_target["updatedBy"] = args.actor.strip()
    if args.status == "blocked":
        upsert_exception_entry(
            evidence,
            scope_type="verification-check",
            scope_id=args.check,
            status=args.status,
            decision=args.decision,
            justification=args.justification.strip(),
            owner=args.owner.strip(),
            review_on=args.review_on.strip(),
            actor=args.actor.strip(),
            note=args.note.strip(),
        )
    else:
        remove_exception_entry(evidence, scope_type="verification-check", scope_id=args.check)
    if all(str(check.get("status")) != "pending" for check in checks):
        run_payload["phaseStatus"]["verification"] = "recorded"
    else:
        run_payload["phaseStatus"]["verification"] = "in-progress"
    write_run(paths, run_payload, verification=verification, evidence=evidence)
    print(f"run_id={run_payload['run_id']} check={args.check} status={args.status}")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    _, paths, run_payload, _, _, _, evidence = load_run(args.run)
    deny_generic_mutation_for_controlled_proof(run_payload, "supplemental evidence")
    run_payload.setdefault("evidenceRecords", [])
    record = {
        "phase": args.phase,
        "actor": args.actor.strip(),
        "evidenceRef": args.evidence_ref.strip(),
        "note": args.note.strip(),
        "recordedAt": now_utc(),
    }
    run_payload["evidenceRecords"].append(record)
    evidence.setdefault("supplementalRecords", [])
    evidence["supplementalRecords"].append(record)
    write_run(paths, run_payload, evidence=evidence)
    print(f"run_id={run_payload['run_id']} evidence_recorded={args.phase}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    _, paths, run_payload, _, _, restore, evidence = load_run(args.run)
    enforce_controlled_restore_record(run_payload, args.status)
    surfaces = restore.get("surfaces") or []
    target = next((surface for surface in surfaces if surface.get("id") == args.surface), None)
    if target is None:
        raise SystemExit(f"unknown restore surface id {args.surface!r}")
    if args.status == "exception":
        for field_name, value in {
            "--decision": args.decision,
            "--justification": args.justification,
            "--owner": args.owner,
            "--review-on": args.review_on,
        }.items():
            if not value.strip():
                raise SystemExit(f"{field_name} is required when --status=exception")
    target["status"] = args.status
    target["decision"] = args.decision or None
    target["justification"] = args.justification.strip()
    target["owner"] = args.owner.strip()
    target["reviewOn"] = args.review_on.strip()
    target["note"] = args.note.strip()
    target["updatedAt"] = now_utc()
    target["updatedBy"] = args.actor.strip()
    evidence_surfaces = (evidence.get("restoreAttestation") or {}).get("surfaces") or []
    evidence_target = next((surface for surface in evidence_surfaces if surface.get("id") == args.surface), None)
    if evidence_target is None:
        raise SystemExit(f"evidence file is missing restore surface {args.surface!r}")
    evidence_target["status"] = args.status
    evidence_target["decision"] = args.decision or None
    evidence_target["justification"] = args.justification.strip()
    evidence_target["owner"] = args.owner.strip()
    evidence_target["reviewOn"] = args.review_on.strip()
    evidence_target["note"] = args.note.strip()
    evidence_target["updatedAt"] = target["updatedAt"]
    evidence_target["updatedBy"] = args.actor.strip()
    if args.status == "exception":
        upsert_exception_entry(
            evidence,
            scope_type="restore-surface",
            scope_id=args.surface,
            status=args.status,
            decision=args.decision,
            justification=args.justification.strip(),
            owner=args.owner.strip(),
            review_on=args.review_on.strip(),
            actor=args.actor.strip(),
            note=args.note.strip(),
        )
    else:
        remove_exception_entry(evidence, scope_type="restore-surface", scope_id=args.surface)
    if all(str(surface.get("status")) != "pending" for surface in surfaces):
        run_payload["phaseStatus"]["restore"] = "recorded"
    else:
        run_payload["phaseStatus"]["restore"] = "in-progress"
    write_run(paths, run_payload, restore=restore, evidence=evidence)
    print(f"run_id={run_payload['run_id']} restore_surface={args.surface} status={args.status}")
    return 0


def cmd_controlled_exception(args: argparse.Namespace) -> int:
    run_dir, paths, run_payload, _, _, restore, evidence = load_run(args.run)
    artifacts = load_controlled_proof_artifacts(run_dir, run_payload)
    from controlled_proof.execution import record_governed_exception  # noqa: PLC0415

    exception, exception_path, exception_digest = record_governed_exception(
        authorization=artifacts["authorization"],
        authorization_digest=artifacts["authorization_digest"],
        consumption_receipt=artifacts["consumption_receipt"],
        consumption_receipt_digest=artifacts["consumption_receipt_digest"],
        execution_claim=artifacts["execution_claim"],
        execution_claim_digest=artifacts["execution_claim_digest"],
        stopped_draft=artifacts["stopped_draft"],
        stopped_draft_digest=artifacts["stopped_draft_digest"],
        output_root=artifacts["output_root"],
        decision=args.decision,
        justification=args.justification,
        owner=args.owner,
        review_on=args.review_on,
        actor=args.actor,
        note=args.note,
        contracts=artifacts["contracts"],
    )
    for surface in restore.get("surfaces") or []:
        surface["status"] = "exception"
        surface["decision"] = exception["decision"]
        surface["justification"] = exception["justification"]
        surface["owner"] = exception["owner"]
        surface["reviewOn"] = exception["review_on"]
        surface["note"] = exception["note"]
        surface["updatedAt"] = exception["recorded_at"]
        surface["updatedBy"] = exception["recorded_by"]
    for surface in (evidence.get("restoreAttestation") or {}).get("surfaces") or []:
        surface["status"] = "exception"
        surface["decision"] = exception["decision"]
        surface["justification"] = exception["justification"]
        surface["owner"] = exception["owner"]
        surface["reviewOn"] = exception["review_on"]
        surface["note"] = exception["note"]
        surface["updatedAt"] = exception["recorded_at"]
        surface["updatedBy"] = exception["recorded_by"]
    upsert_exception_entry(
        evidence,
        scope_type="controlled-proof-session",
        scope_id=exception["commissioning_session_id"],
        status="exception",
        decision=exception["decision"],
        justification=exception["justification"],
        owner=exception["owner"],
        review_on=exception["review_on"],
        actor=exception["recorded_by"],
        note=exception["note"],
    )
    controlled = artifacts["controlled"]
    controlled.update(
        {
            "stoppedDraftPath": str(artifacts["stopped_draft_path"]),
            "stoppedDraftDigest": artifacts["stopped_draft_digest"],
            "governedExceptionPath": str(exception_path),
            "governedExceptionDigest": exception_digest,
            "executionStatus": "stopped-awaiting-result",
        }
    )
    run_payload["phaseStatus"]["restore"] = "recorded"
    write_run(paths, run_payload, restore=restore, evidence=evidence)
    print(f"run_id={run_payload['run_id']} controlled_exception={exception['record_id']}")
    print(f"exception_digest={exception_digest}")
    return 0


def cmd_controlled_finalize(args: argparse.Namespace) -> int:
    run_dir, paths, run_payload, _, _, _, _ = load_run(args.run)
    artifacts = load_controlled_proof_artifacts(run_dir, run_payload)
    controlled = artifacts["controlled"]
    required = {"governedExceptionPath", "governedExceptionDigest"}
    missing = sorted(required - set(controlled))
    if missing:
        raise SystemExit(
            "controlled proof exception must be recorded before finalization"
        )
    from controlled_proof.execution import finalize_stopped_result  # noqa: PLC0415
    from controlled_proof.model import read_bounded_json  # noqa: PLC0415

    exception = read_bounded_json(
        input_artifact_path(str(controlled["governedExceptionPath"])),
        expected_digest=str(controlled["governedExceptionDigest"]),
    )
    result, result_digest = finalize_stopped_result(
        authorization=artifacts["authorization"],
        authorization_digest=artifacts["authorization_digest"],
        consumption_receipt=artifacts["consumption_receipt"],
        consumption_receipt_digest=artifacts["consumption_receipt_digest"],
        execution_claim=artifacts["execution_claim"],
        execution_claim_digest=artifacts["execution_claim_digest"],
        stopped_draft=artifacts["stopped_draft"],
        stopped_draft_digest=artifacts["stopped_draft_digest"],
        governed_exception=exception,
        governed_exception_digest=str(controlled["governedExceptionDigest"]),
        output_root=artifacts["output_root"],
        contracts=artifacts["contracts"],
    )
    result_path = artifacts["output_root"] / "controlled-proof-result.json"
    controlled.update(
        {
            "resultPath": str(result_path),
            "resultDigest": result_digest,
            "executionStatus": "stopped-result-emitted",
        }
    )
    write_run(paths, run_payload)
    print(f"run_id={run_payload['run_id']} result={result['result_id']}")
    print(f"result_digest={result_digest} outcome={result['outcome']}")
    return 0


def controlled_execution_status(run_dir: Path, run_payload: dict[str, Any]) -> str | None:
    controlled = run_payload.get("controlledProof")
    if not isinstance(controlled, dict):
        return None
    output_root_value = str(controlled.get("outputRoot") or "").strip()
    if not output_root_value:
        return "invalid-artifact-bindings"
    output_root_path = input_artifact_path(output_root_value)
    if output_root_path != (run_dir / "controlled-proof-output").absolute():
        return "invalid-artifact-bindings"
    result_path = output_root_path / "controlled-proof-result.json"
    exception_path = output_root_path / "controlled-proof-governed-exception.json"
    draft_path = output_root_path / "controlled-proof-stopped-draft.json"
    execution_claim_value = str(controlled.get("executionClaimPath") or "").strip()
    execution_claim_path = (
        input_artifact_path(execution_claim_value) if execution_claim_value else None
    )
    if result_path.is_file() and not result_path.is_symlink():
        return "result-emitted"
    if exception_path.is_file() and not exception_path.is_symlink():
        return "stopped-awaiting-result"
    if draft_path.is_file() and not draft_path.is_symlink():
        return "stopped-awaiting-exception"
    if (
        execution_claim_path is not None
        and execution_claim_path.is_file()
        and not execution_claim_path.is_symlink()
    ):
        return "execution-claimed"
    return "permit-consumed"


def cmd_status(args: argparse.Namespace) -> int:
    if args.run:
        run_dir, _, run_payload, baseline, verification, restore, evidence = load_run(args.run)
        pending_checks = sum(1 for check in verification.get("checks", []) if check.get("status") == "pending")
        blocked_checks = sum(1 for check in verification.get("checks", []) if check.get("status") == "blocked")
        pending_restore = sum(1 for surface in restore.get("surfaces", []) if surface.get("status") == "pending")
        pending_baseline = sum(
            1
            for surface in baseline.get("runtimeSurfaces", [])
            if surface.get("baselineState") != "attested"
            or not str(surface.get("evidenceRef") or "").strip()
        )
        summary = {
            "run_id": run_payload["run_id"],
            "profile_id": run_payload["profile_id"],
            "run_dir": str(run_dir),
            "phaseStatus": run_payload.get("phaseStatus", {}),
            "sourceRepoCount": len((baseline.get("sourceRepos") or {}).keys()),
            "runtimeSurfaceCount": len(baseline.get("runtimeSurfaces") or []),
            "pendingBaselineCount": pending_baseline,
            "pendingCheckCount": pending_checks,
            "blockedCheckCount": blocked_checks,
            "pendingRestoreCount": pending_restore,
            "evidenceRecordCount": len(run_payload.get("evidenceRecords") or []),
            "exceptionCount": len(((evidence.get("exceptionRegister") or {}).get("entries") or [])),
            "evidenceFile": str(run_paths(run_dir)["evidence"]),
            "controlledExecutionStatus": controlled_execution_status(
                run_dir, run_payload
            ),
        }
        if args.format == "json":
            print(json.dumps(summary, indent=2))
            return 0
        print(f"run_id={summary['run_id']} profile={summary['profile_id']}")
        print(f"run_dir={summary['run_dir']}")
        print(f"evidence_file={summary['evidenceFile']}")
        print(
            f"baseline={summary['phaseStatus'].get('baseline')} "
            f"activation={summary['phaseStatus'].get('activation')} "
            f"verification={summary['phaseStatus'].get('verification')} "
            f"restore={summary['phaseStatus'].get('restore')}"
        )
        print(
            f"source_repos={summary['sourceRepoCount']} runtime_surfaces={summary['runtimeSurfaceCount']} "
            f"pending_baseline={summary['pendingBaselineCount']} "
            f"pending_checks={summary['pendingCheckCount']} blocked_checks={summary['blockedCheckCount']} "
            f"pending_restore={summary['pendingRestoreCount']} evidence_records={summary['evidenceRecordCount']} "
            f"exceptions={summary['exceptionCount']}"
        )
        if summary["controlledExecutionStatus"] is not None:
            print(
                "controlled_execution_status="
                f"{summary['controlledExecutionStatus']}"
            )
        return 0

    profile_path, contract = profile_payload(args)
    evidence_template_path_value, _ = evidence_template_payload(args.repo_root, profile_path, contract)
    summary = {
        "profile": contract["id"],
        "title": contract["title"],
        "profilePath": str(profile_path),
        "evidenceTemplatePath": str(evidence_template_path_value),
        "surfaceCount": len(contract["scope"]["surfaces"]),
        "checkCount": len(contract["verificationPack"]["checks"]),
        "restoreSurfaceCount": len(contract["restoreScope"]["surfaces"]),
        "restoreMode": contract["restoreMode"],
    }
    if args.format == "json":
        print(json.dumps(summary, indent=2))
        return 0
    print(f"profile={summary['profile']} title={summary['title']}")
    print(f"profile_path={summary['profilePath']}")
    print(f"evidence_template_path={summary['evidenceTemplatePath']}")
    print(
        f"surfaces={summary['surfaceCount']} checks={summary['checkCount']} "
        f"restore_surfaces={summary['restoreSurfaceCount']} restore_mode={summary['restoreMode']}"
    )
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "plan":
        return cmd_plan(args)
    if args.command == "snapshot":
        return cmd_snapshot(args)
    if args.command == "attest-baseline":
        return cmd_attest_baseline(args)
    if args.command == "activate":
        return cmd_activate(args)
    if args.command == "verify":
        return cmd_verify(args)
    if args.command == "record":
        return cmd_record(args)
    if args.command == "restore":
        return cmd_restore(args)
    if args.command == "controlled-exception":
        return cmd_controlled_exception(args)
    if args.command == "controlled-finalize":
        return cmd_controlled_finalize(args)
    if args.command == "status":
        return cmd_status(args)
    raise SystemExit(f"unknown command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
