#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
from typing import Protocol
from uuid import uuid4

import yaml

from dev_integration_host_services import (
    HostServiceError,
    inspect_host_services,
    reconcile_host_services,
    render_host_service_status,
    resolve_host_services,
    stop_host_services,
)
from dev_integration_compositions import (
    bounded_child_environment,
    CompositionError,
    composition_state_root,
    execute_composition,
    resolve_runtime_composition,
)


ACTIONS = {
    "access": "access",
    "backup": "backup",
    "up": "up",
    "status": "status",
    "smoke": "smoke",
    "down": "down",
    "reset": "reset",
    "restore": "restore",
    "promote-check": "promote_check",
}

ACTIVE_ONLY_ACTIONS = {"access", "backup", "restore", "up", "smoke"}
READ_ONLY_ACTIONS = {"status"}


class DigestWriter(Protocol):
    def update(self, value: bytes) -> None: ...


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def dump_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False))


def dump_yaml_exclusive(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(yaml.safe_dump(payload, sort_keys=False))
    path.chmod(0o600)


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        capture_output=True,
    )
    output = (result.stdout or "").strip()
    if output:
        return output
    return (result.stderr or "").strip()


def run_bytes(cmd: list[str], *, cwd: Path | None = None) -> bytes:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
    ).stdout


def _add_digest_field(digest: DigestWriter, label: bytes, value: bytes) -> None:
    digest.update(len(label).to_bytes(4, "big"))
    digest.update(label)
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def working_tree_sha256(repo_root: Path) -> str:
    changed_paths = run_bytes(
        [
            "git",
            "-C",
            str(repo_root),
            "diff",
            "--name-only",
            "-z",
            "--no-renames",
            "--no-ext-diff",
            "--no-textconv",
            "HEAD",
            "--",
        ]
    ).split(b"\0")
    untracked_paths = run_bytes(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
        ]
    ).split(b"\0")
    digest = hashlib.sha256()
    for raw_path in sorted({path for path in (*changed_paths, *untracked_paths) if path}):
        path = repo_root / os.fsdecode(raw_path)
        _add_digest_field(digest, b"path", raw_path)
        try:
            path_stat = path.lstat()
        except FileNotFoundError:
            _add_digest_field(digest, b"kind", b"missing")
            continue
        _add_digest_field(digest, b"mode", f"{stat.S_IMODE(path_stat.st_mode):04o}".encode())
        if stat.S_ISREG(path_stat.st_mode):
            content_digest = hashlib.sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    content_digest.update(chunk)
            _add_digest_field(digest, b"kind", b"file")
            _add_digest_field(digest, b"content_sha256", content_digest.digest())
        elif stat.S_ISLNK(path_stat.st_mode):
            _add_digest_field(digest, b"kind", b"symlink")
            _add_digest_field(digest, b"target", os.fsencode(os.readlink(path)))
        elif stat.S_ISDIR(path_stat.st_mode):
            submodule_head = run_bytes(
                ["git", "-C", str(path), "rev-parse", "HEAD"]
            ).strip()
            submodule_dirty = bool(
                run_bytes(
                    [
                        "git",
                        "-C",
                        str(path),
                        "status",
                        "--porcelain=v1",
                        "-z",
                        "--untracked-files=all",
                    ]
                )
            )
            _add_digest_field(digest, b"kind", b"submodule")
            _add_digest_field(digest, b"submodule_head", submodule_head)
            if submodule_dirty:
                _add_digest_field(
                    digest,
                    b"submodule_working_tree_sha256",
                    working_tree_sha256(path).encode(),
                )
        else:
            raise SystemExit(f"Unsupported Git-visible source path type: {path}")
    return digest.hexdigest()


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", value.lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "devint"


def now_utc() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_repo_overrides(entries: list[str]) -> dict[str, Path]:
    overrides: dict[str, Path] = {}
    for entry in entries:
        if "=" not in entry:
            raise SystemExit(f"--repo-path entries must look like repo=/abs/path, got {entry!r}")
        repo_name, raw_path = entry.split("=", 1)
        repo_name = repo_name.strip()
        raw_path = raw_path.strip()
        if not repo_name or not raw_path:
            raise SystemExit(f"--repo-path entries must look like repo=/abs/path, got {entry!r}")
        overrides[repo_name] = Path(raw_path).expanduser().resolve()
    return overrides


