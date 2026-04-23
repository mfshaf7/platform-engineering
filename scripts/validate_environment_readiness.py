#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


DEFAULT_CONFIGS = {
    "stage": Path("environments/stage/environment-readiness.yaml"),
    "prod": Path("environments/prod/environment-readiness.yaml"),
}
STATUS_TOKEN_RE = re.compile(r"(?:^| )(?P<key>[a-z_]+)=(?P<value>[^ ]+)")


@dataclass
class RequirementResult:
    requirement_id: str
    kind: str
    path: str
    accepted_statuses: list[str]
    actual_status: str
    ok: bool
    summary: str


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected a YAML mapping")
    return data


def relative_label(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def status_token(text: str, key: str) -> str | None:
    for match in STATUS_TOKEN_RE.finditer(text.strip()):
        if match.group("key") == key:
            return match.group("value")
    return None


def summarize_command_failure(run: subprocess.CompletedProcess[str]) -> str:
    parts: list[str] = [f"command exited {run.returncode}"]
    stderr = (run.stderr or "").strip()
    stdout = (run.stdout or "").strip()
    if stderr:
        parts.append(stderr.splitlines()[-1])
    elif stdout:
        parts.append(stdout.splitlines()[-1])
    return "; ".join(parts)


def run_python(repo_root: Path, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def ensure_note(record: dict, errors: list[str], context: str) -> None:
    note = record.get("note")
    if not isinstance(note, str) or not note.strip():
        errors.append(f"{context}: note is required")


def ensure_existing_path(repo_root: Path, raw_path: str | None, errors: list[str], context: str) -> Path | None:
    if not raw_path:
        errors.append(f"{context}: path is required")
        return None
    path = repo_root / raw_path
    if not path.exists():
        errors.append(f"{context}: missing referenced path {raw_path}")
        return None
    return path


def candidate_required_checks(record: dict) -> list[str]:
    if not isinstance(record, dict):
        return []
    candidate_ref = record.get("candidateRef") or {}
    environment_contract_ref = record.get("environmentContractRef") or {}
    required = list(candidate_ref.get("requiredChecks") or [])
    required.extend(environment_contract_ref.get("requiredChecks") or [])
    return sorted(dict.fromkeys(required))


def verification_results(record: dict, errors: list[str], context: str) -> dict[str, str]:
    results: dict[str, str] = {}
    for entry in record.get("checks") or []:
        if not isinstance(entry, dict):
            errors.append(f"{context}: check entries must be mappings")
            continue
        check_id = entry.get("id")
        status = entry.get("status")
        if not check_id or not status:
            errors.append(f"{context}: check entries require id and status")
            continue
        results[str(check_id)] = str(status)
    return results


def validate_candidate_ref(repo_root: Path, candidate_ref: dict, errors: list[str], context: str) -> None:
    path = ensure_existing_path(repo_root, candidate_ref.get("path"), errors, context)
    if path is None:
        return
    candidate = load_yaml(path)
    expected_status = candidate_ref.get("status")
    actual_status = candidate.get("status")
    if expected_status is not None and actual_status != expected_status:
        errors.append(
            f"{context}: candidate status mismatch, expected {expected_status!r} but {relative_label(path, repo_root)} is {actual_status!r}"
        )


def validate_environment_contract_ref(repo_root: Path, contract_ref: dict, errors: list[str], context: str) -> None:
    found = False
    path = contract_ref.get("path")
    if path:
        found = True
        ensure_existing_path(repo_root, path, errors, context)
    for key in ("deploymentContractRefs", "supportingContractRefs"):
        for index, entry in enumerate(contract_ref.get(key) or []):
            found = True
            if not isinstance(entry, dict):
                errors.append(f"{context}: {key}[{index}] must be a mapping")
                continue
            ensure_existing_path(repo_root, entry.get("path"), errors, f"{context} {key}[{index}]")
    if not found:
        errors.append(f"{context}: no contract paths were declared")


def validate_verification_record(repo_root: Path, path: Path) -> tuple[dict, list[str]]:
    errors: list[str] = []
    record = load_yaml(path)
    context = relative_label(path, repo_root)
    status = record.get("status")
    if not isinstance(status, str) or not status:
        errors.append(f"{context}: status is required")
    ensure_note(record, errors, context)
    candidate_ref = record.get("candidateRef")
    if isinstance(candidate_ref, dict) and candidate_ref:
        validate_candidate_ref(repo_root, candidate_ref, errors, f"{context} candidateRef")
    environment_contract_ref = record.get("environmentContractRef")
    if isinstance(environment_contract_ref, dict) and environment_contract_ref:
        validate_environment_contract_ref(
            repo_root,
            environment_contract_ref,
            errors,
            f"{context} environmentContractRef",
        )
    if status == "recorded":
        for field in ("verifiedAt", "verifiedBy", "evidenceRef"):
            if not record.get(field):
                errors.append(f"{context}: {field} is required when status is recorded")
        results = verification_results(record, errors, context)
        if not results:
            errors.append(f"{context}: recorded verification must include check results")
        missing = [check_id for check_id in candidate_required_checks(record) if check_id not in results]
        if missing:
            errors.append(
                f"{context}: recorded verification is missing required checks: {', '.join(missing)}"
            )
    return record, errors


def validate_verification_ref(
    repo_root: Path,
    verification_ref: dict,
    errors: list[str],
    context: str,
) -> tuple[dict | None, str]:
    path = ensure_existing_path(repo_root, verification_ref.get("path"), errors, context)
    if path is None:
        return None, "missing"
    verification_record, verification_errors = validate_verification_record(repo_root, path)
    errors.extend(verification_errors)
    actual_status = str(verification_record.get("status") or "unset")
    expected_status = verification_ref.get("status")
    if expected_status is not None and actual_status != expected_status:
        errors.append(
            f"{context}: verification status mismatch, expected {expected_status!r} but {relative_label(path, repo_root)} is {actual_status!r}"
        )
    expected_verified_at = verification_ref.get("verifiedAt")
    if expected_verified_at is not None and verification_record.get("verifiedAt") != expected_verified_at:
        errors.append(
            f"{context}: verification verifiedAt mismatch, expected {expected_verified_at!r} but found {verification_record.get('verifiedAt')!r}"
        )
    return verification_record, actual_status


def evaluate_stage_readiness_record(repo_root: Path, requirement: dict) -> RequirementResult:
    path = repo_root / requirement["path"]
    record = load_yaml(path)
    errors: list[str] = []
    context = relative_label(path, repo_root)
    actual_status = str(record.get("status") or "unset")
    ensure_note(record, errors, context)
    candidate_ref = record.get("candidateRef") or {}
    if not isinstance(candidate_ref, dict):
        errors.append(f"{context}: candidateRef must be a mapping")
    else:
        validate_candidate_ref(repo_root, candidate_ref, errors, f"{context} candidateRef")
    verification_ref = record.get("verificationRef") or {}
    if not isinstance(verification_ref, dict):
        errors.append(f"{context}: verificationRef must be a mapping")
        verification_status = "missing"
    else:
        _, verification_status = validate_verification_ref(
            repo_root,
            verification_ref,
            errors,
            f"{context} verificationRef",
        )
    if actual_status == "approved":
        for field in ("approvedAt", "approvedBy"):
            if not record.get(field):
                errors.append(f"{context}: {field} is required when status is approved")
        if verification_status != "recorded":
            errors.append(
                f"{context}: approved stage readiness requires recorded verification, found {verification_status!r}"
            )
    if actual_status not in requirement["acceptedStatuses"]:
        errors.append(
            f"{context}: status {actual_status!r} is not acceptable; expected one of {', '.join(requirement['acceptedStatuses'])}"
        )
    ok = actual_status in requirement["acceptedStatuses"] and not errors
    summary = "; ".join(errors) if errors else f"status {actual_status!r} is acceptable"
    return RequirementResult(
        requirement_id=requirement["id"],
        kind=requirement["kind"],
        path=requirement["path"],
        accepted_statuses=list(requirement["acceptedStatuses"]),
        actual_status=actual_status,
        ok=ok,
        summary=summary,
    )


def evaluate_support_readiness_record(repo_root: Path, requirement: dict) -> RequirementResult:
    path = repo_root / requirement["path"]
    record = load_yaml(path)
    errors: list[str] = []
    context = relative_label(path, repo_root)
    actual_status = str(record.get("status") or "unset")
    ensure_note(record, errors, context)
    environment_contract_ref = record.get("environmentContractRef") or {}
    if not isinstance(environment_contract_ref, dict):
        errors.append(f"{context}: environmentContractRef must be a mapping")
    else:
        validate_environment_contract_ref(
            repo_root,
            environment_contract_ref,
            errors,
            f"{context} environmentContractRef",
        )
    verification_ref = record.get("verificationRef") or {}
    if not isinstance(verification_ref, dict):
        errors.append(f"{context}: verificationRef must be a mapping")
        verification_status = "missing"
    else:
        _, verification_status = validate_verification_ref(
            repo_root,
            verification_ref,
            errors,
            f"{context} verificationRef",
        )
    if actual_status == "approved":
        for field in ("assessedAt", "assessedBy"):
            if not record.get(field):
                errors.append(f"{context}: {field} is required when status is approved")
        if verification_status != "recorded":
            errors.append(
                f"{context}: approved support readiness requires recorded verification, found {verification_status!r}"
            )
    if actual_status not in requirement["acceptedStatuses"]:
        errors.append(
            f"{context}: status {actual_status!r} is not acceptable; expected one of {', '.join(requirement['acceptedStatuses'])}"
        )
    ok = actual_status in requirement["acceptedStatuses"] and not errors
    summary = "; ".join(errors) if errors else f"status {actual_status!r} is acceptable"
    return RequirementResult(
        requirement_id=requirement["id"],
        kind=requirement["kind"],
        path=requirement["path"],
        accepted_statuses=list(requirement["acceptedStatuses"]),
        actual_status=actual_status,
        ok=ok,
        summary=summary,
    )


def evaluate_prod_verification_record(repo_root: Path, requirement: dict) -> RequirementResult:
    path = repo_root / requirement["path"]
    record, errors = validate_verification_record(repo_root, path)
    context = relative_label(path, repo_root)
    actual_status = str(record.get("status") or "unset")
    if actual_status not in {"recorded", "inactive", "pending", "rejected"}:
        errors.append(f"{context}: unexpected prod verification status {actual_status!r}")
    if actual_status not in requirement["acceptedStatuses"]:
        errors.append(
            f"{context}: status {actual_status!r} is not acceptable; expected one of {', '.join(requirement['acceptedStatuses'])}"
        )
    ok = actual_status in requirement["acceptedStatuses"] and not errors
    summary = "; ".join(errors) if errors else f"status {actual_status!r} is acceptable"
    return RequirementResult(
        requirement_id=requirement["id"],
        kind=requirement["kind"],
        path=requirement["path"],
        accepted_statuses=list(requirement["acceptedStatuses"]),
        actual_status=actual_status,
        ok=ok,
        summary=summary,
    )


def evaluate_openclaw_stage_readiness(repo_root: Path, requirement: dict) -> RequirementResult:
    script = repo_root / "products/openclaw/scripts/gateway_release.py"
    status_run = run_python(repo_root, script, "readiness", "status", "--repo-root", str(repo_root))
    actual_status = status_token(status_run.stdout, "status") or "unknown"
    errors: list[str] = []
    if status_run.returncode != 0:
        errors.append(summarize_command_failure(status_run))
    if actual_status not in requirement["acceptedStatuses"]:
        errors.append(
            f"OpenClaw stage readiness is {actual_status!r}; expected one of {', '.join(requirement['acceptedStatuses'])}"
        )
    validate_run = run_python(repo_root, script, "readiness", "validate", "--repo-root", str(repo_root))
    if validate_run.returncode != 0:
        errors.append(summarize_command_failure(validate_run))
    ok = not errors
    summary = "; ".join(errors) if errors else "OpenClaw stage readiness validate passed"
    return RequirementResult(
        requirement_id=requirement["id"],
        kind=requirement["kind"],
        path="products/openclaw/scripts/gateway_release.py readiness",
        accepted_statuses=list(requirement["acceptedStatuses"]),
        actual_status=actual_status,
        ok=ok,
        summary=summary,
    )


def evaluate_openclaw_prod_verification(repo_root: Path, requirement: dict) -> RequirementResult:
    script = repo_root / "products/openclaw/scripts/gateway_release.py"
    status_run = run_python(
        repo_root,
        script,
        "prod-verification",
        "status",
        "--repo-root",
        str(repo_root),
    )
    actual_status = status_token(status_run.stdout, "status") or "unknown"
    lifecycle_state = status_token(status_run.stdout, "lifecycle_state") or "unknown"
    errors: list[str] = []
    if status_run.returncode != 0:
        errors.append(summarize_command_failure(status_run))
    if actual_status not in requirement["acceptedStatuses"]:
        errors.append(
            f"OpenClaw prod verification is {actual_status!r}; expected one of {', '.join(requirement['acceptedStatuses'])}"
        )
    if lifecycle_state == "live":
        validate_run = run_python(
            repo_root,
            script,
            "prod-verification",
            "validate",
            "--repo-root",
            str(repo_root),
        )
        if validate_run.returncode != 0:
            errors.append(summarize_command_failure(validate_run))
    elif actual_status != "inactive":
        errors.append(
            f"OpenClaw prod lifecycle is {lifecycle_state!r}; prod verification should be inactive while the lifecycle is not live"
        )
    ok = not errors
    summary = "; ".join(errors) if errors else f"OpenClaw prod verification is acceptable for lifecycle {lifecycle_state!r}"
    return RequirementResult(
        requirement_id=requirement["id"],
        kind=requirement["kind"],
        path="products/openclaw/scripts/gateway_release.py prod-verification",
        accepted_statuses=list(requirement["acceptedStatuses"]),
        actual_status=actual_status,
        ok=ok,
        summary=summary,
    )


def evaluate_requirement(repo_root: Path, requirement: dict) -> RequirementResult:
    kind = requirement.get("kind")
    if kind == "stage-readiness-record":
        return evaluate_stage_readiness_record(repo_root, requirement)
    if kind == "support-readiness-record":
        return evaluate_support_readiness_record(repo_root, requirement)
    if kind == "prod-verification-record":
        return evaluate_prod_verification_record(repo_root, requirement)
    if kind == "openclaw-stage-readiness":
        return evaluate_openclaw_stage_readiness(repo_root, requirement)
    if kind == "openclaw-prod-verification":
        return evaluate_openclaw_prod_verification(repo_root, requirement)
    raise SystemExit(f"unknown requirement kind {kind!r}")


def load_config(repo_root: Path, environment: str, override: Path | None) -> tuple[Path, dict]:
    config_path = override or (repo_root / DEFAULT_CONFIGS[environment])
    if not config_path.is_absolute():
        config_path = repo_root / config_path
    config = load_yaml(config_path)
    expected_environment = config.get("environment")
    if expected_environment != environment:
        raise SystemExit(
            f"{config_path}: environment {expected_environment!r} does not match requested environment {environment!r}"
        )
    requirements = config.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise SystemExit(f"{config_path}: requirements must be a non-empty list")
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            raise SystemExit(f"{config_path}: requirements[{index}] must be a mapping")
        for field in ("id", "kind", "acceptedStatuses"):
            if field not in requirement:
                raise SystemExit(f"{config_path}: requirements[{index}] is missing {field}")
        accepted_statuses = requirement.get("acceptedStatuses")
        if not isinstance(accepted_statuses, list) or not accepted_statuses:
            raise SystemExit(
                f"{config_path}: requirements[{index}].acceptedStatuses must be a non-empty list"
            )
        if requirement["kind"] in {"stage-readiness-record", "support-readiness-record", "prod-verification-record"}:
            if "path" not in requirement:
                raise SystemExit(f"{config_path}: requirements[{index}] is missing path")
    return config_path, config


def print_report(environment: str, config_path: Path, results: list[RequirementResult]) -> None:
    passed = sum(1 for result in results if result.ok)
    overall_status = "ready" if passed == len(results) else "not-ready"
    print(
        f"environment={environment} overall_status={overall_status} satisfied={passed}/{len(results)} "
        f"config={config_path}"
    )
    for result in results:
        marker = "PASS" if result.ok else "FAIL"
        accepted = ",".join(result.accepted_statuses)
        print(
            f"{marker} id={result.requirement_id} kind={result.kind} actual_status={result.actual_status} "
            f"accepted_statuses={accepted} path={result.path} summary={result.summary}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assess aggregate fail-closed stage or prod environment readiness."
    )
    parser.add_argument("action", choices=("status", "validate"))
    parser.add_argument("environment", choices=tuple(DEFAULT_CONFIGS))
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="platform-engineering repository root",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="override environment-readiness config path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    config_path, config = load_config(repo_root, args.environment, args.config)
    results = [evaluate_requirement(repo_root, requirement) for requirement in config["requirements"]]
    print_report(args.environment, config_path, results)
    if args.action == "validate" and any(not result.ok for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
