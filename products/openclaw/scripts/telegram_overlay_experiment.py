#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from gateway_contract import write_github_output
from gateway_environment import (
    TELEGRAM_OVERLAY_STATUSES,
    is_placeholder,
    load_yaml,
    sync_environment,
    telegram_overlay_state,
    validate_environment_contract,
    write_yaml,
)
from gateway_release_ops import (
    ensure_clean_repo,
    ensure_repo_identity,
    require_real_value,
    resolve_commit,
)
from stage_readiness import (
    current_stage_components,
    record_stage_release_candidate,
    reset_stage_promotion_readiness,
    reset_stage_release_candidate,
    reset_stage_verification,
)


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def add_repo_root_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[3],
        type=Path,
        help="platform-engineering repository root",
    )


def versions_path(repo_root: Path, environment: str) -> Path:
    return repo_root / "environments" / environment / "versions.yaml"


def load_versions(repo_root: Path, environment: str) -> dict:
    return load_yaml(versions_path(repo_root, environment))


def ensure_stage_environment(environment: str) -> None:
    if environment != "stage":
        raise SystemExit("telegram overlay experiment is currently supported only for stage")


def compute_overlay_tag(overlay: dict) -> str:
    source_commit = (overlay.get("source") or {}).get("commit") or ""
    tag_prefix = (overlay.get("publish") or {}).get("tagPrefix") or "telegram-overlay"
    if is_placeholder(source_commit):
        raise SystemExit("telegram overlay source commit must be pinned before a tag can be computed")
    return f"{tag_prefix}-{source_commit[:12]}"


def overlay_metadata(versions: dict) -> dict[str, str]:
    overlay = telegram_overlay_state(versions)
    return {
        "overlay_status": overlay["status"],
        "telegram_ref": (overlay.get("source") or {}).get("commit") or "",
        "runtime_distribution_ref": versions["sourceRepos"]["runtimeDistribution"]["commit"],
        "platform_ref": versions["sourceRepos"]["platformEngineering"]["commit"],
        "publish_repository": (overlay.get("publish") or {}).get("repository") or "",
        "publish_tag_prefix": (overlay.get("publish") or {}).get("tagPrefix") or "",
        "publish_tag": compute_overlay_tag(overlay),
        "dockerfile": "deployment/Dockerfile.telegram-overlay",
    }


def print_status(repo_root: Path, environment: str) -> int:
    versions = load_versions(repo_root, environment)
    overlay = telegram_overlay_state(versions)
    print(json.dumps(overlay, indent=2, sort_keys=True))
    return 0