def reexec_from_selected_platform_checkout(
    repo_overrides: dict[str, Path],
    *,
    workspace_root: Path,
) -> None:
    selected_root = repo_overrides.get("platform-engineering")
    if selected_root is None:
        return
    selected_runner = resolve_owner_file(
        selected_root,
        "scripts/dev_integration.py",
        description="Selected Platform runner",
    )
    current_runner = Path(__file__).resolve()
    if selected_runner == current_runner:
        return
    forwarded_args = list(sys.argv[1:])
    if not any(
        arg == "--workspace-root" or arg.startswith("--workspace-root=")
        for arg in forwarded_args
    ):
        forwarded_args.extend(["--workspace-root", str(workspace_root)])
    os.execv(
        sys.executable,
        [sys.executable, str(selected_runner), *forwarded_args],
    )
    raise RuntimeError("failed to execute the selected Platform runner")


def git_state(repo_root: Path, *, workspace_root: Path) -> dict:
    branch = run(["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"])
    head_sha = run(["git", "-C", str(repo_root), "rev-parse", "HEAD"])
    dirty = bool(run(["git", "-C", str(repo_root), "status", "--short"], check=False))
    top_level = Path(
        run(["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"])
    ).resolve()
    git_dir = run(["git", "-C", str(repo_root), "rev-parse", "--git-dir"])
    common_dir = run(["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"])
    git_dir_path = (
        (repo_root / git_dir).resolve() if not Path(git_dir).is_absolute() else Path(git_dir)
    )
    common_dir_path = (
        (repo_root / common_dir).resolve()
        if not Path(common_dir).is_absolute()
        else Path(common_dir)
    )
    default_repo_root = (workspace_root / repo_root.name).resolve()
    try:
        upstream = run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]
        )
    except subprocess.CalledProcessError:
        upstream = None

    return {
        "branch": branch,
        "dirty": dirty,
        "git_common_dir": str(common_dir_path),
        "git_dir": str(git_dir_path),
        "head_sha": head_sha,
        "path": str(repo_root),
        "path_override": repo_root != default_repo_root,
        "top_level": str(top_level),
        "upstream": upstream,
        "uses_worktree": git_dir_path != common_dir_path,
        "working_tree_sha256": working_tree_sha256(repo_root) if dirty else None,
    }


def load_registry(
    workspace_root: Path,
    repo_overrides: dict[str, Path],
) -> tuple[dict, dict]:
    governance_root = repo_overrides.get(
        "workspace-governance",
        workspace_root / "workspace-governance",
    ).resolve()
    policy_path = resolve_owner_file(
        governance_root,
        "contracts/developer-integration-policy.yaml",
        description="Dev-integration lifecycle policy",
    )
    registry_path = resolve_owner_file(
        governance_root,
        "contracts/developer-integration-profiles.yaml",
        description="Dev-integration profile registry",
    )
    policy = load_yaml(policy_path)
    registry = load_yaml(registry_path)
    return policy, registry


def resolve_owner_file(
    owner_repo_root: Path,
    configured_path: str,
    *,
    description: str,
) -> Path:
    relative_path = Path(configured_path)
    if relative_path.is_absolute():
        raise SystemExit(f"{description} must be owner-relative: {configured_path}")
    try:
        resolved_path = (owner_repo_root / relative_path).resolve(strict=True)
    except FileNotFoundError as exc:
        raise SystemExit(f"{description} is unavailable: {configured_path}") from exc
    try:
        resolved_path.relative_to(owner_repo_root)
    except ValueError as exc:
        raise SystemExit(
            f"{description} escapes the selected owner checkout: {configured_path}"
        ) from exc
    if not resolved_path.is_file():
        raise SystemExit(f"{description} is not a file: {configured_path}")
    return resolved_path


