from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile
from typing import Any

import yaml


SUPPORTED_ACTIONS = {"up", "status", "down"}
ENVIRONMENT_VARIABLE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


class CompositionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _now_utc() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", value.lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "composition"


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise CompositionError(
            "composition-state-invalid",
            f"composition state path is not a private directory: {path}",
        )
    path.chmod(0o700)


def _write_private_yaml(path: Path, payload: dict[str, Any]) -> None:
    _private_directory(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            yaml.safe_dump(payload, stream, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        path.chmod(0o600)
    finally:
        temporary_path.unlink(missing_ok=True)


def _load_private_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if path.is_symlink() or not path.is_file():
        raise CompositionError(
            "composition-state-invalid",
            f"composition state is not a regular file: {path}",
        )
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise CompositionError(
            "composition-state-invalid",
            f"composition state is not a mapping: {path}",
        )
    return payload


def composition_state_root(
    workspace_root: Path,
    composition_id: str,
    operator: str,
) -> Path:
    return (
        workspace_root
        / ".dev-integration"
        / "compositions"
        / _slugify(composition_id)
        / _slugify(operator)
    )


def resolve_runtime_composition(
    registry: Mapping[str, Any],
    composition_id: str,
) -> tuple[dict[str, Any], list[str]]:
    compositions = registry.get("runtime_compositions") or {}
    composition = compositions.get(composition_id)
    if not isinstance(composition, dict):
        raise CompositionError(
            "composition-unknown",
            f"unknown dev-integration runtime composition {composition_id!r}",
        )

    profiles = registry.get("profiles") or {}
    participants = composition.get("profiles") or {}
    root_profile_id = composition.get("root_profile_id")
    owner_repo = composition.get("owner_repo")
    if owner_repo != "platform-engineering":
        raise CompositionError(
            "composition-owner-invalid",
            f"composition {composition_id!r} is not owned by platform-engineering",
        )
    if not isinstance(participants, dict) or root_profile_id not in participants:
        raise CompositionError(
            "composition-contract-invalid",
            f"composition {composition_id!r} has no declared root profile",
        )

    graph = {profile_id: set() for profile_id in participants}
    projected_targets: set[tuple[str, str]] = set()
    for profile_id, requirement in participants.items():
        profile = profiles.get(profile_id)
        if not isinstance(profile, dict):
            raise CompositionError(
                "composition-profile-missing",
                f"composition profile {profile_id!r} is not registered",
            )
        required_lifecycle = requirement.get("required_lifecycle")
        if profile.get("lifecycle") != required_lifecycle:
            raise CompositionError(
                "composition-profile-inactive",
                f"composition profile {profile_id!r} requires lifecycle "
                f"{required_lifecycle!r}, got {profile.get('lifecycle')!r}",
            )
        if profile.get("runtime_owner") != owner_repo:
            raise CompositionError(
                "composition-runtime-owner-mismatch",
                f"composition profile {profile_id!r} is not controlled by {owner_repo!r}",
            )

    for dependency in composition.get("dependencies") or []:
        consumer = dependency.get("consumer_profile_id")
        provider = dependency.get("provider_profile_id")
        if consumer not in graph or provider not in graph or consumer == provider:
            raise CompositionError(
                "composition-dependency-invalid",
                f"composition {composition_id!r} has invalid dependency "
                f"{consumer!r} -> {provider!r}",
            )
        graph[consumer].add(provider)
        for projection in dependency.get("endpoint_projections") or []:
            variable = projection.get("environment_variable")
            target = (consumer, variable)
            if (
                not isinstance(variable, str)
                or not ENVIRONMENT_VARIABLE_PATTERN.fullmatch(variable)
                or target in projected_targets
            ):
                raise CompositionError(
                    "composition-projection-invalid",
                    f"composition {composition_id!r} has invalid or repeated projection "
                    f"{consumer!r}:{variable!r}",
                )
            projected_targets.add(target)

    for binding_id, binding in (composition.get("credential_bindings") or {}).items():
        if (
            binding.get("owner_repo") != owner_repo
            or binding.get("value_source") != "runtime-generated"
            or binding.get("retention") != "composition-lifetime"
        ):
            raise CompositionError(
                "composition-credential-contract-invalid",
                f"credential binding {binding_id!r} has unsupported custody semantics",
            )
        for projection in binding.get("projections") or []:
            profile_id = projection.get("profile_id")
            variable = projection.get("environment_variable")
            target = (profile_id, variable)
            if (
                profile_id not in participants
                or not isinstance(variable, str)
                or not ENVIRONMENT_VARIABLE_PATTERN.fullmatch(variable)
                or target in projected_targets
            ):
                raise CompositionError(
                    "composition-projection-invalid",
                    f"credential binding {binding_id!r} has invalid or repeated projection "
                    f"{profile_id!r}:{variable!r}",
                )
            projected_targets.add(target)

    visiting: set[str] = set()
    visited: set[str] = set()
    order: list[str] = []

    def visit(profile_id: str) -> None:
        if profile_id in visiting:
            raise CompositionError(
                "composition-dependency-cycle",
                f"composition {composition_id!r} contains a dependency cycle",
            )
        if profile_id in visited:
            return
        visiting.add(profile_id)
        for provider_id in sorted(graph[profile_id]):
            visit(provider_id)
        visiting.remove(profile_id)
        visited.add(profile_id)
        order.append(profile_id)

    visit(root_profile_id)
    if visited != set(participants):
        missing = ", ".join(sorted(set(participants) - visited))
        raise CompositionError(
            "composition-profile-disconnected",
            f"composition {composition_id!r} has profiles outside the root dependency graph: {missing}",
        )
    return composition, order


def build_profile_environments(
    composition: Mapping[str, Any],
    *,
    namespaces: Mapping[str, str],
    credential_values: Mapping[str, str],
) -> dict[str, dict[str, str]]:
    environments = {
        profile_id: {} for profile_id in (composition.get("profiles") or {})
    }
    for dependency in composition.get("dependencies") or []:
        consumer = dependency["consumer_profile_id"]
        provider = dependency["provider_profile_id"]
        namespace = namespaces[provider]
        for projection in dependency.get("endpoint_projections") or []:
            environments[consumer][projection["environment_variable"]] = (
                f"{projection['scheme']}://{projection['service_name']}."
                f"{namespace}.svc.cluster.local:{projection['service_port']}"
            )
    for binding_id, binding in (composition.get("credential_bindings") or {}).items():
        value = credential_values.get(binding_id)
        if value is None:
            continue
        for projection in binding.get("projections") or []:
            environments[projection["profile_id"]][
                projection["environment_variable"]
            ] = value
    return environments


def bounded_child_environment(
    composition: Mapping[str, Any],
    *,
    base_environment: Mapping[str, str],
    profile_environment: Mapping[str, str],
) -> dict[str, str]:
    declared_variables = {
        projection["environment_variable"]
        for dependency in composition.get("dependencies") or []
        for projection in dependency.get("endpoint_projections") or []
    }
    declared_variables.update(
        projection["environment_variable"]
        for binding in (composition.get("credential_bindings") or {}).values()
        for projection in binding.get("projections") or []
    )
    bounded = {
        key: value
        for key, value in base_environment.items()
        if key not in declared_variables
    }
    bounded.update(profile_environment)
    return bounded


def load_or_create_credentials(
    composition: Mapping[str, Any],
    *,
    state_root: Path,
    create: bool,
) -> tuple[dict[str, str], bool]:
    bindings = composition.get("credential_bindings") or {}
    credentials_root = state_root / "credentials"
    values: dict[str, str] = {}
    created_any = False
    if bindings:
        _private_directory(credentials_root)
    for binding_id in sorted(bindings):
        path = credentials_root / f"{_slugify(binding_id)}.secret"
        if path.is_symlink():
            raise CompositionError(
                "composition-credential-unsafe",
                f"credential binding {binding_id!r} must not be a symlink",
            )
        if path.exists():
            file_stat = path.lstat()
            if (
                not stat.S_ISREG(file_stat.st_mode)
                or stat.S_IMODE(file_stat.st_mode) != 0o600
                or file_stat.st_uid != os.getuid()
            ):
                raise CompositionError(
                    "composition-credential-unsafe",
                    f"credential binding {binding_id!r} is not a private operator-owned file",
                )
            value = path.read_text(encoding="utf-8").strip()
            if not value:
                raise CompositionError(
                    "composition-credential-invalid",
                    f"credential binding {binding_id!r} is empty",
                )
        elif create:
            value = secrets.token_urlsafe(32)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
            created_any = True
        else:
            raise CompositionError(
                "composition-credential-missing",
                f"credential binding {binding_id!r} is missing",
            )
        values[binding_id] = value
    return values, created_any


def remove_credentials(composition: Mapping[str, Any], *, state_root: Path) -> None:
    credentials_root = state_root / "credentials"
    for binding_id in sorted((composition.get("credential_bindings") or {})):
        path = credentials_root / f"{_slugify(binding_id)}.secret"
        if path.is_symlink():
            raise CompositionError(
                "composition-credential-unsafe",
                f"refusing to remove symlinked credential binding {binding_id!r}",
            )
        if path.exists():
            file_stat = path.lstat()
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_uid != os.getuid():
                raise CompositionError(
                    "composition-credential-unsafe",
                    f"refusing to remove unowned credential binding {binding_id!r}",
                )
            path.unlink()
    if credentials_root.exists() and not any(credentials_root.iterdir()):
        credentials_root.rmdir()


def execute_composition(
    *,
    action: str,
    composition_id: str,
    composition: Mapping[str, Any],
    profile_order: list[str],
    namespaces: Mapping[str, str],
    operator: str,
    state_root: Path,
    dispatch: Callable[[str, str, Mapping[str, str]], int],
) -> int:
    if action not in SUPPORTED_ACTIONS:
        raise CompositionError(
            "composition-action-unsupported",
            f"runtime compositions support only {', '.join(sorted(SUPPORTED_ACTIONS))}",
        )
    manifest_path = state_root / "current-composition.yaml"
    state = _load_private_yaml(manifest_path)
    if state and (
        state.get("composition_id") != composition_id
        or state.get("operator") != operator
    ):
        raise CompositionError(
            "composition-state-owner-mismatch",
            "composition state is owned by a different composition or operator",
        )

    credentials: dict[str, str] = {}
    created_credentials = False
    if action == "up":
        credentials, created_credentials = load_or_create_credentials(
            composition,
            state_root=state_root,
            create=True,
        )
    elif action == "status" and not state:
        raise CompositionError(
            "composition-state-missing",
            f"composition {composition_id!r} has no owned runtime state to inspect",
        )
    elif action == "status" and state.get("lifecycle") in {"active", "degraded"}:
        credentials, _ = load_or_create_credentials(
            composition,
            state_root=state_root,
            create=False,
        )
    elif action == "down" and not state:
        raise CompositionError(
            "composition-state-missing",
            f"composition {composition_id!r} has no owned runtime state to stop",
        )
    elif action == "down" and state.get("lifecycle") in {"active", "degraded"}:
        credentials, _ = load_or_create_credentials(
            composition,
            state_root=state_root,
            create=False,
        )

    environments = build_profile_environments(
        composition,
        namespaces=namespaces,
        credential_values=credentials,
    )
    run_order = list(reversed(profile_order)) if action == "down" else profile_order
    completed: list[str] = []
    failures: list[str] = []
    for profile_id in run_order:
        returncode = dispatch(action, profile_id, environments[profile_id])
        if returncode:
            failures.append(profile_id)
            if action == "up":
                break
        else:
            completed.append(profile_id)

    rollback_failures: list[str] = []
    if action == "up" and failures:
        for profile_id in reversed(completed):
            if dispatch("down", profile_id, environments[profile_id]):
                rollback_failures.append(profile_id)
        if created_credentials and not rollback_failures:
            remove_credentials(composition, state_root=state_root)

    lifecycle = "active"
    if failures or rollback_failures:
        lifecycle = "degraded"
    elif action == "down":
        remove_credentials(composition, state_root=state_root)
        lifecycle = "suspended"
    elif action == "status":
        lifecycle = state.get("lifecycle", "unknown")

    endpoint_projections = []
    for dependency in composition.get("dependencies") or []:
        for projection in dependency.get("endpoint_projections") or []:
            endpoint_projections.append(
                {
                    "consumer_profile_id": dependency["consumer_profile_id"],
                    "provider_profile_id": dependency["provider_profile_id"],
                    "environment_variable": projection["environment_variable"],
                    "service_name": projection["service_name"],
                    "service_port": projection["service_port"],
                }
            )

    state_payload = {
        "schema_version": 1,
        "composition_id": composition_id,
        "operator": operator,
        "lifecycle": lifecycle,
        "profile_order": profile_order,
        "credential_binding_ids": sorted(
            (composition.get("credential_bindings") or {}).keys()
        ),
        "endpoint_projections": endpoint_projections,
        "last_action": action,
        "completed_profile_ids": completed,
        "failed_profile_ids": failures,
        "rollback_failed_profile_ids": rollback_failures,
        "updated_at": _now_utc(),
    }
    _write_private_yaml(manifest_path, state_payload)

    print(
        "dev-integration composition: "
        f"id={composition_id} action={action} state={lifecycle} "
        f"profiles={','.join(profile_order)}"
    )
    if failures or rollback_failures:
        return 1
    return 0
