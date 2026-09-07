#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess


SUPPORTED_RESUME_POLICIES = {"manual", "operator-login"}
AUTO_RESUME_ENV = "DEVINT_AUTO_RESUME"


class AutoResumeError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AutoResumeSpec:
    policy: str
    unit_name: str
    unit_path: Path
    unit_content: str


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not normalized:
        raise AutoResumeError(
            "auto-resume-contract-invalid",
            "profile and operator identifiers must contain letters or digits",
        )
    return normalized


def _systemd_quote(value: object) -> str:
    rendered = str(value).replace("\\", "\\\\").replace('"', '\\"')
    rendered = rendered.replace("%", "%%").replace("\n", "\\n")
    return f'"{rendered}"'


def _systemd_path_value(path: Path) -> str:
    rendered = str(path)
    if not path.is_absolute() or "\n" in rendered:
        raise AutoResumeError(
            "auto-resume-contract-invalid",
            "auto-resume working directory must be an absolute single-line path",
        )
    return rendered.replace("%", "%%")


def resolve_resume_policy(profile: dict) -> str:
    runtime = profile.get("runtime") or {}
    if not isinstance(runtime, dict):
        raise AutoResumeError(
            "auto-resume-contract-invalid",
            "runtime must be a mapping",
        )
    policy = runtime.get("resume_policy", "manual")
    if policy not in SUPPORTED_RESUME_POLICIES:
        raise AutoResumeError(
            "auto-resume-contract-invalid",
            "runtime.resume_policy must be manual or operator-login",
        )
    if policy == "operator-login" and runtime.get("state_model") != "persistent":
        raise AutoResumeError(
            "auto-resume-contract-invalid",
            "runtime.resume_policy operator-login requires state_model persistent",
        )
    return policy


def build_auto_resume_spec(
    *,
    operator: str,
    platform_runner: Path,
    profile: dict,
    profile_id: str,
    repo_paths: dict[str, Path],
    workspace_root: Path,
    config_home: Path | None = None,
    python_executable: str | None = None,
) -> AutoResumeSpec:
    policy = resolve_resume_policy(profile)
    unit_name = (
        f"workspace-devint-{_slugify(profile_id)}-{_slugify(operator)}.service"
    )
    resolved_config_home = config_home or Path(
        os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    )
    unit_path = resolved_config_home / "systemd" / "user" / unit_name
    python = python_executable or shutil.which("python3")
    if not python:
        raise AutoResumeError(
            "auto-resume-runtime-unavailable",
            "python3 is required for dev-integration auto-resume",
        )
    command = [
        python,
        str(platform_runner),
        "up",
        "--profile",
        profile_id,
        "--operator",
        operator,
        "--workspace-root",
        str(workspace_root),
    ]
    for repo_name, repo_path in sorted(repo_paths.items()):
        command.extend(["--repo-path", f"{repo_name}={repo_path}"])
    exec_start = " ".join(_systemd_quote(value) for value in command)
    unit_content = "\n".join(
        [
            "[Unit]",
            f"Description=Resume dev-integration profile {profile_id}",
            "StartLimitIntervalSec=0",
            "",
            "[Service]",
            "Type=oneshot",
            f"Environment={AUTO_RESUME_ENV}=1",
            f"WorkingDirectory={_systemd_path_value(platform_runner.parent.parent)}",
            f"ExecStart={exec_start}",
            "RemainAfterExit=yes",
            "Restart=on-failure",
            "RestartSec=15s",
            "TimeoutStartSec=15min",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
    )
    return AutoResumeSpec(
        policy=policy,
        unit_name=unit_name,
        unit_path=unit_path,
        unit_content=unit_content,
    )


def _run_systemctl(arguments: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["systemctl", "--user", *arguments],
            check=check,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        detail = "systemctl is unavailable"
        if isinstance(exc, subprocess.CalledProcessError):
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise AutoResumeError(
            "auto-resume-systemd-failed",
            f"user-systemd auto-resume failed: {detail}",
        ) from exc


def _write_unit(spec: AutoResumeSpec) -> None:
    spec.unit_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = spec.unit_path.with_name(f".{spec.unit_path.name}.{os.getpid()}.tmp")
    temporary.write_text(spec.unit_content, encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, spec.unit_path)


def inspect_auto_resume(spec: AutoResumeSpec) -> dict:
    installed = spec.unit_path.is_file()
    enabled = False
    if installed:
        result = _run_systemctl(["is-enabled", spec.unit_name], check=False)
        enabled = result.returncode == 0 and result.stdout.strip() == "enabled"
    return {
        "policy": spec.policy,
        "status": "enabled" if enabled else "disabled",
        "enabled": enabled,
        "installed": installed,
        "unit": spec.unit_name,
        "unit_path": str(spec.unit_path),
    }


def enable_auto_resume(spec: AutoResumeSpec) -> dict:
    if spec.policy != "operator-login":
        return disable_auto_resume(spec)
    _write_unit(spec)
    _run_systemctl(["daemon-reload"])
    _run_systemctl(["enable", spec.unit_name])
    projection = inspect_auto_resume(spec)
    if not projection["enabled"]:
        raise AutoResumeError(
            "auto-resume-enable-failed",
            f"auto-resume unit {spec.unit_name} was not enabled",
        )
    return projection


def disable_auto_resume(spec: AutoResumeSpec) -> dict:
    if spec.unit_path.exists():
        _run_systemctl(["disable", "--now", spec.unit_name], check=False)
        spec.unit_path.unlink(missing_ok=True)
        _run_systemctl(["daemon-reload"])
    return {
        "policy": spec.policy,
        "status": "disabled",
        "enabled": False,
        "installed": False,
        "unit": spec.unit_name,
        "unit_path": str(spec.unit_path),
    }


def render_auto_resume_status(projection: dict) -> None:
    print(
        "auto resume: "
        f"policy={projection['policy']} status={projection['status']} "
        f"unit={projection['unit']}"
    )
