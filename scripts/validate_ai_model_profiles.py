#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml


ALLOWED_STATUSES = {
    "active",
    "selected-not-active",
    "suspended",
    "retired",
    "exception",
}
MODEL_BINDING_STATUSES = {"active", "selected-not-active", "retired"}
PROFILE_PATH = Path("security/governed-ai-model-profiles.yaml")
RUNTIME_ASSIST_CONTRACT_PATH = Path("security/governed-ai-runtime-assist-contract.yaml")
ACCESS_PLANE_PATH = Path("security/governed-ai-access-plane.yaml")
DEVINT_EGRESS_POLICY_PATH = Path("security/governed-ai-devint-egress-policy.yaml")
RUNTIME_CONTRACT_STATUSES = {"blocked", "planned", "active", "retired"}
ACCESS_PLANE_STATUSES = {"source-defined", "devint-runtime-defined", "active", "retired"}
DEVINT_EGRESS_POLICY_STATUSES = {"source-defined", "devint-runtime-defined", "active", "retired"}
PROVIDER_ROUTE_STATUSES = {"selected-not-active", "active", "retired"}
REQUIRED_RUNTIME_AUDIT_FIELDS = {
    "event_time",
    "correlation_id",
    "caller_identity",
    "operator_identity",
    "approved_profile_id",
    "invocation_path",
    "upstream_provider",
    "provider_route",
    "upstream_model",
    "upstream_model_digest",
    "provider_runtime_version",
    "prompt_version",
    "provider_schema_valid",
    "provider_latency_ms",
    "provider_usage",
    "purpose",
    "task_kind",
    "task_contract_ref",
    "task_contract_version",
    "output_schema_ref",
    "policy_decision",
    "outcome",
    "operator_acceptance_state",
}
REQUIRED_CALLER_IDENTITY_FIELDS = {
    "caller_id",
    "caller_repo",
    "caller_workflow",
    "decision_or_correlation_id",
    "requested_profile_id",
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

    consumers = require_non_empty_mapping(
        contract.get("consumers"),
        label=f"{RUNTIME_ASSIST_CONTRACT_PATH}: contract.consumers",
        errors=errors,
    )
    if consumers is not None:
        allowed_callers = consumers.get("allowed_callers")
        registered_not_active_callers = consumers.get("registered_not_active_callers")
        if not isinstance(allowed_callers, list) or any(
            not isinstance(caller, str) or not caller for caller in (allowed_callers or [])
        ):
            errors.append(
                f"{RUNTIME_ASSIST_CONTRACT_PATH}: consumers.allowed_callers must be a string list"
            )
            allowed_callers = []
        if not isinstance(registered_not_active_callers, list) or any(
            not isinstance(caller, str) or not caller
            for caller in (registered_not_active_callers or [])
        ):
            errors.append(
                f"{RUNTIME_ASSIST_CONTRACT_PATH}: consumers.registered_not_active_callers "
                "must be a string list"
            )
            registered_not_active_callers = []
        overlap = sorted(set(allowed_callers).intersection(registered_not_active_callers))
        if overlap:
            errors.append(
                f"{RUNTIME_ASSIST_CONTRACT_PATH}: callers cannot be both active and "
                f"registered-not-active: {overlap}"
            )
        expected_allowed = sorted(
            caller
            for profile in profiles.values()
            if isinstance(profile, dict) and profile.get("status") == "active"
            for caller in (profile.get("allowed_callers") or [])
        )
        expected_registered = sorted(
            caller
            for profile in profiles.values()
            if isinstance(profile, dict)
            and profile.get("status") == "selected-not-active"
            for caller in (profile.get("allowed_callers") or [])
        )
        if sorted(allowed_callers) != expected_allowed:
            errors.append(
                f"{RUNTIME_ASSIST_CONTRACT_PATH}: consumers.allowed_callers must match "
                "active profile callers exactly"
            )
        if sorted(registered_not_active_callers) != expected_registered:
            errors.append(
                f"{RUNTIME_ASSIST_CONTRACT_PATH}: consumers.registered_not_active_callers "
                "must match selected-not-active profile callers exactly"
            )

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
            "require_task_contract_match",
            "require_security_review_ref",
            "require_provider_route_match",
            "require_upstream_model_allowlist_match",
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
        elif any(not isinstance(field, str) or not field for field in audit_fields):
            errors.append(
                f"{RUNTIME_ASSIST_CONTRACT_PATH}: audit_minimum.required_fields entries must be non-empty strings"
            )
        else:
            missing = sorted(REQUIRED_RUNTIME_AUDIT_FIELDS.difference(audit_fields))
            if missing:
                errors.append(
                    f"{RUNTIME_ASSIST_CONTRACT_PATH}: audit_minimum.required_fields missing {missing}"
                )

    gate_required_keys = {
        "activation_gates": "id",
        "environment_control_gates": "environment",
        "rollback_gates": "id",
    }
    for field_name, required_key in gate_required_keys.items():
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
            if not isinstance(entry.get(required_key), str) or not entry.get(required_key):
                errors.append(
                    f"{RUNTIME_ASSIST_CONTRACT_PATH}: {field_name} entry #{idx} missing non-empty {required_key}"
                )

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


def validate_devint_egress_policy(repo_root: Path, errors: list[str]) -> dict | None:
    policy_path = repo_root / DEVINT_EGRESS_POLICY_PATH
    if not policy_path.exists():
        errors.append(f"missing governed AI devint egress policy: {DEVINT_EGRESS_POLICY_PATH}")
        return None

    payload = load_yaml(policy_path)
    if payload.get("schema_version") != 1:
        errors.append(f"{DEVINT_EGRESS_POLICY_PATH}: schema_version must be 1")

    policy = require_non_empty_mapping(
        payload.get("devint_egress_policy"),
        label=f"{DEVINT_EGRESS_POLICY_PATH}: devint_egress_policy",
        errors=errors,
    )
    if policy is None:
        return None

    if policy.get("owner_repo") != "platform-engineering":
        errors.append(f"{DEVINT_EGRESS_POLICY_PATH}: owner_repo must be platform-engineering")
    if policy.get("status") not in DEVINT_EGRESS_POLICY_STATUSES:
        errors.append(
            f"{DEVINT_EGRESS_POLICY_PATH}: status must be one of {sorted(DEVINT_EGRESS_POLICY_STATUSES)}"
        )

    applies_to = require_non_empty_mapping(
        policy.get("applies_to"),
        label=f"{DEVINT_EGRESS_POLICY_PATH}: applies_to",
        errors=errors,
    )
    if applies_to is not None and applies_to.get("lane") != "dev-integration":
        errors.append(f"{DEVINT_EGRESS_POLICY_PATH}: applies_to.lane must be dev-integration")

    invocation_path = require_non_empty_mapping(
        policy.get("required_invocation_path"),
        label=f"{DEVINT_EGRESS_POLICY_PATH}: required_invocation_path",
        errors=errors,
    )
    if invocation_path is not None:
        if invocation_path.get("service_name") != "governed-ai-gateway":
            errors.append(f"{DEVINT_EGRESS_POLICY_PATH}: required_invocation_path.service_name must be governed-ai-gateway")
        namespace = invocation_path.get("namespace") or invocation_path.get("namespace_pattern")
        if not isinstance(namespace, str) or not namespace:
            errors.append(f"{DEVINT_EGRESS_POLICY_PATH}: required_invocation_path namespace or namespace_pattern must be a non-empty string")

    proof_profile = policy.get("proof_profile")
    if policy.get("status") == "devint-runtime-defined":
        profile = require_non_empty_mapping(
            proof_profile,
            label=f"{DEVINT_EGRESS_POLICY_PATH}: proof_profile",
            errors=errors,
        )
        if profile is not None:
            profile_path = profile.get("profile_path")
            if not isinstance(profile_path, str) or not profile_path:
                errors.append(f"{DEVINT_EGRESS_POLICY_PATH}: proof_profile.profile_path must be non-empty")
            elif not (repo_root / profile_path).exists():
                errors.append(f"{DEVINT_EGRESS_POLICY_PATH}: proof_profile.profile_path does not exist: {profile_path}")
            if profile.get("profile_id") != "governed-ai-gateway":
                errors.append(f"{DEVINT_EGRESS_POLICY_PATH}: proof_profile.profile_id must be governed-ai-gateway")

    consumer_policy = require_non_empty_mapping(
        policy.get("consumer_policy"),
        label=f"{DEVINT_EGRESS_POLICY_PATH}: consumer_policy",
        errors=errors,
    )
    if consumer_policy is not None:
        if consumer_policy.get("default_egress") != "deny":
            errors.append(f"{DEVINT_EGRESS_POLICY_PATH}: consumer_policy.default_egress must be deny")
        if consumer_policy.get("allow_to_governed_gateway") is not True:
            errors.append(f"{DEVINT_EGRESS_POLICY_PATH}: consumer_policy.allow_to_governed_gateway must be true")
        if consumer_policy.get("direct_provider_egress_allowed") is not False:
            errors.append(f"{DEVINT_EGRESS_POLICY_PATH}: direct provider egress must be false")

    for field_name in (
        "denied_provider_destinations",
        "required_kubernetes_controls",
        "evidence_required_before_activation",
    ):
        entries = require_non_empty_list(
            policy.get(field_name),
            label=f"{DEVINT_EGRESS_POLICY_PATH}: {field_name}",
            errors=errors,
        )
        if entries and any(not isinstance(entry, str) or not entry for entry in entries):
            errors.append(f"{DEVINT_EGRESS_POLICY_PATH}: {field_name} entries must be non-empty strings")

    return policy


def validate_access_plane_contract(
    repo_root: Path,
    workspace_root: Path,
    profiles: dict,
    errors: list[str],
) -> None:
    access_plane_path = repo_root / ACCESS_PLANE_PATH
    if not access_plane_path.exists():
        errors.append(f"missing governed AI access-plane contract: {ACCESS_PLANE_PATH}")
        return

    egress_policy = validate_devint_egress_policy(repo_root, errors)
    payload = load_yaml(access_plane_path)
    if payload.get("schema_version") != 1:
        errors.append(f"{ACCESS_PLANE_PATH}: schema_version must be 1")

    access_plane = require_non_empty_mapping(
        payload.get("access_plane"),
        label=f"{ACCESS_PLANE_PATH}: access_plane",
        errors=errors,
    )
    if access_plane is None:
        return

    if access_plane.get("id") != "governed-ai-gateway":
        errors.append(f"{ACCESS_PLANE_PATH}: access_plane.id must be governed-ai-gateway")
    if access_plane.get("status") not in ACCESS_PLANE_STATUSES:
        errors.append(f"{ACCESS_PLANE_PATH}: access_plane.status must be one of {sorted(ACCESS_PLANE_STATUSES)}")
    if access_plane.get("owner_repo") != "platform-engineering":
        errors.append(f"{ACCESS_PLANE_PATH}: access_plane.owner_repo must be platform-engineering")
    if access_plane.get("security_owner") != "security-architecture":
        errors.append(f"{ACCESS_PLANE_PATH}: access_plane.security_owner must be security-architecture")

    for ref_field in ("profile_registry_ref", "runtime_assist_contract_ref", "devint_enforcement_ref"):
        ref = access_plane.get(ref_field)
        if not isinstance(ref, dict):
            errors.append(f"{ACCESS_PLANE_PATH}: access_plane.{ref_field} must be a mapping")
        else:
            resolve_cross_repo_path(
                workspace_root,
                ref,
                label=f"{ACCESS_PLANE_PATH}: access_plane.{ref_field}",
                errors=errors,
            )

    allowed_profiles = require_non_empty_list(
        access_plane.get("allowed_profiles"),
        label=f"{ACCESS_PLANE_PATH}: access_plane.allowed_profiles",
        errors=errors,
    )
    if allowed_profiles:
        for profile_id in allowed_profiles:
            if not isinstance(profile_id, str) or not profile_id:
                errors.append(f"{ACCESS_PLANE_PATH}: allowed_profiles entries must be strings")
            elif profile_id not in profiles:
                errors.append(f"{ACCESS_PLANE_PATH}: unknown allowed profile {profile_id}")

    provider_routes = require_non_empty_list(
        access_plane.get("provider_routes"),
        label=f"{ACCESS_PLANE_PATH}: access_plane.provider_routes",
        errors=errors,
    )
    provider_routes_by_id: dict[str, dict] = {}
    if provider_routes:
        for idx, route in enumerate(provider_routes, start=1):
            if not isinstance(route, dict):
                errors.append(f"{ACCESS_PLANE_PATH}: provider_routes entry #{idx} must be a mapping")
                continue
            route_id = route.get("route_id")
            if not isinstance(route_id, str) or not route_id:
                errors.append(f"{ACCESS_PLANE_PATH}: provider_routes entry #{idx} missing route_id")
                continue
            if route_id in provider_routes_by_id:
                errors.append(f"{ACCESS_PLANE_PATH}: duplicate provider route {route_id}")
                continue
            provider_routes_by_id[route_id] = route
            for field_name in ("provider", "api_family", "endpoint_origin", "endpoint_path", "status"):
                if not isinstance(route.get(field_name), str) or not route.get(field_name):
                    errors.append(
                        f"{ACCESS_PLANE_PATH}: provider route {route_id} missing non-empty {field_name}"
                    )
            if route.get("status") not in PROVIDER_ROUTE_STATUSES:
                errors.append(
                    f"{ACCESS_PLANE_PATH}: provider route {route_id} status must be one of {sorted(PROVIDER_ROUTE_STATUSES)}"
                )
            if not str(route.get("endpoint_path") or "").startswith("/"):
                errors.append(
                    f"{ACCESS_PLANE_PATH}: provider route {route_id} endpoint_path must be absolute"
                )
            if not isinstance(route.get("credential_required"), bool):
                errors.append(
                    f"{ACCESS_PLANE_PATH}: provider route {route_id} credential_required must be boolean"
                )
            for field_name in ("allowed_profiles", "allowed_models"):
                entries = require_non_empty_list(
                    route.get(field_name),
                    label=f"{ACCESS_PLANE_PATH}: provider route {route_id}.{field_name}",
                    errors=errors,
                )
                if entries and any(not isinstance(entry, str) or not entry for entry in entries):
                    errors.append(
                        f"{ACCESS_PLANE_PATH}: provider route {route_id}.{field_name} entries must be non-empty strings"
                    )

    for profile_id, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        bindings = profile.get("bindings") or {}
        selected_bindings = set(
            (profile.get("selected_binding_by_environment") or {}).values()
        )
        for binding_id, binding in bindings.items():
            if not isinstance(binding, dict):
                continue
            route_id = binding.get("provider_route")
            route = provider_routes_by_id.get(route_id)
            if route is None:
                errors.append(
                    f"{ACCESS_PLANE_PATH}: profile {profile_id} binding {binding_id} "
                    f"references unknown provider route {route_id!r}"
                )
                continue
            if route.get("provider") != binding.get("provider"):
                errors.append(
                    f"{ACCESS_PLANE_PATH}: provider route {route_id} provider must match "
                    f"profile {profile_id} binding {binding_id}"
                )
            if profile_id not in (route.get("allowed_profiles") or []):
                errors.append(
                    f"{ACCESS_PLANE_PATH}: provider route {route_id} must allow profile {profile_id}"
                )
            if binding.get("upstream_model") not in (route.get("allowed_models") or []):
                errors.append(
                    f"{ACCESS_PLANE_PATH}: provider route {route_id} must allow model "
                    f"{binding.get('upstream_model')!r}"
                )
            if binding_id in selected_bindings and route.get("status") == "retired":
                errors.append(
                    f"{ACCESS_PLANE_PATH}: selected binding {profile_id}/{binding_id} "
                    f"cannot use retired provider route {route_id}"
                )

    allowed_callers = require_non_empty_list(
        access_plane.get("allowed_callers"),
        label=f"{ACCESS_PLANE_PATH}: access_plane.allowed_callers",
        errors=errors,
    )
    if allowed_callers:
        for idx, caller in enumerate(allowed_callers, start=1):
            if not isinstance(caller, dict):
                errors.append(f"{ACCESS_PLANE_PATH}: allowed_callers entry #{idx} must be a mapping")
                continue
            required_profile = caller.get("required_profile")
            if required_profile not in profiles:
                errors.append(f"{ACCESS_PLANE_PATH}: allowed_callers entry #{idx} references unknown profile {required_profile!r}")
            allowed_task_kinds = caller.get("allowed_task_kinds")
            if (
                not isinstance(allowed_task_kinds, list)
                or not allowed_task_kinds
                or any(not isinstance(item, str) or not item for item in allowed_task_kinds)
            ):
                errors.append(
                    f"{ACCESS_PLANE_PATH}: allowed_callers entry #{idx} "
                    "allowed_task_kinds must be a non-empty string list"
                )
            elif isinstance(profiles.get(required_profile), dict):
                profile_tasks = set(
                    ((profiles[required_profile].get("task_contracts") or {}).get("allowed") or {})
                )
                if set(allowed_task_kinds) != profile_tasks:
                    errors.append(
                        f"{ACCESS_PLANE_PATH}: allowed_callers entry #{idx} task kinds "
                        f"must match profile {required_profile}"
                    )
            for schema_field in (
                "required_provider_output_schema_ref",
                "accepted_record_schema_ref",
            ):
                output_schema_ref = caller.get(schema_field)
                if output_schema_ref is None:
                    continue
                if not isinstance(output_schema_ref, dict):
                    errors.append(
                        f"{ACCESS_PLANE_PATH}: allowed_callers entry #{idx} "
                        f"{schema_field} must be a mapping"
                    )
                    continue
                resolve_cross_repo_path(
                    workspace_root,
                    output_schema_ref,
                    label=f"{ACCESS_PLANE_PATH}: allowed_callers entry #{idx} {schema_field}",
                    errors=errors,
                )

    caller_identity = require_non_empty_mapping(
        access_plane.get("caller_identity"),
        label=f"{ACCESS_PLANE_PATH}: access_plane.caller_identity",
        errors=errors,
    )
    if caller_identity is not None:
        fields = caller_identity.get("required_fields")
        if not isinstance(fields, list) or any(not isinstance(field, str) or not field for field in fields):
            errors.append(f"{ACCESS_PLANE_PATH}: caller_identity.required_fields must be a list of non-empty strings")
        else:
            missing = sorted(REQUIRED_CALLER_IDENTITY_FIELDS.difference(fields))
            if missing:
                errors.append(f"{ACCESS_PLANE_PATH}: caller_identity.required_fields missing {missing}")
        if caller_identity.get("operator_identity_required_when_human_approval_required") is not True:
            errors.append(f"{ACCESS_PLANE_PATH}: caller_identity must require operator identity when human approval is required")

    custody = require_non_empty_mapping(
        access_plane.get("provider_credential_custody"),
        label=f"{ACCESS_PLANE_PATH}: access_plane.provider_credential_custody",
        errors=errors,
    )
    if custody is not None:
        if custody.get("consumer_provider_credentials_allowed") is not False:
            errors.append(f"{ACCESS_PLANE_PATH}: consumer provider credentials must be false")
        devint_secret_ref = custody.get("devint_secret_ref")
        active_route_needs_secret = any(
            route.get("status") == "active" and route.get("credential_required") is True
            for route in provider_routes_by_id.values()
        )
        if access_plane.get("status") in {"devint-runtime-defined", "active"} and active_route_needs_secret:
            if not isinstance(devint_secret_ref, dict):
                errors.append(f"{ACCESS_PLANE_PATH}: active credentialed provider route requires devint_secret_ref")
            elif devint_secret_ref.get("consumer_projection_allowed") is not False:
                errors.append(f"{ACCESS_PLANE_PATH}: devint provider secret consumer projection must be false")
        refs = require_non_empty_list(
            custody.get("provider_secret_refs"),
            label=f"{ACCESS_PLANE_PATH}: provider_credential_custody.provider_secret_refs",
            errors=errors,
        )
        if refs:
            for idx, ref in enumerate(refs, start=1):
                if not isinstance(ref, dict):
                    errors.append(f"{ACCESS_PLANE_PATH}: provider_secret_refs entry #{idx} must be a mapping")
                    continue
                if not isinstance(ref.get("vault_path"), str) or not ref.get("vault_path"):
                    errors.append(f"{ACCESS_PLANE_PATH}: provider_secret_refs entry #{idx} missing vault_path")
                route_id = ref.get("route_id")
                route = provider_routes_by_id.get(route_id)
                if route is None:
                    errors.append(
                        f"{ACCESS_PLANE_PATH}: provider_secret_refs entry #{idx} references unknown route {route_id!r}"
                    )
                elif ref.get("provider") != route.get("provider"):
                    errors.append(
                        f"{ACCESS_PLANE_PATH}: provider_secret_refs entry #{idx} provider must match route {route_id}"
                    )

    audit = require_non_empty_mapping(
        access_plane.get("audit_contract"),
        label=f"{ACCESS_PLANE_PATH}: access_plane.audit_contract",
        errors=errors,
    )
    if audit is not None:
        if access_plane.get("status") in {"devint-runtime-defined", "active"} and audit.get("sink_status") != "devint-local-ledger":
            errors.append(f"{ACCESS_PLANE_PATH}: devint access plane requires devint-local-ledger")
        audit_fields = audit.get("required_fields")
        if not isinstance(audit_fields, list) or any(not isinstance(field, str) or not field for field in audit_fields):
            errors.append(f"{ACCESS_PLANE_PATH}: audit_contract.required_fields must be a list of non-empty strings")
        else:
            missing = sorted(REQUIRED_RUNTIME_AUDIT_FIELDS.difference(audit_fields))
            if missing:
                errors.append(f"{ACCESS_PLANE_PATH}: audit_contract.required_fields missing {missing}")

    admission = require_non_empty_mapping(
        access_plane.get("admission_policy"),
        label=f"{ACCESS_PLANE_PATH}: access_plane.admission_policy",
        errors=errors,
    )
    if admission is not None:
        if admission.get("default_decision") != "deny":
            errors.append(f"{ACCESS_PLANE_PATH}: admission_policy.default_decision must be deny")
        for bool_field in (
            "require_active_profile",
            "require_caller_allowlist_match",
            "require_data_scope_match",
            "require_output_schema_match",
            "require_human_approval_for_governance_decisions",
        ):
            if admission.get(bool_field) is not True:
                errors.append(f"{ACCESS_PLANE_PATH}: admission_policy.{bool_field} must be true")
        if admission.get("direct_provider_passthrough_allowed") is not False:
            errors.append(f"{ACCESS_PLANE_PATH}: admission_policy.direct_provider_passthrough_allowed must be false")

    activation = require_non_empty_mapping(
        access_plane.get("activation_state"),
        label=f"{ACCESS_PLANE_PATH}: access_plane.activation_state",
        errors=errors,
    )
    if activation is not None:
        profile_activations = activation.get("profile_activations")
        if not isinstance(profile_activations, dict) or set(profile_activations) != set(profiles):
            errors.append(
                f"{ACCESS_PLANE_PATH}: activation_state.profile_activations must "
                "cover every profile exactly"
            )
            profile_activations = {}
        for profile_id, profile_activation in profile_activations.items():
            if not isinstance(profile_activation, dict):
                errors.append(
                    f"{ACCESS_PLANE_PATH}: activation for {profile_id} must be a mapping"
                )
                continue
            allowed = profile_activation.get("activation_allowed")
            environment = profile_activation.get("environment")
            binding_id = profile_activation.get("binding")
            if not isinstance(allowed, bool):
                errors.append(
                    f"{ACCESS_PLANE_PATH}: activation for {profile_id} must declare activation_allowed"
                )
            profile = profiles.get(profile_id) or {}
            selected = (profile.get("selected_binding_by_environment") or {}).get(environment)
            if selected != binding_id:
                errors.append(
                    f"{ACCESS_PLANE_PATH}: activation for {profile_id}/{environment} "
                    f"must select binding {binding_id!r}"
                )
            binding = (profile.get("bindings") or {}).get(binding_id) or {}
            if allowed and (
                profile.get("status") != "active" or binding.get("status") != "active"
            ):
                errors.append(
                    f"{ACCESS_PLANE_PATH}: allowed activation for {profile_id} requires "
                    "active profile and binding status"
                )

        activation_allowed = activation.get("profile_activation_allowed")
        if not isinstance(activation_allowed, bool):
            errors.append(f"{ACCESS_PLANE_PATH}: activation_state.profile_activation_allowed must be boolean")
        if activation_allowed and access_plane.get("status") != "active":
            errors.append(f"{ACCESS_PLANE_PATH}: activation requires active access-plane status")
        active_profile = activation.get("active_profile")
        active_environment = activation.get("active_environment")
        active_binding = activation.get("active_binding")
        for field_name, value in (
            ("active_profile", active_profile),
            ("active_environment", active_environment),
            ("active_binding", active_binding),
        ):
            if not isinstance(value, str) or not value:
                errors.append(
                    f"{ACCESS_PLANE_PATH}: activation_state.{field_name} must be a non-empty string"
                )
        selected_profile = profiles.get(active_profile)
        if isinstance(active_profile, str) and active_profile and not isinstance(selected_profile, dict):
            errors.append(
                f"{ACCESS_PLANE_PATH}: activation_state.active_profile references unknown profile {active_profile!r}"
            )
        elif isinstance(selected_profile, dict) and isinstance(active_environment, str):
            selected_binding = (selected_profile.get("selected_binding_by_environment") or {}).get(
                active_environment
            )
            if selected_binding != active_binding:
                errors.append(
                    f"{ACCESS_PLANE_PATH}: activation state {active_profile}/{active_environment} "
                    f"must select binding {active_binding!r}"
                )

    if egress_policy is not None:
        required_path = egress_policy.get("required_invocation_path") or {}
        if required_path.get("service_name") != access_plane.get("id"):
            errors.append(f"{ACCESS_PLANE_PATH}: devint egress policy service_name must match access_plane.id")


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
        for field_name in ("purpose", "invocation_path", "notes"):
            value = profile.get(field_name)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{PROFILE_PATH}: {profile_id} missing non-empty {field_name}")
        environment_bindings = profile.get("selected_binding_by_environment")
        if not isinstance(environment_bindings, dict) or not environment_bindings:
            errors.append(f"{PROFILE_PATH}: {profile_id} selected_binding_by_environment must be a non-empty mapping")
            environment_bindings = {}
        bindings = profile.get("bindings")
        if not isinstance(bindings, dict) or not bindings:
            errors.append(f"{PROFILE_PATH}: {profile_id} bindings must be a non-empty mapping")
            bindings = {}
        for environment, binding_id in environment_bindings.items():
            if not isinstance(environment, str) or not environment:
                errors.append(f"{PROFILE_PATH}: {profile_id} binding environment must be non-empty")
            if binding_id not in bindings:
                errors.append(
                    f"{PROFILE_PATH}: {profile_id} environment {environment!r} references "
                    f"unknown binding {binding_id!r}"
                )
        for binding_id, binding in bindings.items():
            if not isinstance(binding, dict):
                errors.append(f"{PROFILE_PATH}: {profile_id} binding {binding_id} must be a mapping")
                continue
            for field_name in ("status", "provider", "provider_route", "upstream_model"):
                value = binding.get(field_name)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"{PROFILE_PATH}: {profile_id} binding {binding_id} missing non-empty {field_name}"
                    )
            environments = binding.get("environments")
            if not isinstance(environments, list) or not environments or any(
                not isinstance(item, str) or not item for item in environments
            ):
                errors.append(
                    f"{PROFILE_PATH}: {profile_id} binding {binding_id} environments must be a non-empty list"
                )
            selection = binding.get("selection")
            if not isinstance(selection, dict):
                errors.append(f"{PROFILE_PATH}: {profile_id} binding {binding_id} selection must be a mapping")
            else:
                for field_name in ("selected_at", "selected_by", "basis", "documentation_ref"):
                    value = selection.get(field_name)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(
                            f"{PROFILE_PATH}: {profile_id} binding {binding_id} selection "
                            f"missing non-empty {field_name}"
                        )
            if binding.get("status") not in MODEL_BINDING_STATUSES:
                errors.append(
                    f"{PROFILE_PATH}: {profile_id} binding {binding_id} status must be "
                    f"one of {sorted(MODEL_BINDING_STATUSES)}"
                )
            if binding.get("provider") == "ollama":
                for field_name in ("model_digest", "runtime_version"):
                    value = binding.get(field_name)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(
                            f"{PROFILE_PATH}: {profile_id} Ollama binding {binding_id} "
                            f"missing non-empty {field_name}"
                        )
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

        task_root = profile.get("task_contracts")
        if not isinstance(task_root, dict):
            errors.append(f"{PROFILE_PATH}: {profile_id} task_contracts must be a mapping")
            task_root = {}
        tasks = task_root.get("allowed")
        if not isinstance(tasks, dict) or not tasks:
            errors.append(f"{PROFILE_PATH}: {profile_id} task_contracts.allowed must be a non-empty mapping")
            tasks = {}
        default_task = task_root.get("default_task_kind")
        if default_task is not None and default_task not in tasks:
            errors.append(f"{PROFILE_PATH}: {profile_id} default task must reference an allowed task")
        for task_kind, task in tasks.items():
            label = f"{PROFILE_PATH}: {profile_id} task {task_kind}"
            if not isinstance(task, dict):
                errors.append(f"{label} must be a mapping")
                continue
            for field_name in (
                "contract_ref",
                "contract_version",
                "instruction_owner_repo",
                "instruction_source",
            ):
                if not isinstance(task.get(field_name), str) or not task.get(field_name):
                    errors.append(f"{label} missing non-empty {field_name}")
            if task.get("instruction_source") not in {"caller", "gateway-profile"}:
                errors.append(f"{label} instruction_source must be caller or gateway-profile")
            if task.get("instruction_source") == "gateway-profile" and not task.get("prompt_version"):
                errors.append(f"{label} gateway-profile instruction requires prompt_version")
            for ref_field in ("contract_source_ref", "provider_output_schema_ref"):
                ref = task.get(ref_field)
                if not isinstance(ref, dict):
                    errors.append(f"{label} {ref_field} must be a mapping")
                else:
                    resolve_cross_repo_path(
                        workspace_root,
                        ref,
                        label=f"{label} {ref_field}",
                        errors=errors,
                    )
            input_contract = task.get("input_contract")
            if not isinstance(input_contract, dict):
                errors.append(f"{label} input_contract must be a mapping")
            else:
                allowed_fields = input_contract.get("allowed_fields")
                required_fields = input_contract.get("required_fields")
                if not isinstance(allowed_fields, list) or not allowed_fields:
                    errors.append(f"{label} input_contract.allowed_fields must be a non-empty list")
                if not isinstance(required_fields, list) or not required_fields:
                    errors.append(f"{label} input_contract.required_fields must be a non-empty list")
                if isinstance(allowed_fields, list) and isinstance(required_fields, list):
                    unknown = sorted(set(required_fields).difference(allowed_fields))
                    if unknown:
                        errors.append(f"{label} requires fields outside its allowlist: {unknown}")

        for schema_field in ("provider_output_schema_ref", "accepted_record_schema_ref"):
            output_schema_ref = profile.get(schema_field)
            if output_schema_ref is None:
                continue
            if not isinstance(output_schema_ref, dict):
                errors.append(f"{PROFILE_PATH}: {profile_id} {schema_field} must be a mapping")
                continue
            resolve_cross_repo_path(
                workspace_root,
                output_schema_ref,
                label=f"{PROFILE_PATH}: {profile_id} {schema_field}",
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

    validate_access_plane_contract(repo_root, workspace_root, profiles, errors)
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
        f"access_plane={ACCESS_PLANE_PATH} "
        f"runtime_assist_contract={RUNTIME_ASSIST_CONTRACT_PATH}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
