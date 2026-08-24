#!/usr/bin/env python3
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from typing import Callable

import yaml


SERVICE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SERVICE_KEYS = {"id", "command", "readiness"}
READINESS_KEYS = {
    "mode",
    "command",
    "timeout_seconds",
    "interval_seconds",
    "probe_timeout_seconds",
}


class HostServiceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ReadinessSpec:
    mode: str
    command_path: Path | None
    timeout_seconds: float
    interval_seconds: float
    probe_timeout_seconds: float


@dataclass(frozen=True)
class HostServiceSpec:
    service_id: str
    command_path: Path
    command_digest: str
    readiness: ReadinessSpec


def now_utc() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _resolve_owner_file(owner_repo_root: Path, configured_path: object, label: str) -> Path:
    if not isinstance(configured_path, str) or not configured_path.strip():
        raise HostServiceError("host-service-contract-invalid", f"{label} must be a non-empty owner-relative path")
    relative_path = Path(configured_path)
    if relative_path.is_absolute():
        raise HostServiceError("host-service-contract-invalid", f"{label} must be owner-relative")
    try:
        resolved = (owner_repo_root / relative_path).resolve(strict=True)
    except FileNotFoundError as exc:
        raise HostServiceError("host-service-command-missing", f"{label} is unavailable: {configured_path}") from exc
    try:
        resolved.relative_to(owner_repo_root)
    except ValueError as exc:
        raise HostServiceError("host-service-contract-invalid", f"{label} escapes the selected owner checkout") from exc
    if not resolved.is_file():
        raise HostServiceError("host-service-command-missing", f"{label} is not a file: {configured_path}")
    return resolved


def _positive_number(value: object, *, default: float, label: str) -> float:
    candidate = default if value is None else value
    if isinstance(candidate, bool) or not isinstance(candidate, (int, float)) or candidate <= 0:
        raise HostServiceError("host-service-contract-invalid", f"{label} must be a positive number")
    return float(candidate)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _command(path: Path) -> list[str]:
    if path.suffix == ".sh":
        return ["bash", str(path)]
    if path.suffix == ".py":
        return ["python3", str(path)]
    return [str(path)]


