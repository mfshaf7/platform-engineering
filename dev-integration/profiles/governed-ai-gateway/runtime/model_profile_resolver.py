from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


class ModelProfileResolutionError(ValueError):
    """Raised when governed profile selection cannot be proven safely."""


def _load_yaml(path: Path, label: str) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    payload = yaml.safe_load(raw) or {}
    if not isinstance(payload, dict):
        raise ModelProfileResolutionError(f"{label} must be a mapping")
    return payload, f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ModelProfileResolutionError(f"{label} must be a mapping")
    return value


def _non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelProfileResolutionError(f"{label} must be a non-empty string")
    return value.strip()


def _optional_non_empty_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _non_empty_string(value, label)


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ModelProfileResolutionError(f"{label} must be a non-empty list")
    values = [_non_empty_string(item, f"{label} entry") for item in value]
    if len(values) != len(set(values)):
        raise ModelProfileResolutionError(f"{label} must not contain duplicates")
    return values


def _schema_ref(value: Any, label: str) -> tuple[dict[str, str], str]:
    mapping = _mapping(value, label)
    repo = _non_empty_string(mapping.get("repo"), f"{label}.repo")
    path = _non_empty_string(mapping.get("path"), f"{label}.path")
    return {"repo": repo, "path": path}, f"{repo}/{path}"


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _index_mappings(
    value: Any, label: str, key_name: str
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ModelProfileResolutionError(f"{label} must be a non-empty list")
    indexed: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(value, start=1):
        mapping = _mapping(item, f"{label} entry #{index}")
        key = _non_empty_string(
            mapping.get(key_name), f"{label} entry #{index}.{key_name}"
        )
        if key in indexed:
            raise ModelProfileResolutionError(
                f"{label} contains duplicate {key_name} {key}"
            )
        indexed[key] = mapping
    return indexed


def resolve_model_profile(
    profile_registry_path: Path,
    access_plane_path: Path,
    *,
    profile_id: str,
    environment: str,
    require_active: bool = False,
) -> dict[str, Any]:
    profile_id = _non_empty_string(profile_id, "profile_id")
    environment = _non_empty_string(environment, "environment")
    registry, registry_digest = _load_yaml(
        profile_registry_path, "model profile registry"
    )
    access_document, access_plane_digest = _load_yaml(
        access_plane_path, "access plane contract"
    )

    profiles = _mapping(registry.get("model_profiles"), "model_profiles")
    if profile_id not in profiles:
        raise ModelProfileResolutionError(f"unknown governed model profile: {profile_id}")
    profile = _mapping(profiles[profile_id], f"model_profiles.{profile_id}")

    bindings = _mapping(
        profile.get("bindings"), f"model_profiles.{profile_id}.bindings"
    )
    environment_bindings = _mapping(
        profile.get("active_binding_by_environment"),
        f"model_profiles.{profile_id}.active_binding_by_environment",
    )
    binding_id = _non_empty_string(
        environment_bindings.get(environment),
        f"model_profiles.{profile_id}.active_binding_by_environment.{environment}",
    )
    if binding_id not in bindings:
        raise ModelProfileResolutionError(
            f"profile {profile_id} selects unknown binding {binding_id} for {environment}"
        )
    binding = _mapping(
        bindings[binding_id],
        f"model_profiles.{profile_id}.bindings.{binding_id}",
    )
    binding_environments = _string_list(
        binding.get("environments"),
        f"model_profiles.{profile_id}.bindings.{binding_id}.environments",
    )
    if environment not in binding_environments:
        raise ModelProfileResolutionError(
            f"binding {binding_id} does not allow environment {environment}"
        )

    profile_status = _non_empty_string(
        profile.get("status"), f"profile {profile_id} status"
    )
    binding_status = _non_empty_string(
        binding.get("status"), f"binding {binding_id} status"
    )
    purpose = _non_empty_string(profile.get("purpose"), f"profile {profile_id} purpose")
    invocation_path = _non_empty_string(
        profile.get("invocation_path"), f"profile {profile_id} invocation_path"
    )
    provider = _non_empty_string(
        binding.get("provider"), f"binding {binding_id} provider"
    )
    if profile.get("direct_provider_access_allowed") is not False:
        raise ModelProfileResolutionError(
            f"profile {profile_id} must prohibit direct provider access"
        )
    if profile.get("human_approval_required") is not True:
        raise ModelProfileResolutionError(
            f"profile {profile_id} must require human approval"
        )
    provider_route = _non_empty_string(
        binding.get("provider_route"), f"binding {binding_id} provider_route"
    )
    upstream_model = _non_empty_string(
        binding.get("upstream_model"), f"binding {binding_id} upstream_model"
    )
    model_digest = _optional_non_empty_string(
        binding.get("model_digest"), f"binding {binding_id} model_digest"
    )
    runtime_version = _optional_non_empty_string(
        binding.get("runtime_version"), f"binding {binding_id} runtime_version"
    )
    if provider == "ollama" and (model_digest is None or runtime_version is None):
        raise ModelProfileResolutionError(
            f"Ollama binding {binding_id} requires model_digest and runtime_version"
        )
    allowed_callers = sorted(
        _string_list(
            profile.get("allowed_callers"), f"profile {profile_id} allowed_callers"
        )
    )
    output_schema, output_schema_ref = _schema_ref(
        profile.get("provider_output_schema_ref"),
        f"profile {profile_id} provider_output_schema_ref",
    )
    selection_metadata = _mapping(
        binding.get("selection"), f"binding {binding_id} selection"
    )
    selection_metadata = {
        field: _non_empty_string(
            selection_metadata.get(field),
            f"binding {binding_id} selection.{field}",
        )
        for field in ("selected_at", "selected_by", "basis", "documentation_ref")
    }

    access_plane = _mapping(access_document.get("access_plane"), "access_plane")
    access_plane_id = _non_empty_string(access_plane.get("id"), "access_plane.id")
    access_plane_status = _non_empty_string(
        access_plane.get("status"), "access_plane.status"
    )
    if invocation_path != access_plane_id:
        raise ModelProfileResolutionError(
            f"profile invocation path {invocation_path} does not match access plane "
            f"{access_plane_id}"
        )
    allowed_profiles = _string_list(
        access_plane.get("allowed_profiles"), "access_plane.allowed_profiles"
    )
    if profile_id not in allowed_profiles:
        raise ModelProfileResolutionError(f"access plane does not allow profile {profile_id}")

    routes = _index_mappings(
        access_plane.get("provider_routes"), "access_plane.provider_routes", "route_id"
    )
    if provider_route not in routes:
        raise ModelProfileResolutionError(f"unknown provider route: {provider_route}")
    route = routes[provider_route]
    route_status = _non_empty_string(
        route.get("status"), f"provider route {provider_route} status"
    )
    route_provider = _non_empty_string(
        route.get("provider"), f"provider route {provider_route} provider"
    )
    if route_provider != provider:
        raise ModelProfileResolutionError(
            f"binding provider {provider} does not match route provider {route_provider}"
        )
    if profile_id not in _string_list(
        route.get("allowed_profiles"), f"provider route {provider_route} allowed_profiles"
    ):
        raise ModelProfileResolutionError(
            f"provider route {provider_route} does not allow profile {profile_id}"
        )
    if upstream_model not in _string_list(
        route.get("allowed_models"), f"provider route {provider_route} allowed_models"
    ):
        raise ModelProfileResolutionError(
            f"provider route {provider_route} does not allow model {upstream_model}"
        )
    endpoint_origin = _non_empty_string(
        route.get("endpoint_origin"), f"provider route {provider_route} endpoint_origin"
    )
    endpoint_path = _non_empty_string(
        route.get("endpoint_path"), f"provider route {provider_route} endpoint_path"
    )
    api_family = _non_empty_string(
        route.get("api_family"), f"provider route {provider_route} api_family"
    )
    credential_required = route.get("credential_required")
    if not isinstance(credential_required, bool):
        raise ModelProfileResolutionError(
            f"provider route {provider_route} credential_required must be boolean"
        )

    caller_contracts = _index_mappings(
        access_plane.get("allowed_callers"), "access_plane.allowed_callers", "caller_id"
    )
    for caller_id in allowed_callers:
        caller = caller_contracts.get(caller_id)
        if caller is None:
            raise ModelProfileResolutionError(
                f"profile caller {caller_id} is missing from access-plane callers"
            )
        if caller.get("required_profile") != profile_id:
            raise ModelProfileResolutionError(
                f"caller {caller_id} required_profile does not match {profile_id}"
            )
        if caller.get("purpose") != purpose:
            raise ModelProfileResolutionError(
                f"caller {caller_id} purpose does not match profile {profile_id}"
            )
        caller_schema, _ = _schema_ref(
            caller.get("required_provider_output_schema_ref"),
            f"caller {caller_id} required_provider_output_schema_ref",
        )
        if caller_schema != output_schema:
            raise ModelProfileResolutionError(
                f"caller {caller_id} output schema does not match profile {profile_id}"
            )

    activation_state = _mapping(
        access_plane.get("activation_state"), "access_plane.activation_state"
    )
    activation_allowed = activation_state.get("profile_activation_allowed")
    if not isinstance(activation_allowed, bool):
        raise ModelProfileResolutionError(
            "access_plane.activation_state.profile_activation_allowed must be boolean"
        )
    active_profile = _non_empty_string(
        activation_state.get("active_profile"),
        "access_plane.activation_state.active_profile",
    )
    active_environment = _non_empty_string(
        activation_state.get("active_environment"),
        "access_plane.activation_state.active_environment",
    )
    active_binding = _non_empty_string(
        activation_state.get("active_binding"),
        "access_plane.activation_state.active_binding",
    )
    if activation_allowed and (
        active_profile != profile_id
        or active_environment != environment
        or active_binding != binding_id
    ):
        raise ModelProfileResolutionError(
            "access-plane activation does not match the selected profile and "
            "environment binding"
        )

    activation_denial_reasons = []
    if profile_status != "active":
        activation_denial_reasons.append("profile-not-active")
    if binding_status != "active":
        activation_denial_reasons.append("binding-not-active")
    if access_plane_status != "active":
        activation_denial_reasons.append("access-plane-not-active")
    if route_status != "active":
        activation_denial_reasons.append("provider-route-not-active")
    if not activation_allowed:
        activation_denial_reasons.append("profile-activation-not-allowed")
    if require_active and activation_denial_reasons:
        raise ModelProfileResolutionError(
            "selected binding is not activation eligible: "
            + ",".join(activation_denial_reasons)
        )

    evidence = {
        "schema_version": 1,
        "profile_id": profile_id,
        "profile_status": profile_status,
        "purpose": purpose,
        "environment": environment,
        "binding_id": binding_id,
        "binding_status": binding_status,
        "provider": provider,
        "provider_route": provider_route,
        "provider_route_status": route_status,
        "endpoint_origin": endpoint_origin,
        "endpoint_path": endpoint_path,
        "api_family": api_family,
        "credential_required": credential_required,
        "upstream_model": upstream_model,
        "model_digest": model_digest,
        "runtime_version": runtime_version,
        "invocation_path": invocation_path,
        "allowed_callers": allowed_callers,
        "provider_output_schema_ref": output_schema_ref,
        "selection_metadata": selection_metadata,
        "profile_registry_digest": registry_digest,
        "access_plane_digest": access_plane_digest,
        "human_approval_required": True,
        "direct_provider_access_allowed": False,
        "fallback_mode": "fail-closed-no-implicit-fallback",
        "profile_activation_allowed": activation_allowed,
        "activation_profile_id": active_profile,
        "activation_eligible": not activation_denial_reasons,
        "activation_denial_reasons": activation_denial_reasons,
    }
    selection_digest = _canonical_digest(evidence)
    return {
        **evidence,
        "selection_digest": selection_digest,
        "selection_ref": f"model-binding-selection:{selection_digest.removeprefix('sha256:')}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve one governed AI model profile binding."
    )
    parser.add_argument("--profile-registry", type=Path, required=True)
    parser.add_argument("--access-plane", type=Path, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--require-active", action="store_true")
    args = parser.parse_args()
    try:
        result = resolve_model_profile(
            args.profile_registry,
            args.access_plane,
            profile_id=args.profile_id,
            environment=args.environment,
            require_active=args.require_active,
        )
    except (OSError, yaml.YAMLError, ModelProfileResolutionError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