def pin_overlay_source(
    environment: str,
    *,
    repo_root: Path,
    workspace_root: Path,
    telegram_repo: Path | None = None,
    platform_repo: Path | None = None,
    runtime_distribution_repo: Path | None = None,
    telegram_ref: str = "HEAD",
    runtime_distribution_ref: str = "HEAD",
    platform_ref: str = "HEAD",
    allow_dirty: bool = False,
    skip_origin_check: bool = False,
) -> int:
    ensure_stage_environment(environment)

    repo_root = repo_root.resolve()
    workspace_root = workspace_root.resolve()
    versions = load_versions(repo_root, environment)
    overlay = telegram_overlay_state(versions)

    telegram_checkout = (telegram_repo or (workspace_root / "openclaw-telegram-enhanced")).resolve()
    platform_checkout = (platform_repo or repo_root).resolve()
    runtime_distribution_checkout = (
        runtime_distribution_repo or (workspace_root / "openclaw-runtime-distribution")
    ).resolve()

    if not telegram_checkout.exists():
        raise SystemExit(f"missing Telegram repo checkout at {telegram_checkout}")
    if not platform_checkout.exists():
        raise SystemExit(f"missing platform repo checkout at {platform_checkout}")
    if not runtime_distribution_checkout.exists():
        raise SystemExit(f"missing runtime-distribution repo checkout at {runtime_distribution_checkout}")

    ensure_repo_identity(
        telegram_checkout,
        overlay["source"]["repository"],
        "telegram repo",
        skip_origin_check=skip_origin_check,
    )
    ensure_repo_identity(
        platform_checkout,
        versions["sourceRepos"]["platformEngineering"]["repository"],
        "platform repo",
        skip_origin_check=skip_origin_check,
    )
    ensure_repo_identity(
        runtime_distribution_checkout,
        versions["sourceRepos"]["runtimeDistribution"]["repository"],
        "runtime-distribution repo",
        skip_origin_check=skip_origin_check,
    )
    ensure_clean_repo(telegram_checkout, "telegram repo", allow_dirty=allow_dirty)
    ensure_clean_repo(platform_checkout, "platform repo", allow_dirty=allow_dirty)
    ensure_clean_repo(
        runtime_distribution_checkout,
        "runtime-distribution repo",
        allow_dirty=allow_dirty,
    )

    telegram_commit = resolve_commit(telegram_checkout, telegram_ref, "telegram repo")
    runtime_distribution_commit = resolve_commit(
        runtime_distribution_checkout,
        runtime_distribution_ref,
        "runtime-distribution repo",
    )
    platform_commit = resolve_commit(platform_checkout, platform_ref, "platform repo")

    overlay["status"] = "pending-build"
    overlay["source"]["commit"] = telegram_commit
    overlay["image"]["repository"] = overlay["publish"]["repository"]
    overlay["image"]["tag"] = compute_overlay_tag(overlay)
    overlay["image"]["digest"] = ""
    versions.setdefault("experiments", {})["telegramOverlay"] = overlay
    versions["sourceRepos"]["runtimeDistribution"]["commit"] = runtime_distribution_commit
    versions["sourceRepos"]["platformEngineering"]["commit"] = platform_commit

    write_yaml(versions_path(repo_root, environment), versions)
    sync_environment(environment, repo_root)
    _, errors = validate_environment_contract(environment, repo_root)
    if errors:
        raise SystemExit("\n".join(errors))

    reset_stage_release_candidate(
        repo_root,
        status="pending-build",
        note="Stage Telegram overlay experiment pins changed; build and record a new overlay artifact before rehearsal.",
    )
    reset_stage_verification(
        repo_root,
        status="pending",
        note="Stage Telegram overlay experiment pins changed; re-run stage rehearsal after recording the overlay artifact.",
    )
    readiness_status = "pending" if current_stage_components(repo_root) else "inactive"
    reset_stage_promotion_readiness(
        repo_root,
        status=readiness_status,
        note="Stage Telegram overlay experiment pins changed; promotion remains blocked until the experiment is disabled and stage is re-approved.",
    )

    print(
        "Pinned stage Telegram overlay experiment to "
        f"{telegram_commit} with runtime-distribution {runtime_distribution_commit} "
        f"and expected tag {overlay['image']['tag']}"
    )
    return 0