def _spawn_detached(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.chmod(log_path, 0o600)
    read_fd, write_fd = os.pipe()
    os.set_inheritable(write_fd, False)
    try:
        launcher_pid = os.fork()
    except OSError:
        os.close(read_fd)
        os.close(write_fd)
        os.close(log_fd)
        raise
    if launcher_pid == 0:
        try:
            os.close(read_fd)
            os.setsid()
            service_pid = os.fork()
            if service_pid > 0:
                os._exit(0)
            os.setpgid(0, 0)
            os.write(write_fd, f"{os.getpid()}\n".encode())
            os.chdir(cwd)
            null_fd = os.open(os.devnull, os.O_RDONLY)
            os.dup2(null_fd, 0)
            os.dup2(log_fd, 1)
            os.dup2(log_fd, 2)
            for descriptor in {null_fd, log_fd}:
                if descriptor > 2:
                    os.close(descriptor)
            os.execvpe(command[0], command, env)
        except BaseException as exc:
            try:
                os.write(write_fd, f"ERROR:{exc.__class__.__name__}:{exc}\n".encode())
            finally:
                os._exit(127)
    os.close(write_fd)
    os.close(log_fd)
    with os.fdopen(read_fd, "rb", closefd=True) as stream:
        launch_result = stream.read().decode(errors="replace").splitlines()
    _, launcher_status = os.waitpid(launcher_pid, 0)
    raw_pid = launch_result[0] if launch_result else ""
    launch_error = next(
        (
            line.removeprefix("ERROR:")
            for line in launch_result[1:]
            if line.startswith("ERROR:")
        ),
        None,
    )
    if launcher_status != 0 or not raw_pid.isdigit() or launch_error is not None:
        detail = f": {launch_error}" if launch_error else ""
        raise HostServiceError(
            "host-service-start-failed",
            f"detached host-service launcher failed{detail}",
        )
    return int(raw_pid)


def resolve_host_services(
    profile: dict,
    owner_repo_root: Path,
    source_revisions: dict[str, dict] | None = None,
) -> list[HostServiceSpec]:
    declarations = profile.get("host_services") or []
    if not isinstance(declarations, list):
        raise HostServiceError("host-service-contract-invalid", "host_services must be a list")
    specs: list[HostServiceSpec] = []
    seen: set[str] = set()
    for index, declaration in enumerate(declarations):
        label = f"host_services[{index}]"
        if not isinstance(declaration, dict):
            raise HostServiceError("host-service-contract-invalid", f"{label} must be a mapping")
        unknown = sorted(set(declaration) - SERVICE_KEYS)
        if unknown:
            raise HostServiceError("host-service-contract-invalid", f"{label} has unsupported fields: {', '.join(unknown)}")
        service_id = declaration.get("id")
        if not isinstance(service_id, str) or not SERVICE_ID_PATTERN.fullmatch(service_id):
            raise HostServiceError("host-service-contract-invalid", f"{label}.id must use lowercase letters, digits, and hyphens")
        if service_id in seen:
            raise HostServiceError("host-service-contract-invalid", f"duplicate host service id {service_id!r}")
        seen.add(service_id)
        command_path = _resolve_owner_file(owner_repo_root, declaration.get("command"), f"{label}.command")
        readiness_payload = declaration.get("readiness")
        if not isinstance(readiness_payload, dict):
            raise HostServiceError("host-service-contract-invalid", f"{label}.readiness must be a mapping")
        unknown_readiness = sorted(set(readiness_payload) - READINESS_KEYS)
        if unknown_readiness:
            raise HostServiceError("host-service-contract-invalid", f"{label}.readiness has unsupported fields: {', '.join(unknown_readiness)}")
        mode = readiness_payload.get("mode")
        if mode not in {"process", "command"}:
            raise HostServiceError("host-service-contract-invalid", f"{label}.readiness.mode must be process or command")
        readiness_command = None
        if mode == "command":
            readiness_command = _resolve_owner_file(
                owner_repo_root,
                readiness_payload.get("command"),
                f"{label}.readiness.command",
            )
        elif readiness_payload.get("command") is not None:
            raise HostServiceError("host-service-contract-invalid", f"{label}.readiness.command is only valid in command mode")
        readiness = ReadinessSpec(
            mode=mode,
            command_path=readiness_command,
            timeout_seconds=_positive_number(
                readiness_payload.get("timeout_seconds"),
                default=10.0,
                label=f"{label}.readiness.timeout_seconds",
            ),
            interval_seconds=_positive_number(
                readiness_payload.get("interval_seconds"),
                default=0.25,
                label=f"{label}.readiness.interval_seconds",
            ),
            probe_timeout_seconds=_positive_number(
                readiness_payload.get("probe_timeout_seconds"),
                default=5.0,
                label=f"{label}.readiness.probe_timeout_seconds",
            ),
        )
        digest_payload = {
            "id": service_id,
            "command": declaration["command"],
            "command_sha256": _file_sha256(command_path),
            "readiness": {
                "mode": readiness.mode,
                "command": readiness_payload.get("command"),
                "command_sha256": _file_sha256(readiness_command) if readiness_command else None,
                "timeout_seconds": readiness.timeout_seconds,
                "interval_seconds": readiness.interval_seconds,
                "probe_timeout_seconds": readiness.probe_timeout_seconds,
            },
            "source_revisions": {
                repo: {
                    "head_sha": revision.get("head_sha"),
                    "working_tree_sha256": revision.get("working_tree_sha256"),
                }
                for repo, revision in sorted((source_revisions or {}).items())
            },
        }
        command_digest = f"sha256:{hashlib.sha256(json.dumps(digest_payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}"
        specs.append(
            HostServiceSpec(
                service_id=service_id,
                command_path=command_path,
                command_digest=command_digest,
                readiness=readiness,
            )
        )
    return specs


def _service_paths(state_root: Path, service_id: str) -> tuple[Path, Path]:
    service_root = state_root / "host-services" / service_id
    return service_root / "service.yaml", service_root / "service.log"


@contextmanager
def _exclusive_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _profile_lock_path(state_root: Path) -> Path:
    return state_root / "host-services" / "lifecycle.lock"


def _service_lock_path(state_root: Path, service_id: str) -> Path:
    state_path, _ = _service_paths(state_root, service_id)
    return state_path.with_name("service.lock")


def _recorded_service_ids(state_root: Path) -> list[str]:
    services_root = state_root / "host-services"
    if not services_root.is_dir():
        return []
    return sorted(
        entry.name
        for entry in services_root.iterdir()
        if entry.is_dir()
        and SERVICE_ID_PATTERN.fullmatch(entry.name)
        and (entry / "service.yaml").is_file()
    )


def _recorded_service_requires_reconciliation(state_root: Path, service_id: str) -> bool:
    state_path, _ = _service_paths(state_root, service_id)
    state = _load_state(state_path)
    return not (
        state.get("status") == "stopped"
        and state.get("pid") is None
        and state.get("process_start_ticks") is None
    )


def _write_private_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise HostServiceError("host-service-state-invalid", f"host service state is not a mapping: {path}")
    return payload


def _process_start_ticks(pid: int) -> str | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return None
    close = raw.rfind(")")
    if close < 0:
        return None
    fields = raw[close + 2 :].split()
    if len(fields) <= 19 or fields[0] == "Z":
        return None
    return fields[19]


def _boot_id() -> str:
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError, OSError) as exc:
        raise HostServiceError(
            "host-service-identity-unavailable",
            "Linux boot identity is unavailable",
        ) from exc
    if not boot_id:
        raise HostServiceError(
            "host-service-identity-unavailable",
            "Linux boot identity is empty",
        )
    return boot_id


