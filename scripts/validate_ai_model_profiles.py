#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml


ALLOWED_STATUSES = {"active", "suspended", "retired", "exception"}
PROFILE_PATH = Path("security/governed-ai-model-profiles.yaml")
RUNTIME_ASSIST_CONTRACT_PATH = Path("security/governed-ai-runtime-assist-contract.yaml")
RUNTIME_CONTRACT_STATUSES = {"blocked", "planned", "active", "retired"}
REQUIRED_RUNTIME_AUDIT_FIELDS = {
    "event_time",
    "correlation_id",
    "caller_identity",
    "operator_identity",
    "approved_profile_id",
    "invocation_path",
    "purpose",
    "output_schema_ref",
    "policy_decision",
    "outcome",
    "operator_acceptance_state",
}


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def resolve_cross_repo_path(workspace_root: Path, ref: dict, *, label: str, errors: list[str]) -> None:
    repo = ref.get("repo")
    rel_path = ref.get("path")
    if not isinstance(repo, str) or not repo:
        errors.append(f"{label}: missing repo")
        return
    if not isinstance(rel_path, str) or not rel_path:
        errors.append(f"{label}: missing path")
        return
    repo_root = workspace_root / repo
    if not repo_root.exists():
        return
    target = repo_root / rel_path
    if not target.exists():
        errors.append(f"{label}: missing referenced artifact {repo}/{rel_path}")


def require_non_empty_mapping(value: object, *, label: str, errors: list[str]) -> dict | None:
    if not isinstance(value, dict) or not value:
        errors.append(f"{label} must be a non-empty mapping")
        return None
    return value


def require_non_empty_list(value: object, *, label: str, errors: list[str]) -> list | None:
    if not isinstance(value, list) or not value:
        errors.append(f"{label} must be a non-empty list")
        return None
    return value