def record_overlay_image(
    environment: str,
    *,
    repo_root: Path,
    digest: str,
    tag: str | None,
    platform_sha: str | None,
    note: str,
) -> int:
    ensure_stage_environment(environment)

    if not SHA256_RE.fullmatch(digest):
        raise SystemExit(f"overlay digest must look like sha256:<64 hex chars>, got {digest!r}")

    versions = load_versions(repo_root, environment)
    overlay = telegram_overlay_state(versions)
    if overlay["status"] not in {"pending-build", "candidate"}:
        raise SystemExit("stage Telegram overlay experiment must be pinned before recording an image digest")

    source_commit = overlay["source"].get("commit") or ""
    require_real_value("telegram overlay source commit", source_commit)

    expected_tag = compute_overlay_tag(overlay)
    effective_tag = tag or expected_tag
    if effective_tag != expected_tag:
        raise SystemExit(
            f"telegram overlay tag must match the current pinned source commit: expected {expected_tag!r}, got {effective_tag!r}"
        )

    if platform_sha:
        if not re.fullmatch(r"^[0-9a-f]{40}$", platform_sha):
            raise SystemExit(f"platform sha must look like a 40-character git commit, got {platform_sha!r}")
        versions["sourceRepos"]["platformEngineering"]["commit"] = platform_sha

    overlay["status"] = "candidate"
    overlay["image"]["repository"] = overlay["publish"]["repository"]
    overlay["image"]["tag"] = effective_tag
    overlay["image"]["digest"] = digest
    versions.setdefault("experiments", {})["telegramOverlay"] = overlay

    write_yaml(versions_path(repo_root, environment), versions)
    sync_environment(environment, repo_root)
    _, errors = validate_environment_contract(environment, repo_root)
    if errors:
        raise SystemExit("\n".join(errors))

    candidate_note = note or "Stage Telegram overlay experiment recorded from the pinned Telegram source commit."
    candidate = record_stage_release_candidate(repo_root, note=candidate_note)
    reset_stage_verification(
        repo_root,
        status="pending",
        note="Stage Telegram overlay experiment recorded; rehearse the current candidate before any further decision.",
    )
    reset_stage_promotion_readiness(
        repo_root,
        status="pending",
        note="Stage Telegram overlay experiment is active; promotion remains blocked until the experiment is disabled and the standard stage candidate is re-approved.",
    )

    print(
        f"Recorded stage Telegram overlay experiment for {candidate['candidate']['sourceBundleRef']} at {overlay['image']['repository']}@{digest}"
    )
    return 0


def disable_overlay_experiment(environment: str, *, repo_root: Path, note: str) -> int:
    ensure_stage_environment(environment)

    versions = load_versions(repo_root, environment)
    overlay = telegram_overlay_state(versions)
    overlay["status"] = "inactive"
    overlay["source"]["commit"] = ""
    overlay["image"]["tag"] = ""
    overlay["image"]["digest"] = ""
    versions.setdefault("experiments", {})["telegramOverlay"] = overlay

    write_yaml(versions_path(repo_root, environment), versions)
    sync_environment(environment, repo_root)
    _, errors = validate_environment_contract(environment, repo_root)
    if errors:
        raise SystemExit("\n".join(errors))

    reset_stage_release_candidate(
        repo_root,
        status="pending-build",
        note=note or "Stage Telegram overlay experiment disabled; rebuild or re-record the standard stage candidate before promotion.",
    )
    reset_stage_verification(
        repo_root,
        status="pending",
        note="Stage Telegram overlay experiment disabled; re-run the standard stage rehearsal before approval.",
    )
    readiness_status = "pending" if current_stage_components(repo_root) else "inactive"
    reset_stage_promotion_readiness(
        repo_root,
        status=readiness_status,
        note="Stage Telegram overlay experiment disabled; record and re-approve the standard stage candidate before promotion.",
    )
    print("Disabled the stage Telegram overlay experiment")
    return 0