def _identity_status(state: dict) -> str:
    pid = state.get("pid")
    expected_ticks = state.get("process_start_ticks")
    expected_boot_id = state.get("boot_id")
    if (
        not isinstance(pid, int)
        or pid <= 0
        or not isinstance(expected_ticks, str)
        or not isinstance(expected_boot_id, str)
    ):
        return "not-running"
    if expected_boot_id != _boot_id():
        return "not-running"
    actual_ticks = _process_start_ticks(pid)
    if actual_ticks is None:
        return "not-running"
    if actual_ticks != expected_ticks:
        return "identity-mismatch"
    return "running"


def _group_alive(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_group(pid: int, timeout: float = 3.0) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _group_alive(pid):
            return
        time.sleep(0.05)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and _group_alive(pid):
        time.sleep(0.05)


def _probe(spec: HostServiceSpec, state: dict, *, cwd: Path, env: dict[str, str]) -> tuple[bool, str]:
    if _identity_status(state) != "running":
        return False, "process-not-running"
    if spec.readiness.mode == "process":
        return True, "process-alive"
    assert spec.readiness.command_path is not None
    probe_env = {
        **env,
        "DEVINT_HOST_SERVICE_ID": spec.service_id,
        "DEVINT_HOST_SERVICE_PID": str(state["pid"]),
        "DEVINT_HOST_SERVICE_STATE_FILE": str(state["state_file"]),
        "DEVINT_HOST_SERVICE_LOG_FILE": str(state["log_path"]),
    }
    try:
        process = subprocess.Popen(
            _command(spec.readiness.command_path),
            cwd=str(cwd),
            env=probe_env,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as exc:
        return False, f"readiness-probe-launch-failed:{exc.__class__.__name__}"
    try:
        output, _ = process.communicate(timeout=spec.readiness.probe_timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_group(process.pid)
        return False, "readiness-probe-timeout"
    finally:
        _terminate_group(process.pid)
    detail = (output or "").strip().replace("\n", " ")[-500:]
    if process.returncode == 0:
        return True, detail or "readiness-command-passed"
    return False, detail or f"readiness-command-exit-{process.returncode}"


def _projection(spec: HostServiceSpec, state: dict, *, healthy: bool, status: str, detail: str) -> dict:
    return {
        "id": spec.service_id,
        "status": status,
        "healthy": healthy,
        "pid": state.get("pid"),
        "process_start_ticks": state.get("process_start_ticks"),
        "boot_id": state.get("boot_id"),
        "command_digest": state.get("command_digest") or spec.command_digest,
        "log_path": state.get("log_path"),
        "readiness": {
            "mode": spec.readiness.mode,
            "status": "ready" if healthy else "not-ready",
            "detail": detail,
            "checked_at": now_utc(),
        },
    }


def inspect_host_service(
    spec: HostServiceSpec,
    *,
    state_root: Path,
    cwd: Path,
    env: dict[str, str],
) -> dict:
    state_path, log_path = _service_paths(state_root, spec.service_id)
    state = _load_state(state_path)
    state_exists = bool(state)
    state.setdefault("state_file", str(state_path))
    state.setdefault("log_path", str(log_path))
    identity = _identity_status(state)
    if identity == "identity-mismatch":
        return _projection(spec, state, healthy=False, status="identity-mismatch", detail="recorded PID belongs to a different process")
    if identity != "running":
        if not state_exists:
            status = "not-started"
        elif state.get("status") in {"failed", "stopped"}:
            status = state["status"]
        else:
            status = "stale"
        return _projection(spec, state, healthy=False, status=status, detail="process-not-running")
    if state.get("command_digest") != spec.command_digest:
        return _projection(spec, state, healthy=False, status="configuration-changed", detail="running command digest does not match the profile")
    healthy, detail = _probe(spec, state, cwd=cwd, env=env)
    return _projection(spec, state, healthy=healthy, status="running" if healthy else "unhealthy", detail=detail)


def _recorded_projection(
    service_id: str,
    state: dict,
    *,
    healthy: bool,
    status: str,
    detail: str,
) -> dict:
    readiness = state.get("readiness") if isinstance(state.get("readiness"), dict) else {}
    return {
        "id": service_id,
        "status": status,
        "healthy": healthy,
        "pid": state.get("pid"),
        "process_start_ticks": state.get("process_start_ticks"),
        "boot_id": state.get("boot_id"),
        "command_digest": state.get("command_digest"),
        "log_path": state.get("log_path"),
        "readiness": {
            "mode": readiness.get("mode") or state.get("readiness_mode") or "process",
            "status": "ready" if healthy else "not-ready",
            "detail": detail,
            "checked_at": now_utc(),
        },
    }


def inspect_recorded_host_service(service_id: str, *, state_root: Path) -> dict:
    state_path, log_path = _service_paths(state_root, service_id)
    state = _load_state(state_path)
    state.setdefault("state_file", str(state_path))
    state.setdefault("log_path", str(log_path))
    identity = _identity_status(state)
    if identity == "identity-mismatch":
        return _recorded_projection(
            service_id,
            state,
            healthy=False,
            status="identity-mismatch",
            detail="recorded PID belongs to a different process",
        )
    return _recorded_projection(
        service_id,
        state,
        healthy=False,
        status="undeclared" if identity == "running" else "stale-undeclared",
        detail="service is no longer declared by the selected profile",
    )


def _stop_host_service_unlocked(
    service_id: str,
    *,
    state_root: Path,
    spec: HostServiceSpec | None = None,
) -> dict:
    state_path, log_path = _service_paths(state_root, service_id)
    state = _load_state(state_path)
    state.setdefault("state_file", str(state_path))
    state.setdefault("log_path", str(log_path))
    identity = _identity_status(state)
    if identity == "identity-mismatch":
        raise HostServiceError("host-service-identity-mismatch", f"refusing to stop {service_id}: recorded PID belongs to a different process")
    pid = state.get("pid")
    has_recorded_identity = isinstance(pid, int) and pid > 0 and isinstance(
        state.get("process_start_ticks"), str
    ) and state.get("boot_id") == _boot_id()
    if identity == "running" or (has_recorded_identity and _group_alive(pid)):
        _terminate_group(state["pid"])
        if _group_alive(state["pid"]):
            raise HostServiceError("host-service-stop-failed", f"host service {service_id} did not stop")
    stopped = {
        **state,
        "schema_version": 1,
        "service_id": service_id,
        "status": "stopped",
        "pid": None,
        "process_start_ticks": None,
        "boot_id": state.get("boot_id") or _boot_id(),
        "command_digest": state.get("command_digest") or (spec.command_digest if spec else None),
        "state_file": str(state_path),
        "log_path": str(log_path),
        "updated_at": now_utc(),
    }
    _write_private_yaml(state_path, stopped)
    if spec is not None:
        return _projection(spec, stopped, healthy=False, status="stopped", detail="service-stopped")
    return _recorded_projection(
        service_id,
        stopped,
        healthy=False,
        status="stopped",
        detail="service-stopped",
    )


def stop_host_service(spec: HostServiceSpec, *, state_root: Path) -> dict:
    with _exclusive_lock(_profile_lock_path(state_root)):
        with _exclusive_lock(_service_lock_path(state_root, spec.service_id)):
            return _stop_host_service_unlocked(
                spec.service_id,
                state_root=state_root,
                spec=spec,
            )


def _start_host_service_unlocked(
    spec: HostServiceSpec,
    *,
    state_root: Path,
    cwd: Path,
    env: dict[str, str],
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    current = inspect_host_service(spec, state_root=state_root, cwd=cwd, env=env)
    if current["healthy"]:
        return current
    if current["status"] == "identity-mismatch":
        raise HostServiceError("host-service-identity-mismatch", f"refusing to replace {spec.service_id}: recorded PID belongs to a different process")
    state_path, log_path = _service_paths(state_root, spec.service_id)
    old_state = _load_state(state_path)
    if _identity_status(old_state) == "running":
        _stop_host_service_unlocked(
            spec.service_id,
            state_root=state_root,
            spec=spec,
        )
    service_env = {
        **env,
        "DEVINT_HOST_SERVICE_ID": spec.service_id,
        "DEVINT_HOST_SERVICE_STATE_FILE": str(state_path),
        "DEVINT_HOST_SERVICE_LOG_FILE": str(log_path),
    }
    try:
        service_pid = _spawn_detached(
            _command(spec.command_path),
            cwd=cwd,
            env=service_env,
            log_path=log_path,
        )
    except OSError as exc:
        raise HostServiceError(
            "host-service-start-failed",
            f"host service {spec.service_id} could not be launched: {exc}",
        ) from exc
    process_start_ticks = _process_start_ticks(service_pid)
    if process_start_ticks is None:
        _terminate_group(service_pid)
        raise HostServiceError("host-service-start-failed", f"host service {spec.service_id} exited before identity could be recorded")
    state = {
        "schema_version": 1,
        "service_id": spec.service_id,
        "status": "starting",
        "pid": service_pid,
        "process_start_ticks": process_start_ticks,
        "boot_id": _boot_id(),
        "command_digest": spec.command_digest,
        "command_path": str(spec.command_path),
        "readiness_mode": spec.readiness.mode,
        "state_file": str(state_path),
        "log_path": str(log_path),
        "started_at": now_utc(),
        "updated_at": now_utc(),
    }
    try:
        _write_private_yaml(state_path, state)
    except BaseException:
        _terminate_group(service_pid)
        raise
    deadline = time.monotonic() + spec.readiness.timeout_seconds
    last_detail = "readiness-not-checked"
    while time.monotonic() < deadline:
        healthy, last_detail = _probe(spec, state, cwd=cwd, env=env)
        if healthy:
            running = {
                **state,
                "status": "running",
                "updated_at": now_utc(),
                "readiness": {
                    "mode": spec.readiness.mode,
                    "status": "ready",
                    "detail": last_detail,
                    "checked_at": now_utc(),
                },
            }
            _write_private_yaml(state_path, running)
            return _projection(spec, running, healthy=True, status="running", detail=last_detail)
        sleep(spec.readiness.interval_seconds)
    try:
        _stop_host_service_unlocked(
            spec.service_id,
            state_root=state_root,
            spec=spec,
        )
    finally:
        failed = {
            **state,
            "status": "failed",
            "pid": None,
            "process_start_ticks": None,
            "updated_at": now_utc(),
            "readiness": {
                "mode": spec.readiness.mode,
                "status": "not-ready",
                "detail": last_detail,
                "checked_at": now_utc(),
            },
        }
        _write_private_yaml(state_path, failed)
    raise HostServiceError("host-service-readiness-failed", f"host service {spec.service_id} did not become ready: {last_detail}")


def start_host_service(
    spec: HostServiceSpec,
    *,
    state_root: Path,
    cwd: Path,
    env: dict[str, str],
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    with _exclusive_lock(_profile_lock_path(state_root)):
        with _exclusive_lock(_service_lock_path(state_root, spec.service_id)):
            return _start_host_service_unlocked(
                spec,
                state_root=state_root,
                cwd=cwd,
                env=env,
                sleep=sleep,
            )


def reconcile_host_services(
    specs: list[HostServiceSpec],
    *,
    state_root: Path,
    cwd: Path,
    env: dict[str, str],
) -> list[dict]:
    with _exclusive_lock(_profile_lock_path(state_root)):
        projections: list[dict] = []
        declared_ids = {spec.service_id for spec in specs}
        for service_id in _recorded_service_ids(state_root):
            if service_id in declared_ids or not _recorded_service_requires_reconciliation(
                state_root,
                service_id,
            ):
                continue
            with _exclusive_lock(_service_lock_path(state_root, service_id)):
                projections.append(
                    _stop_host_service_unlocked(service_id, state_root=state_root)
                )
        for spec in specs:
            with _exclusive_lock(_service_lock_path(state_root, spec.service_id)):
                projections.append(
                    _start_host_service_unlocked(
                        spec,
                        state_root=state_root,
                        cwd=cwd,
                        env=env,
                    )
                )
        return projections


def inspect_host_services(
    specs: list[HostServiceSpec],
    *,
    state_root: Path,
    cwd: Path,
    env: dict[str, str],
) -> list[dict]:
    with _exclusive_lock(_profile_lock_path(state_root)):
        projections = [
            inspect_host_service(spec, state_root=state_root, cwd=cwd, env=env)
            for spec in specs
        ]
        declared_ids = {spec.service_id for spec in specs}
        projections.extend(
            inspect_recorded_host_service(service_id, state_root=state_root)
            for service_id in _recorded_service_ids(state_root)
            if service_id not in declared_ids
            and _recorded_service_requires_reconciliation(state_root, service_id)
        )
        return projections


def stop_host_services(specs: list[HostServiceSpec], *, state_root: Path) -> list[dict]:
    with _exclusive_lock(_profile_lock_path(state_root)):
        projections: list[dict] = []
        errors: list[str] = []
        specs_by_id = {spec.service_id: spec for spec in specs}
        service_ids = list(specs_by_id)
        service_ids.extend(
            service_id
            for service_id in _recorded_service_ids(state_root)
            if service_id not in specs_by_id
            and _recorded_service_requires_reconciliation(state_root, service_id)
        )
        for service_id in reversed(service_ids):
            spec = specs_by_id.get(service_id)
            try:
                with _exclusive_lock(_service_lock_path(state_root, service_id)):
                    projections.append(
                        _stop_host_service_unlocked(
                            service_id,
                            state_root=state_root,
                            spec=spec,
                        )
                    )
            except HostServiceError as exc:
                errors.append(f"{service_id}: {exc}")
        if errors:
            raise HostServiceError("host-service-stop-failed", "; ".join(errors))
        return list(reversed(projections))


def render_host_service_status(projections: list[dict]) -> None:
    for projection in projections:
        print(
            "host service: "
            f"id={projection['id']} status={projection['status']} "
            f"healthy={str(projection['healthy']).lower()} "
            f"pid={projection['pid'] or '-'} "
            f"readiness={projection['readiness']['detail']} "
            f"log={projection['log_path'] or '-'}"
        )