def validate_runtime_assist_contract(
    repo_root: Path,
    workspace_root: Path,
    profiles: dict,
    errors: list[str],
) -> None:
    contract_path = repo_root / RUNTIME_ASSIST_CONTRACT_PATH
    if not contract_path.exists():
        errors.append(f"missing governed AI runtime-assist contract: {RUNTIME_ASSIST_CONTRACT_PATH}")
        return

    payload = load_yaml(contract_path)
    if payload.get("schema_version") != 1:
        errors.append(f"{RUNTIME_ASSIST_CONTRACT_PATH}: schema_version must be 1")

    contract = require_non_empty_mapping(
        payload.get("contract"),
        label=f"{RUNTIME_ASSIST_CONTRACT_PATH}: contract",
        errors=errors,
    )
    if contract is None:
        return

    if contract.get("owner_repo") != "platform-engineering":
        errors.append(f"{RUNTIME_ASSIST_CONTRACT_PATH}: contract.owner_repo must be platform-engineering")
    if contract.get("security_owner") != "security-architecture":
        errors.append(f"{RUNTIME_ASSIST_CONTRACT_PATH}: contract.security_owner must be security-architecture")
    if contract.get("status") not in RUNTIME_CONTRACT_STATUSES:
        errors.append(
            f"{RUNTIME_ASSIST_CONTRACT_PATH}: contract.status must be one of {sorted(RUNTIME_CONTRACT_STATUSES)}"
        )

    referenced_profiles = require_non_empty_list(
        contract.get("model_profiles"),
        label=f"{RUNTIME_ASSIST_CONTRACT_PATH}: contract.model_profiles",
        errors=errors,
    )
    if referenced_profiles:
        for profile_id in referenced_profiles:
            if not isinstance(profile_id, str) or not profile_id:
                errors.append(f"{RUNTIME_ASSIST_CONTRACT_PATH}: contract.model_profiles entries must be strings")
            elif profile_id not in profiles:
                errors.append(f"{RUNTIME_ASSIST_CONTRACT_PATH}: unknown referenced profile {profile_id}")

    selection = require_non_empty_mapping(
        contract.get("model_profile_selection"),
        label=f"{RUNTIME_ASSIST_CONTRACT_PATH}: contract.model_profile_selection",
        errors=errors,
    )
    if selection is not None:
        required_status = selection.get("required_profile_status_for_live_activation")
        if required_status != "active":
            errors.append(
                f"{RUNTIME_ASSIST_CONTRACT_PATH}: live activation must require active profile status"
            )
        for bool_field in (
            "require_profile_purpose_match",
            "require_allowed_caller_match",
            "require_allowed_data_scope_match",
            "require_output_schema_ref",
            "require_security_review_ref",
            "prohibit_pending_upstream_model_for_live_activation",
        ):
            if selection.get(bool_field) is not True:
                errors.append(f"{RUNTIME_ASSIST_CONTRACT_PATH}: {bool_field} must be true")

    invocation = require_non_empty_mapping(
        contract.get("invocation_boundary"),
        label=f"{RUNTIME_ASSIST_CONTRACT_PATH}: contract.invocation_boundary",
        errors=errors,
    )
    if invocation is not None:
        if invocation.get("required_path") != "governed-ai-gateway":
            errors.append(f"{RUNTIME_ASSIST_CONTRACT_PATH}: invocation_boundary.required_path must be governed-ai-gateway")
        if invocation.get("direct_provider_access_allowed") is not False:
            errors.append(f"{RUNTIME_ASSIST_CONTRACT_PATH}: direct provider access must be false")
        if invocation.get("provider_credentials_allowed_in_consumers") is not False:
            errors.append(
                f"{RUNTIME_ASSIST_CONTRACT_PATH}: provider credentials must not be allowed in consumers"
            )
        require_non_empty_list(
            invocation.get("required_controls"),
            label=f"{RUNTIME_ASSIST_CONTRACT_PATH}: invocation_boundary.required_controls",
            errors=errors,
        )

    approval = require_non_empty_mapping(
        contract.get("approval_boundary"),
        label=f"{RUNTIME_ASSIST_CONTRACT_PATH}: contract.approval_boundary",
        errors=errors,
    )
    if approval is not None:
        if approval.get("human_approval_required") is not True:
            errors.append(f"{RUNTIME_ASSIST_CONTRACT_PATH}: human approval must be required")
        if approval.get("model_output_mutates_canonical_state") is not False:
            errors.append(
                f"{RUNTIME_ASSIST_CONTRACT_PATH}: model output must not mutate canonical state directly"
            )
        require_non_empty_list(
            approval.get("required_acceptance_evidence"),
            label=f"{RUNTIME_ASSIST_CONTRACT_PATH}: approval_boundary.required_acceptance_evidence",
            errors=errors,
        )

    audit = require_non_empty_mapping(
        contract.get("audit_minimum"),
        label=f"{RUNTIME_ASSIST_CONTRACT_PATH}: contract.audit_minimum",
        errors=errors,
    )
    if audit is not None:
        audit_fields = audit.get("required_fields")
        if not isinstance(audit_fields, list):
            errors.append(f"{RUNTIME_ASSIST_CONTRACT_PATH}: audit_minimum.required_fields must be a list")
        else:
            missing = sorted(REQUIRED_RUNTIME_AUDIT_FIELDS.difference(audit_fields))
            if missing:
                errors.append(
                    f"{RUNTIME_ASSIST_CONTRACT_PATH}: audit_minimum.required_fields missing {missing}"
                )

    for field_name in ("activation_gates", "environment_control_gates", "rollback_gates"):
        entries = require_non_empty_list(
            contract.get(field_name),
            label=f"{RUNTIME_ASSIST_CONTRACT_PATH}: contract.{field_name}",
            errors=errors,
        )
        if not entries:
            continue
        for idx, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                errors.append(f"{RUNTIME_ASSIST_CONTRACT_PATH}: {field_name} entry #{idx} must be a mapping")
                continue
            if "id" not in entry and "environment" not in entry:
                errors.append(f"{RUNTIME_ASSIST_CONTRACT_PATH}: {field_name} entry #{idx} missing id or environment")

    for field_name in ("security_review_refs", "related_artifacts"):
        refs = require_non_empty_list(
            contract.get(field_name),
            label=f"{RUNTIME_ASSIST_CONTRACT_PATH}: contract.{field_name}",
            errors=errors,
        )
        if not refs:
            continue
        for idx, ref in enumerate(refs, start=1):
            if not isinstance(ref, dict):
                errors.append(f"{RUNTIME_ASSIST_CONTRACT_PATH}: {field_name} entry #{idx} must be a mapping")
                continue
            resolve_cross_repo_path(
                workspace_root,
                ref,
                label=f"{RUNTIME_ASSIST_CONTRACT_PATH}: {field_name} entry #{idx}",
                errors=errors,
            )


