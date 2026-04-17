#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml


ALLOWED_STATUSES = {"active", "suspended", "retired", "exception"}
PROFILE_PATH = Path("security/governed-ai-model-profiles.yaml")


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
    target = workspace_root / repo / rel_path
    if not target.exists():
        errors.append(f"{label}: missing referenced artifact {repo}/{rel_path}")


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
        f"profiles={len(payload.get('model_profiles', {}))}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
