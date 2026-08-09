#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from uuid import uuid4

import yaml


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
    selected_runner = (selected_root / "scripts/dev_integration.py").resolve()
    current_runner = Path(__file__).resolve()
    if selected_runner == current_runner:
        return
    if not selected_runner.is_file():
        raise SystemExit(
            "Selected platform-engineering checkout does not contain the shared "
            f"dev-integration runner: {selected_runner}"
        )
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
    }


def load_registry(
    workspace_root: Path,
    repo_overrides: dict[str, Path],
) -> tuple[dict, dict]:
    governance_root = repo_overrides.get(
        "workspace-governance",
        workspace_root / "workspace-governance",
    ).resolve()
    policy = load_yaml(governance_root / "contracts" / "developer-integration-policy.yaml")
    registry = load_yaml(governance_root / "contracts" / "developer-integration-profiles.yaml")
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
    for raw_entry in profile["source_repos"]:
        repo_name = raw_entry["repo"] if isinstance(raw_entry, dict) else raw_entry
        repo_path = repo_overrides.get(repo_name, workspace_root / repo_name).resolve()
        if not repo_path.exists():
            raise SystemExit(f"Source repo path for {repo_name!r} does not exist: {repo_path}")
        repo_paths[repo_name] = repo_path
        repo_states[repo_name] = git_state(repo_path, workspace_root=workspace_root)

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
    return {
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


def dispatch_command(command_path: Path, *, cwd: Path, env: dict[str, str]) -> int:
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
        for signum in (signal.SIGHUP, signal.SIGTERM)
    }
    try:
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
        if received_signal is not None:
            return 128 + received_signal
        return returncode
    finally:
        if process is not None:
            terminate_process_group(process.pid)
        for signum, previous_handler in previous_handlers.items():
            signal.signal(signum, previous_handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a shared dev-integration profile action.")
    parser.add_argument("action", choices=sorted(ACTIONS))
    parser.add_argument("--profile", required=True, help="registered dev-integration profile id")
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

    entry, profile, owner_repo_root, profile_path, repo_paths, repo_states = resolve_profile(
        action=ACTIONS[args.action],
        workspace_root=workspace_root,
        profile_id=args.profile,
        repo_overrides=repo_overrides,
    )
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
    archive_path, result_path, manifest_snapshot = prepare_session_files(
        manifest=manifest,
        current_manifest=current_manifest_path,
        sessions_root=paths["sessions_root"],
    )
    paths["sessions_root"].mkdir(parents=True, exist_ok=True)

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
    try:
        returncode = dispatch_command(
            command_path,
            cwd=owner_repo_root,
            env=env,
        )
    except KeyboardInterrupt:
        returncode = 130
    write_execution_result(
        manifest_snapshot=manifest_snapshot,
        manifest_path=archive_path,
        result_path=result_path,
        returncode=returncode,
    )
    if returncode:
        raise SystemExit(returncode)

    print(
        "dev-integration action complete: "
        f"profile={args.profile} action={args.action} namespace={namespace} session={session_id}"
    )
    print(f"session manifest: {current_manifest_path}")
    print(f"archived action manifest: {archive_path}")
    print(f"action result: {result_path}")
    if ACTIONS[args.action] == "promote_check":
        print(f"promotion report: {promotion_report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
