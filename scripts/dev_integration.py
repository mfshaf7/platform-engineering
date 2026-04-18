#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import yaml


ACTIONS = {
    "up": "up",
    "status": "status",
    "smoke": "smoke",
    "down": "down",
    "reset": "reset",
    "promote-check": "promote_check",
}


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def dump_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False))


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


def load_registry(workspace_root: Path) -> tuple[dict, dict]:
    governance_root = workspace_root / "workspace-governance"
    policy = load_yaml(governance_root / "contracts" / "developer-integration-policy.yaml")
    registry = load_yaml(governance_root / "contracts" / "developer-integration-profiles.yaml")
    return policy, registry


def resolve_profile(
    *,
    workspace_root: Path,
    profile_id: str,
    repo_overrides: dict[str, Path],
) -> tuple[dict, dict, Path, Path, dict[str, Path], dict[str, dict]]:
    _policy, registry = load_registry(workspace_root)
    try:
        entry = registry["profiles"][profile_id]
    except KeyError as exc:
        raise SystemExit(f"Unknown dev-integration profile {profile_id!r}") from exc

    owner_repo_root = workspace_root / entry["owner_repo"]
    profile_path = owner_repo_root / entry["profile_path"]
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

    return entry, profile, owner_repo_root, profile_path, repo_paths, repo_states


def compute_namespace(profile: dict, profile_id: str, operator: str) -> str:
    pattern = profile["runtime"].get("namespace_pattern", "devint-{profile}-{operator}")
    rendered = pattern.format(profile=profile_id, operator=operator)
    return slugify(rendered)[:63]


def session_paths(workspace_root: Path, profile_id: str, operator: str) -> dict[str, Path]:
    base_root = workspace_root / ".dev-integration"
    state_root = base_root / profile_id / operator
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
    return {
        "schema_version": 1,
        "lane": "dev-integration",
        "profile_id": profile_id,
        "profile_path": str(profile_path),
        "summary": profile["summary"],
        "owner_repo": entry["owner_repo"],
        "runtime_owner": entry["runtime_owner"],
        "security_owner": entry["security_owner"],
        "action": action,
        "operator": operator,
        "namespace": namespace,
        "session_id": session_id,
        "created_at": now_utc(),
        "workspace_root": str(workspace_root),
        "state_root": str(state_root),
        "stage_handoff": profile["stage_handoff"],
        "source_repos": repo_states,
    }


def write_session_files(
    *,
    manifest: dict,
    current_manifest: Path,
    sessions_root: Path,
) -> Path:
    current_manifest.parent.mkdir(parents=True, exist_ok=True)
    sessions_root.mkdir(parents=True, exist_ok=True)
    dump_yaml(current_manifest, manifest)
    archive_path = sessions_root / f"{manifest['session_id']}.yaml"
    dump_yaml(archive_path, manifest)
    return archive_path


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


def dispatch_command(command_path: Path, *, cwd: Path, env: dict[str, str]) -> None:
    if command_path.suffix == ".sh":
        cmd = ["bash", str(command_path)]
    elif command_path.suffix == ".py":
        cmd = ["python3", str(command_path)]
    else:
        cmd = [str(command_path)]
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True, text=True)


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

    entry, profile, owner_repo_root, profile_path, repo_paths, repo_states = resolve_profile(
        workspace_root=workspace_root,
        profile_id=args.profile,
        repo_overrides=repo_overrides,
    )
    paths = session_paths(workspace_root, args.profile, operator)
    namespace = compute_namespace(profile, args.profile, operator)

    current_manifest_path = paths["current_manifest"]
    existing_manifest = load_yaml(current_manifest_path) if current_manifest_path.exists() else {}
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
    archive_path = write_session_files(
        manifest=manifest,
        current_manifest=current_manifest_path,
        sessions_root=paths["sessions_root"],
    )

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
        DEVINT_SESSION_ARCHIVE=str(archive_path),
        DEVINT_SESSION_FILE=str(current_manifest_path),
        DEVINT_SESSION_ID=session_id,
        DEVINT_STATE_ROOT=str(paths["state_root"]),
        DEVINT_WORKSPACE_ROOT=str(workspace_root),
    )

    command_key = ACTIONS[args.action]
    command_path = workspace_root / entry["owner_repo"] / profile["commands"][command_key]
    dispatch_command(command_path, cwd=owner_repo_root, env=env)

    print(
        "dev-integration action complete: "
        f"profile={args.profile} action={args.action} namespace={namespace} session={session_id}"
    )
    print(f"session manifest: {current_manifest_path}")
    if ACTIONS[args.action] == "promote_check":
        print(f"promotion report: {promotion_report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