def resolve_profile(
    *,
    action: str,
    workspace_root: Path,
    profile_id: str,
    repo_overrides: dict[str, Path],
) -> tuple[dict, dict, Path, Path, dict[str, Path], dict[str, dict]]:
    policy, registry = load_registry(workspace_root, repo_overrides)
    try:
        entry = registry["profiles"][profile_id]
    except KeyError as exc:
        raise SystemExit(f"Unknown dev-integration profile {profile_id!r}") from exc
    launchable_statuses = set(policy["profile_lifecycle"]["self_serve_statuses"])
    lifecycle = entry["lifecycle"]
    if action in ACTIVE_ONLY_ACTIONS and lifecycle not in launchable_statuses:
        raise SystemExit(
            "dev-integration profile "
            f"{profile_id!r} is {lifecycle!r} and cannot run action {action!r}. "
            "Request or complete admission first, then activate the profile before launching or rehearsing it from the shared runner."
        )

    owner_repo_root = repo_overrides.get(
        entry["owner_repo"],
        workspace_root / entry["owner_repo"],
    ).resolve()
    if not owner_repo_root.exists():
        raise SystemExit(
            f"Owner repo path for {entry['owner_repo']!r} does not exist: "
            f"{owner_repo_root}"
        )
    profile_path = resolve_owner_file(
        owner_repo_root,
        entry["profile_path"],
        description=f"Profile {profile_id!r}",
    )
    profile = load_yaml(profile_path)

    repo_paths: dict[str, Path] = {}
    repo_states: dict[str, dict] = {}

    def record_source_repo(repo_name: str, repo_path: Path) -> None:
        repo_path = repo_path.resolve()
        if repo_name in repo_paths:
            if repo_paths[repo_name] != repo_path:
                raise SystemExit(
                    f"Source repo {repo_name!r} resolves to conflicting checkouts"
                )
            return
        if not repo_path.exists():
            raise SystemExit(f"Source repo path for {repo_name!r} does not exist: {repo_path}")
        repo_paths[repo_name] = repo_path
        repo_states[repo_name] = git_state(repo_path, workspace_root=workspace_root)

    for raw_entry in profile["source_repos"]:
        repo_name = raw_entry["repo"] if isinstance(raw_entry, dict) else raw_entry
        record_source_repo(
            repo_name,
            repo_overrides.get(repo_name, workspace_root / repo_name),
        )

    record_source_repo(
        "workspace-governance",
        repo_overrides.get("workspace-governance", workspace_root / "workspace-governance"),
    )
    record_source_repo(
        "platform-engineering",
        repo_overrides.get("platform-engineering", Path(__file__).resolve().parents[1]),
    )
    if repo_states["platform-engineering"]["dirty"]:
        raise SystemExit(
            "Selected Platform runner checkout must be clean so execution provenance "
            "is bound to its recorded Git head"
        )

    if repo_paths.get(entry["owner_repo"]) != owner_repo_root:
        raise SystemExit(
            f"Profile {profile_id!r} must declare its selected owner repo "
            f"{entry['owner_repo']!r} as a source repo"
        )

    return entry, profile, owner_repo_root, profile_path, repo_paths, repo_states


def compute_namespace(profile: dict, profile_id: str, operator: str) -> str:
    pattern = profile["runtime"].get("namespace_pattern", "devint-{profile}-{operator}")
    rendered = pattern.format(profile=profile_id, operator=operator)
    return slugify(rendered)[:63]


def smoke_testing(profile: dict) -> dict:
    return ((profile.get("testing") or {}).get("smoke") or {})


def session_paths(workspace_root: Path, profile_id: str, operator: str) -> dict[str, Path]:
    base_root = workspace_root / ".dev-integration"
    state_root = base_root / slugify(profile_id) / slugify(operator)
    sessions_root = base_root / "sessions"
    return {
        "base_root": base_root,
        "state_root": state_root,
        "current_manifest": state_root / "current-session.yaml",
        "sessions_root": sessions_root,
    }


def build_manifest(
    *,
    action: str,
    entry: dict,
    operator: str,
    namespace: str,
    profile: dict,
    profile_id: str,
    profile_path: Path,
    repo_states: dict[str, dict],
    session_id: str,
    state_root: Path,
    workspace_root: Path,
) -> dict:
    execution_id = (
        f"{session_id}-{slugify(action)}-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-"
        f"{uuid4().hex[:8]}"
    )
    manifest = {
        "schema_version": 1,
        "lane": "dev-integration",
        "profile_id": profile_id,
        "profile_lifecycle": entry["lifecycle"],
        "runtime_state_model": profile.get("runtime", {}).get("state_model", "disposable"),
        "profile_path": str(profile_path),
        "summary": profile["summary"],
        "owner_repo": entry["owner_repo"],
        "runtime_owner": entry["runtime_owner"],
        "security_owner": entry["security_owner"],
        "action": action,
        "execution_id": execution_id,
        "operator": operator,
        "namespace": namespace,
        "session_id": session_id,
        "created_at": now_utc(),
        "workspace_root": str(workspace_root),
        "state_root": str(state_root),
        "stage_handoff": profile["stage_handoff"],
        "source_repos": repo_states,
    }
    composition_id = os.environ.get("DEVINT_COMPOSITION_ID")
    if composition_id:
        manifest["runtime_composition_id"] = composition_id
        manifest["runtime_composition_root_profile_id"] = os.environ.get(
            "DEVINT_COMPOSITION_ROOT_PROFILE_ID"
        )
    return manifest