def validate(repo_root: Path) -> list[str]:
    errors: list[str] = []
    registry_path = repo_root / PROFILE_PATH
    if not registry_path.exists():
        return [f"missing governed AI model profile registry: {PROFILE_PATH}"]

    workspace_root = repo_root.parent
    payload = load_yaml(registry_path)
    if payload.get("schema_version") != 1:
        errors.append(f"{PROFILE_PATH}: schema_version must be 1")

    registry = payload.get("registry")
    if not isinstance(registry, dict):
        errors.append(f"{PROFILE_PATH}: registry must be a mapping")
    else:
        if registry.get("owner_repo") != "platform-engineering":
            errors.append(f"{PROFILE_PATH}: registry.owner_repo must be platform-engineering")
        if registry.get("security_owner") != "security-architecture":
            errors.append(f"{PROFILE_PATH}: registry.security_owner must be security-architecture")
        review_ref = registry.get("review_ref")
        if not isinstance(review_ref, dict):
            errors.append(f"{PROFILE_PATH}: registry.review_ref must be a mapping")
        else:
            resolve_cross_repo_path(
                workspace_root,
                review_ref,
                label=f"{PROFILE_PATH}: registry.review_ref",
                errors=errors,
            )

    profiles = payload.get("model_profiles")
    if not isinstance(profiles, dict) or not profiles:
        errors.append(f"{PROFILE_PATH}: model_profiles must be a non-empty mapping")
        return errors

    for profile_id, profile in profiles.items():
        if not isinstance(profile, dict):
            errors.append(f"{PROFILE_PATH}: {profile_id} must be a mapping")
            continue
        status = profile.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(
                f"{PROFILE_PATH}: {profile_id} status must be one of {sorted(ALLOWED_STATUSES)}"
            )
        for field_name in ("purpose", "invocation_path", "provider", "upstream_model", "notes"):
            value = profile.get(field_name)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{PROFILE_PATH}: {profile_id} missing non-empty {field_name}")
        allowed_callers = profile.get("allowed_callers")
        if not isinstance(allowed_callers, list) or not allowed_callers or any(
            not isinstance(item, str) or "/" not in item for item in allowed_callers
        ):
            errors.append(
                f"{PROFILE_PATH}: {profile_id} allowed_callers must be a non-empty list of repo/path strings"
            )
        allowed_data_scope = profile.get("allowed_data_scope")
        if not isinstance(allowed_data_scope, list) or not allowed_data_scope or any(
            not isinstance(item, str) or not item.strip() for item in allowed_data_scope
        ):
            errors.append(
                f"{PROFILE_PATH}: {profile_id} allowed_data_scope must be a non-empty list of strings"
            )
        for bool_field in ("human_approval_required", "direct_provider_access_allowed"):
            if not isinstance(profile.get(bool_field), bool):
                errors.append(f"{PROFILE_PATH}: {profile_id} {bool_field} must be boolean")

        output_schema_ref = profile.get("output_schema_ref")
        if not isinstance(output_schema_ref, dict):
            errors.append(f"{PROFILE_PATH}: {profile_id} output_schema_ref must be a mapping")
        else:
            resolve_cross_repo_path(
                workspace_root,
                output_schema_ref,
                label=f"{PROFILE_PATH}: {profile_id} output_schema_ref",
                errors=errors,
            )

        security_review_ref = profile.get("security_review_ref")
        if not isinstance(security_review_ref, dict):
            errors.append(f"{PROFILE_PATH}: {profile_id} security_review_ref must be a mapping")
        else:
            resolve_cross_repo_path(
                workspace_root,
                security_review_ref,
                label=f"{PROFILE_PATH}: {profile_id} security_review_ref",
                errors=errors,
            )

        if status == "active":
            if profile.get("direct_provider_access_allowed"):
                errors.append(
                    f"{PROFILE_PATH}: {profile_id} active governed profile must not allow direct provider access"
                )
            if profile.get("upstream_model") == "pending-selection":
                errors.append(
                    f"{PROFILE_PATH}: {profile_id} active profile must not keep upstream_model as pending-selection"
                )

    validate_runtime_assist_contract(repo_root, workspace_root, profiles, errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate governed AI model profile registry.")
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="platform-engineering repository root",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    errors = validate(repo_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    payload = load_yaml(repo_root / PROFILE_PATH)
    print(
        "governed AI model profiles valid: "
        f"profiles={len(payload.get('model_profiles', {}))} "
        f"runtime_assist_contract={RUNTIME_ASSIST_CONTRACT_PATH}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
