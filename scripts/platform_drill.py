#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

import yaml


CHECK_STATUSES = {"pending", "passed", "failed", "blocked", "not_applicable"}
DECISIONS = {"remove", "workaround", "accept-risk", "defer"}
RESTORE_STATUSES = {"pending", "restored", "exception"}
PHASES = {"baseline", "activation", "verification", "restore", "general"}
PROFILE_ALIASES = {
    "full-platform-runtime-drill": "environment-complete-runtime-drill",
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
        required_authorization_fields = {
            "required",
            "artifactType",
            "schemaRef",
            "policyRef",
            "targetProfileId",
            "targetProfileLifecycle",
            "maxRuns",
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
        for key in ("schemaRef", "policyRef", "targetProfileId"):
            if not str(authorization.get(key) or "").strip():
                raise SystemExit(f"{path} authorization.{key} must not be empty")

    scope = payload["scope"]
    if not isinstance(scope, dict):
        raise SystemExit(f"{path} field scope must be an object")
    source_repos = scope.get("sourceRepos") or []
    surfaces = scope.get("surfaces") or []
    if not isinstance(source_repos, list) or not source_repos:
        raise SystemExit(f"{path} scope.sourceRepos must be a non-empty list")
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
    evidence_template_path_value, evidence_template = evidence_template_payload(
        args.repo_root, profile_path, contract
    )
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
    run_dir = output_root(args.repo_root, args.output_root) / contract["id"] / run_id
    if run_dir.exists():
        raise SystemExit(f"run directory already exists: {run_dir}")
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
        }
    baseline_payload = build_baseline(contract, args.repo_root)
    dump_yaml(paths["run"], manifest)
    dump_yaml(paths["baseline"], baseline_payload)
    dump_yaml(paths["verification"], build_verification(contract))
    dump_yaml(paths["restore"], build_restore(contract))
    dump_yaml(
        paths["evidence"],
        build_evidence(contract, evidence_template, manifest, run_dir, baseline_payload),
    )
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


def cmd_attest_baseline(args: argparse.Namespace) -> int:
    _, paths, run_payload, baseline, _, _, evidence = load_run(args.run)
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
    if args.command == "status":
        return cmd_status(args)
    raise SystemExit(f"unknown command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