def prepare_session_files(
    *,
    manifest: dict,
    current_manifest: Path,
    sessions_root: Path,
) -> tuple[Path, Path, bytes]:
    current_manifest.parent.mkdir(parents=True, exist_ok=True)
    session_root = sessions_root / manifest["session_id"]
    archive_path = session_root / f"{manifest['execution_id']}.manifest.yaml"
    result_path = session_root / f"{manifest['execution_id']}.result.yaml"
    manifest_snapshot = yaml.safe_dump(manifest, sort_keys=False).encode()
    current_manifest.write_bytes(manifest_snapshot)
    current_manifest.chmod(0o600)
    return archive_path, result_path, manifest_snapshot


def prepare_action_session_files(
    *,
    action: str,
    manifest: dict,
    current_manifest: Path,
    sessions_root: Path,
) -> tuple[Path, Path, bytes] | None:
    """Create action evidence only for commands that can change local state."""

    if action in READ_ONLY_ACTIONS:
        return None
    return prepare_session_files(
        manifest=manifest,
        current_manifest=current_manifest,
        sessions_root=sessions_root,
    )


def write_execution_result(
    *,
    manifest_snapshot: bytes,
    manifest_path: Path,
    result_path: Path,
    returncode: int,
) -> None:
    manifest = yaml.safe_load(manifest_snapshot)
    if not isinstance(manifest, dict):
        raise SystemExit("Archived dev-integration source manifest must be a mapping.")
    payload = {
        "schema_version": 1,
        "lane": "dev-integration",
        "profile_id": manifest["profile_id"],
        "session_id": manifest["session_id"],
        "execution_id": manifest["execution_id"],
        "action": manifest["action"],
        "result": "succeeded" if returncode == 0 else "failed",
        "returncode": returncode,
        "manifest_path": str(manifest_path),
        "manifest_sha256": hashlib.sha256(manifest_snapshot).hexdigest(),
        "source_manifest": manifest,
        "completed_at": now_utc(),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("xb") as stream:
        stream.write(manifest_snapshot)
        stream.flush()
        os.fsync(stream.fileno())
    manifest_path.chmod(0o400)
    dump_yaml_exclusive(result_path, payload)
    result_path.chmod(0o400)


def render_promotion_report(
    *,
    manifest: dict,
    report_path: Path,
) -> None:
    dirty_repos = sorted(
        repo_name
        for repo_name, payload in manifest["source_repos"].items()
        if payload["dirty"]
    )
    repos_without_upstream = sorted(
        repo_name
        for repo_name, payload in manifest["source_repos"].items()
        if not payload["upstream"]
    )
    report = {
        "schema_version": 1,
        "lane": "dev-integration",
        "profile_id": manifest["profile_id"],
        "session_id": manifest["session_id"],
        "namespace": manifest["namespace"],
        "owner_repo": manifest["owner_repo"],
        "runtime_owner": manifest["runtime_owner"],
        "stage_handoff": manifest["stage_handoff"],
        "blocking_conditions": {
            "dirty_repos": dirty_repos,
            "repos_without_upstream": repos_without_upstream,
        },
        "source_repos": manifest["source_repos"],
        "generated_at": now_utc(),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    dump_yaml(report_path, report)


def terminate_process_group(process_group_id: int, timeout: float = 2.0) -> None:
    try:
        os.killpg(process_group_id, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.killpg(process_group_id, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    try:
        os.killpg(process_group_id, signal.SIGKILL)
    except ProcessLookupError:
        pass


def dispatch_command(
    command_path: Path,
    *,
    cwd: Path,
    env: dict[str, str],
    publish_result: Callable[[int], int | None] | None = None,
) -> int:
    if command_path.suffix == ".sh":
        command = ["bash", str(command_path)]
    elif command_path.suffix == ".py":
        command = ["python3", str(command_path)]
    else:
        command = [str(command_path)]
    process: subprocess.Popen[str] | None = None
    received_signal: int | None = None

    def stop_action(signum: int, _frame: object) -> None:
        nonlocal received_signal
        received_signal = signum
        if process is not None:
            terminate_process_group(process.pid)

    previous_handlers = {
        signum: signal.signal(signum, stop_action)
        for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)
    }
    try:
        if received_signal is not None:
            returncode = 128 + received_signal
        else:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                env=env,
                start_new_session=True,
                text=True,
            )
            if received_signal is not None:
                terminate_process_group(process.pid)
            returncode = process.wait()
            terminate_process_group(process.pid)
            process = None
        if received_signal is not None:
            returncode = 128 + received_signal
        if publish_result is not None:
            published_returncode = publish_result(returncode)
            if isinstance(published_returncode, int):
                returncode = published_returncode
        if received_signal is not None:
            returncode = 128 + received_signal
        return returncode
    finally:
        if process is not None:
            terminate_process_group(process.pid)
        for signum, previous_handler in previous_handlers.items():
            signal.signal(signum, previous_handler)


def run_runtime_composition(
    *,
    action: str,
    composition_id: str,
    operator: str,
    repo_overrides: dict[str, Path],
    workspace_root: Path,
) -> int:
    _, registry = load_registry(workspace_root, repo_overrides)
    try:
        composition, profile_order = resolve_runtime_composition(
            registry,
            composition_id,
        )
    except CompositionError as exc:
        raise SystemExit(f"{exc.code}: {exc}") from exc

    runner_root = Path(__file__).resolve().parents[1]
    if git_state(runner_root, workspace_root=workspace_root)["dirty"]:
        raise SystemExit(
            "Selected Platform runner checkout must be clean so composition "
            "execution provenance is bound to its recorded Git head"
        )

    namespaces: dict[str, str] = {}
    for profile_id in profile_order:
        entry = registry["profiles"][profile_id]
        owner_root = repo_overrides.get(
            entry["owner_repo"],
            workspace_root / entry["owner_repo"],
        ).resolve()
        profile_path = resolve_owner_file(
            owner_root,
            entry["profile_path"],
            description=f"Composition profile {profile_id!r}",
        )
        profile = load_yaml(profile_path)
        namespaces[profile_id] = compute_namespace(profile, profile_id, operator)

    forwarded_repo_paths: list[str] = []
    for repo_name, repo_path in sorted(repo_overrides.items()):
        forwarded_repo_paths.extend(["--repo-path", f"{repo_name}={repo_path}"])

    def dispatch(
        child_action: str,
        profile_id: str,
        projection_environment: Mapping[str, str],
    ) -> int:
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            child_action,
            "--profile",
            profile_id,
            "--workspace-root",
            str(workspace_root),
            "--operator",
            operator,
            *forwarded_repo_paths,
        ]
        child_environment = bounded_child_environment(
            composition,
            base_environment=os.environ,
            profile_environment={
                **projection_environment,
                "DEVINT_COMPOSITION_ID": composition_id,
                "DEVINT_COMPOSITION_ROOT_PROFILE_ID": composition["root_profile_id"],
            },
        )
        return subprocess.run(command, env=child_environment, check=False).returncode

    try:
        return execute_composition(
            action=action,
            composition_id=composition_id,
            composition=composition,
            profile_order=profile_order,
            namespaces=namespaces,
            operator=operator,
            state_root=composition_state_root(
                workspace_root,
                composition_id,
                operator,
            ),
            dispatch=dispatch,
        )
    except CompositionError as exc:
        raise SystemExit(f"{exc.code}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a shared dev-integration profile action.")
    parser.add_argument("action", choices=sorted(ACTIONS))
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--profile", help="registered dev-integration profile id")
    target.add_argument(
        "--composition",
        help="registered dev-integration runtime composition id",
    )
    parser.add_argument(
        "--workspace-root",
        default=Path(__file__).resolve().parents[2],
        type=Path,
        help="workspace root containing the owner repos",
    )
    parser.add_argument(
        "--operator",
        default=None,
        help="operator identity to embed in the session manifest; defaults to the local username",
    )
    parser.add_argument(
        "--repo-path",
        action="append",
        default=[],
        help="override one source repo root with repo=/abs/path, useful for git worktrees",
    )
    args = parser.parse_args()

    workspace_root = args.workspace_root.resolve()
    operator = args.operator or run(["whoami"])
    repo_overrides = parse_repo_overrides(args.repo_path)
    reexec_from_selected_platform_checkout(
        repo_overrides,
        workspace_root=workspace_root,
    )

    if args.composition:
        return run_runtime_composition(
            action=ACTIONS[args.action],
            composition_id=args.composition,
            operator=operator,
            repo_overrides=repo_overrides,
            workspace_root=workspace_root,
        )

    entry, profile, owner_repo_root, profile_path, repo_paths, repo_states = resolve_profile(
        action=ACTIONS[args.action],
        workspace_root=workspace_root,
        profile_id=args.profile,
        repo_overrides=repo_overrides,
    )
    try:
        host_service_specs = resolve_host_services(
            profile,
            owner_repo_root,
            source_revisions=repo_states,
        )
    except HostServiceError as exc:
        raise SystemExit(f"{exc.code}: {exc}") from exc
    if ACTIONS[args.action] == "smoke":
        state_model = (profile.get("runtime") or {}).get("state_model")
        mutation_mode = smoke_testing(profile).get("mutation_mode")
        companion_profile = smoke_testing(profile).get("companion_profile_id")
        if state_model == "persistent" and mutation_mode != "read-only":
            guidance = ""
            if companion_profile:
                guidance = (
                    f" Use the disposable companion profile instead: "
                    f"make devint-smoke PROFILE={companion_profile}."
                )
            raise SystemExit(
                f"Persistent dev-integration profile {args.profile!r} cannot run mutating smoke "
                f"against its working lane.{guidance}"
            )
    paths = session_paths(workspace_root, args.profile, operator)
    namespace = compute_namespace(profile, args.profile, operator)

    current_manifest_path = paths["current_manifest"]
    existing_manifest = load_yaml(current_manifest_path) if current_manifest_path.exists() else {}
    existing_operator = existing_manifest.get("operator")
    if existing_operator and existing_operator != operator:
        raise SystemExit(
            "Refusing dev-integration operator slug collision: "
            f"{operator!r} maps to state already owned by {existing_operator!r}"
        )
    existing_profile_id = existing_manifest.get("profile_id")
    if existing_profile_id and existing_profile_id != args.profile:
        raise SystemExit(
            "Refusing dev-integration profile slug collision: "
            f"{args.profile!r} maps to state already owned by {existing_profile_id!r}"
        )
    if existing_manifest.get("session_id") and args.action != "up":
        session_id = existing_manifest["session_id"]
    else:
        session_id = f"{slugify(args.profile)}-{slugify(operator)}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    manifest = build_manifest(
        action=ACTIONS[args.action],
        entry=entry,
        operator=operator,
        namespace=namespace,
        profile=profile,
        profile_id=args.profile,
        profile_path=profile_path,
        repo_states=repo_states,
        session_id=session_id,
        state_root=paths["state_root"],
        workspace_root=workspace_root,
    )
    manifest["host_services"] = []
    action_files = prepare_action_session_files(
        action=ACTIONS[args.action],
        manifest=manifest,
        current_manifest=current_manifest_path,
        sessions_root=paths["sessions_root"],
    )
    archive_path: Path | None = None
    result_path: Path | None = None
    if action_files is not None:
        archive_path, result_path, _ = action_files

    promotion_report_path = paths["state_root"] / "promotion-report.yaml"
    if ACTIONS[args.action] == "promote_check":
        render_promotion_report(manifest=manifest, report_path=promotion_report_path)

    env = dict(
        **os.environ,
        DEVINT_ACTION=ACTIONS[args.action],
        DEVINT_NAMESPACE=namespace,
        DEVINT_OPERATOR=operator,
        DEVINT_OWNER_REPO=entry["owner_repo"],
        DEVINT_OWNER_REPO_ROOT=str(owner_repo_root),
        DEVINT_PROFILE_FILE=str(profile_path),
        DEVINT_PROFILE_ID=args.profile,
        DEVINT_PROFILE_JSON=json.dumps(profile),
        DEVINT_PROMOTION_REPORT=str(promotion_report_path),
        DEVINT_REPO_PATHS_JSON=json.dumps({name: str(path) for name, path in repo_paths.items()}),
        DEVINT_REPO_STATES_JSON=json.dumps(repo_states),
        DEVINT_SESSION_FILE=str(current_manifest_path),
        DEVINT_SESSION_ID=session_id,
        DEVINT_STATE_ROOT=str(paths["state_root"]),
        DEVINT_WORKSPACE_ROOT=str(workspace_root),
    )
    env["DEVINT_HOST_SERVICES_JSON"] = json.dumps(
        [
            {
                "id": spec.service_id,
                "command_digest": spec.command_digest,
                "readiness_mode": spec.readiness.mode,
            }
            for spec in host_service_specs
        ]
    )

    command_key = ACTIONS[args.action]
    try:
        command_relpath = profile["commands"][command_key]
    except KeyError as exc:
        available_actions = ", ".join(sorted(profile.get("commands", {}).keys()))
        raise SystemExit(
            f"dev-integration profile {args.profile!r} does not implement action {command_key!r}. "
            f"Available actions: {available_actions or 'none'}."
        ) from exc
    command_path = resolve_owner_file(
        owner_repo_root,
        command_relpath,
        description=f"Profile {args.profile!r} action {command_key!r}",
    )
    lifecycle_error: HostServiceError | None = None
    host_service_projection: list[dict] = []
    if command_key in {"down", "reset"}:
        try:
            host_service_projection = stop_host_services(
                host_service_specs,
                state_root=paths["state_root"],
            )
        except HostServiceError as exc:
            lifecycle_error = exc
            print(f"{exc.code}: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    def publish_result(action_returncode: int) -> int:
        nonlocal host_service_projection, lifecycle_error
        final_returncode = action_returncode
        if command_key == "up":
            try:
                if action_returncode != 0:
                    host_service_projection = inspect_host_services(
                        host_service_specs,
                        state_root=paths["state_root"],
                        cwd=owner_repo_root,
                        env=env,
                    )
                else:
                    host_service_projection = reconcile_host_services(
                        host_service_specs,
                        state_root=paths["state_root"],
                        cwd=owner_repo_root,
                        env=env,
                    )
            except HostServiceError as exc:
                lifecycle_error = exc
                print(f"{exc.code}: {exc}", file=sys.stderr)
                try:
                    host_service_projection = inspect_host_services(
                        host_service_specs,
                        state_root=paths["state_root"],
                        cwd=owner_repo_root,
                        env=env,
                    )
                except HostServiceError as inspect_error:
                    print(f"{inspect_error.code}: {inspect_error}", file=sys.stderr)
        elif command_key == "status":
            try:
                host_service_projection = inspect_host_services(
                    host_service_specs,
                    state_root=paths["state_root"],
                    cwd=owner_repo_root,
                    env=env,
                )
            except HostServiceError as exc:
                lifecycle_error = exc
                print(f"{exc.code}: {exc}", file=sys.stderr)
        elif command_key not in {"down", "reset"}:
            try:
                host_service_projection = inspect_host_services(
                    host_service_specs,
                    state_root=paths["state_root"],
                    cwd=owner_repo_root,
                    env=env,
                )
            except HostServiceError as exc:
                lifecycle_error = exc
                print(f"{exc.code}: {exc}", file=sys.stderr)
        if host_service_projection:
            render_host_service_status(host_service_projection)
        if lifecycle_error is not None or (
            command_key == "status"
            and any(not projection["healthy"] for projection in host_service_projection)
        ):
            final_returncode = final_returncode or 1
        manifest["host_services"] = host_service_projection
        if action_files is not None:
            assert archive_path is not None and result_path is not None
            manifest_snapshot = yaml.safe_dump(manifest, sort_keys=False).encode()
            current_manifest_path.write_bytes(manifest_snapshot)
            current_manifest_path.chmod(0o600)
            write_execution_result(
                manifest_snapshot=manifest_snapshot,
                manifest_path=archive_path,
                result_path=result_path,
                returncode=final_returncode,
            )
        return final_returncode

    returncode = dispatch_command(
        command_path,
        cwd=owner_repo_root,
        env=env,
        publish_result=publish_result,
    )
    if returncode:
        raise SystemExit(returncode)

    print(
        "dev-integration action complete: "
        f"profile={args.profile} action={args.action} namespace={namespace} session={session_id}"
    )
    if action_files is not None:
        assert archive_path is not None and result_path is not None
        print(f"session manifest: {current_manifest_path}")
        print(f"archived action manifest: {archive_path}")
        print(f"action result: {result_path}")
    if ACTIONS[args.action] == "promote_check":
        print(f"promotion report: {promotion_report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