def validate_overlay_experiment(environment: str, *, repo_root: Path) -> int:
    versions, errors = validate_environment_contract(environment, repo_root)
    if errors:
        raise SystemExit("\n".join(errors))
    overlay = telegram_overlay_state(versions)
    if overlay["status"] not in TELEGRAM_OVERLAY_STATUSES:
        raise SystemExit(f"invalid telegram overlay experiment status: {overlay['status']!r}")
    print(
        f"{environment} telegram overlay experiment valid: status={overlay['status']} source={overlay['source'].get('commit') or 'disabled'}"
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage the stage-only OpenClaw Telegram overlay experiment without rebuilding the full gateway image."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Print the current Telegram overlay experiment state.")
    status_parser.add_argument("environment", help="Environment name, currently stage only")
    add_repo_root_arg(status_parser)

    metadata_parser = subparsers.add_parser("metadata", help="Emit build metadata for the overlay image workflow.")
    metadata_parser.add_argument("environment", help="Environment name, currently stage only")
    add_repo_root_arg(metadata_parser)
    metadata_parser.add_argument("--json", action="store_true", help="Print metadata as JSON.")
    metadata_parser.add_argument("--github-output", type=Path, help="Write metadata to a GitHub Actions output file.")

    pin_parser = subparsers.add_parser("pin", help="Pin the stage Telegram overlay source commit from a local checkout.")
    pin_parser.add_argument("environment", help="Environment name, currently stage only")
    add_repo_root_arg(pin_parser)
    pin_parser.add_argument(
        "--workspace-root",
        default=Path(__file__).resolve().parents[4],
        type=Path,
        help="Workspace root containing the sibling repos",
    )
    pin_parser.add_argument("--telegram-repo", type=Path, help="Path to openclaw-telegram-enhanced")
    pin_parser.add_argument("--platform-repo", type=Path, help="Path to platform-engineering")
    pin_parser.add_argument(
        "--runtime-distribution-repo",
        type=Path,
        help="Path to openclaw-runtime-distribution",
    )
    pin_parser.add_argument("--telegram-ref", default="HEAD", help="Git ref to pin for Telegram")
    pin_parser.add_argument(
        "--runtime-distribution-ref",
        default="HEAD",
        help="Git ref to pin for openclaw-runtime-distribution",
    )
    pin_parser.add_argument("--platform-ref", default="HEAD", help="Git ref to pin for platform-engineering")
    pin_parser.add_argument("--allow-dirty", action="store_true", help="Allow pinning from a dirty checkout")
    pin_parser.add_argument(
        "--skip-origin-check",
        action="store_true",
        help="Skip origin/repository identity verification for local checkouts",
    )

    record_parser = subparsers.add_parser("record", help="Record a built Telegram overlay artifact digest into stage.")
    record_parser.add_argument("environment", help="Environment name, currently stage only")
    add_repo_root_arg(record_parser)
    record_parser.add_argument("--digest", required=True, help="Published Telegram overlay image digest")
    record_parser.add_argument("--tag", help="Published Telegram overlay image tag")
    record_parser.add_argument("--platform-sha", help="Platform-engineering commit that recorded the artifact")
    record_parser.add_argument("--note", default="", help="human note stored with the recorded stage candidate")

    disable_parser = subparsers.add_parser("disable", help="Disable the stage Telegram overlay experiment.")
    disable_parser.add_argument("environment", help="Environment name, currently stage only")
    add_repo_root_arg(disable_parser)
    disable_parser.add_argument("--note", default="", help="human note recorded when disabling the experiment")

    validate_parser = subparsers.add_parser("validate", help="Validate the environment contract including the overlay experiment.")
    validate_parser.add_argument("environment", help="Environment name")
    add_repo_root_arg(validate_parser)

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.command == "status":
        return print_status(args.repo_root, args.environment)
    if args.command == "metadata":
        ensure_stage_environment(args.environment)
        metadata = overlay_metadata(load_versions(args.repo_root, args.environment))
        if args.github_output:
            write_github_output(args.github_output, metadata)
        if args.json:
            print(json.dumps(metadata, indent=2, sort_keys=True))
        else:
            for key, value in metadata.items():
                print(f"{key}={value}")
        return 0
    if args.command == "pin":
        return pin_overlay_source(
            args.environment,
            repo_root=args.repo_root,
            workspace_root=args.workspace_root,
            telegram_repo=args.telegram_repo,
            platform_repo=args.platform_repo,
            runtime_distribution_repo=args.runtime_distribution_repo,
            telegram_ref=args.telegram_ref,
            runtime_distribution_ref=args.runtime_distribution_ref,
            platform_ref=args.platform_ref,
            allow_dirty=args.allow_dirty,
            skip_origin_check=args.skip_origin_check,
        )
    if args.command == "record":
        return record_overlay_image(
            args.environment,
            repo_root=args.repo_root,
            digest=args.digest,
            tag=args.tag,
            platform_sha=args.platform_sha,
            note=args.note,
        )
    if args.command == "disable":
        return disable_overlay_experiment(args.environment, repo_root=args.repo_root, note=args.note)
    return validate_overlay_experiment(args.environment, repo_root=args.repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
