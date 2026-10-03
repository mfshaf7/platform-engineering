from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
from typing import Any


class CompositionPreflightError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CompositionPreflightProfile:
    profile_id: str
    profile: Mapping[str, Any]
    owner_repo_root: Path
    auto_resume_unit_path: Path


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    command_runner: CommandRunner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    try:
        return command_runner(
            list(command),
            cwd=str(cwd) if cwd else None,
            env=dict(env) if env is not None else None,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise CompositionPreflightError(
            "composition-preflight-command-missing",
            f"required preflight command is unavailable: {command[0]}",
        ) from exc


def _private_runtime_directory(environment: Mapping[str, str]) -> Path:
    runtime_value = environment.get("XDG_RUNTIME_DIR")
    runtime_dir = (
        Path(runtime_value).expanduser()
        if runtime_value
        else Path("/run/user") / str(os.getuid())
    )
    try:
        runtime_stat = runtime_dir.lstat()
    except FileNotFoundError as exc:
        raise CompositionPreflightError(
            "composition-preflight-runtime-directory-missing",
            f"operator runtime directory is unavailable: {runtime_dir}",
        ) from exc
    if (
        runtime_dir.is_symlink()
        or not stat.S_ISDIR(runtime_stat.st_mode)
        or runtime_stat.st_uid != os.getuid()
        or stat.S_IMODE(runtime_stat.st_mode) & 0o077
    ):
        raise CompositionPreflightError(
            "composition-preflight-runtime-directory-unsafe",
            "operator runtime directory must be a private directory owned by the "
            f"current uid: {runtime_dir}",
        )
    return runtime_dir


def _nearest_existing_ancestor(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def _check_auto_resume(
    profiles: Sequence[CompositionPreflightProfile],
    *,
    environment: Mapping[str, str],
    command_runner: CommandRunner,
) -> list[str]:
    auto_resume_profiles = [
        item
        for item in profiles
        if (item.profile.get("runtime") or {}).get("resume_policy", "manual")
        == "operator-login"
    ]
    if not auto_resume_profiles:
        return []
    result = _run(
        ["systemctl", "--user", "show-environment"],
        env=environment,
        command_runner=command_runner,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "user manager unavailable").strip()
        raise CompositionPreflightError(
            "composition-preflight-user-systemd-unavailable",
            f"user systemd is not ready for operator-login recovery: {detail}",
        )
    checked: list[str] = []
    for item in auto_resume_profiles:
        ancestor = _nearest_existing_ancestor(item.auto_resume_unit_path.parent)
        ancestor_stat = ancestor.lstat()
        if (
            ancestor.is_symlink()
            or not stat.S_ISDIR(ancestor_stat.st_mode)
            or ancestor_stat.st_uid != os.getuid()
            or not os.access(ancestor, os.W_OK | os.X_OK)
        ):
            raise CompositionPreflightError(
                "composition-preflight-auto-resume-path-unsafe",
                "auto-resume unit path has no writable operator-owned ancestor: "
                f"{item.auto_resume_unit_path}",
            )
        checked.append(item.profile_id)
    return checked


def _check_source_dependencies(
    profiles: Sequence[CompositionPreflightProfile],
    *,
    environment: Mapping[str, str],
    command_runner: CommandRunner,
) -> list[str]:
    checked: list[str] = []
    for item in profiles:
        if not item.profile.get("host_services"):
            continue
        package_json = item.owner_repo_root / "package.json"
        package_lock = item.owner_repo_root / "package-lock.json"
        if not package_json.exists() and not package_lock.exists():
            continue
        if not package_json.is_file() or not package_lock.is_file():
            raise CompositionPreflightError(
                "composition-preflight-source-dependency-contract-invalid",
                f"host-service owner {item.profile_id!r} must keep package.json and "
                "package-lock.json together",
            )
        npm = shutil.which("npm", path=environment.get("PATH"))
        if not npm:
            raise CompositionPreflightError(
                "composition-preflight-source-dependency-tool-missing",
                f"npm is required to verify host-service dependencies for {item.profile_id!r}",
            )
        result = _run(
            [npm, "ls", "--omit=dev", "--depth=0", "--json"],
            cwd=item.owner_repo_root,
            env=environment,
            command_runner=command_runner,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "dependency tree unavailable").strip()
            raise CompositionPreflightError(
                "composition-preflight-source-dependencies-unready",
                f"production source dependencies are not ready for host-service profile "
                f"{item.profile_id!r}: {detail}",
            )
        checked.append(item.profile_id)
    return checked


def _check_pending_helm_operations(
    *,
    environment: Mapping[str, str],
    command_runner: CommandRunner,
) -> list[dict[str, Any]]:
    helm_command = shlex.split(environment.get("DEVINT_HELM", "helm"))
    if not helm_command:
        raise CompositionPreflightError(
            "composition-preflight-helm-command-invalid",
            "DEVINT_HELM must identify a Helm command",
        )
    command_environment = dict(environment)
    command_environment["KUBECONFIG"] = environment.get(
        "DEVINT_KUBECONFIG",
        "/etc/rancher/k3s/k3s.yaml",
    )
    result = _run(
        [*helm_command, "list", "--all-namespaces", "--pending", "-o", "json"],
        env=command_environment,
        command_runner=command_runner,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Helm state unavailable").strip()
        raise CompositionPreflightError(
            "composition-preflight-helm-state-unavailable",
            f"cannot inspect pending Helm operations: {detail}",
        )
    try:
        releases = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise CompositionPreflightError(
            "composition-preflight-helm-state-invalid",
            "Helm pending-operation output was not valid JSON",
        ) from exc
    if not isinstance(releases, list):
        raise CompositionPreflightError(
            "composition-preflight-helm-state-invalid",
            "Helm pending-operation output must be a list",
        )
    if releases:
        summary = ", ".join(
            f"{item.get('namespace', '?')}/{item.get('name', '?')}={item.get('status', '?')}"
            for item in releases
            if isinstance(item, dict)
        )
        raise CompositionPreflightError(
            "composition-preflight-helm-operation-pending",
            f"pending Helm operations must be repaired before composition startup: {summary}",
        )
    return releases


def run_composition_preflight(
    profiles: Sequence[CompositionPreflightProfile],
    *,
    environment: Mapping[str, str] | None = None,
    command_runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    effective_environment = dict(os.environ if environment is None else environment)
    runtime_dir = _private_runtime_directory(effective_environment)
    dependency_profiles = _check_source_dependencies(
        profiles,
        environment=effective_environment,
        command_runner=command_runner,
    )
    auto_resume_profiles = _check_auto_resume(
        profiles,
        environment=effective_environment,
        command_runner=command_runner,
    )
    _check_pending_helm_operations(
        environment=effective_environment,
        command_runner=command_runner,
    )
    result = {
        "profile_ids": [item.profile_id for item in profiles],
        "source_dependency_profile_ids": dependency_profiles,
        "runtime_directory": str(runtime_dir),
        "auto_resume_profile_ids": auto_resume_profiles,
        "pending_helm_operations": 0,
    }
    print(
        "dev-integration composition preflight: "
        f"profiles={','.join(result['profile_ids'])} "
        f"source_dependencies={','.join(dependency_profiles) or 'none'} "
        f"runtime_directory={runtime_dir} "
        f"auto_resume={','.join(auto_resume_profiles) or 'none'} "
        "pending_helm_operations=0"
    )
    return result
