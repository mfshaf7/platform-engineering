#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gateway_contract import build_metadata, compute_publish_tag, load_versions, write_github_output
from gateway_environment import validate_environment_contract
from gateway_release_ops import pin_gateway_source_repos, promote_environment, record_gateway_image
from prod_verification import (
    print_status as print_prod_verification_status,
    record_prod_verification,
    reset_prod_verification,
    validate_prod_verification,
)
from stage_readiness import (
    approve_stage_promotion_readiness,
    print_status as print_stage_status,
    record_stage_verification,
    reset_stage_promotion_readiness,
    reset_stage_verification,
    validate_stage_promotion_readiness,
    validate_stage_verification,
)


def add_repo_root_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[3],
        type=Path,
        help="platform-engineering repository root",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Unified operator entrypoint for governed gateway release work: "
            "pin source repos, inspect build metadata, record image digests, "
            "record stage and prod verification evidence, manage stage readiness, "
            "and promote environments."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    metadata_parser = subparsers.add_parser(
        "metadata",
        help="Print computed build metadata for an environment.",
    )
    metadata_parser.add_argument("environment", help="Environment name, for example stage or prod")
    add_repo_root_arg(metadata_parser)
    metadata_parser.add_argument("--json", action="store_true", help="Print the full metadata object as JSON.")
    metadata_parser.add_argument("--github-output", type=Path, help="Write metadata to a GitHub Actions output file.")

    tag_parser = subparsers.add_parser(
        "tag",
        help="Print only the deterministic publish tag for an environment.",
    )
    tag_parser.add_argument("environment", help="Environment name, for example stage or prod")
    add_repo_root_arg(tag_parser)

    pin_parser = subparsers.add_parser(
        "pin",
        help="Pin source SHAs from real local repos, sync derived values, and clear stale image digest state.",
    )
    pin_parser.add_argument("environment", help="Environment name, for example stage or prod")
    add_repo_root_arg(pin_parser)
    pin_parser.add_argument(
        "--workspace-root",
        default=Path(__file__).resolve().parents[4],
        type=Path,
        help="Workspace root containing the sibling repos",
    )
    pin_parser.add_argument("--telegram-repo", type=Path, help="Path to openclaw-telegram-enhanced")
    pin_parser.add_argument("--host-bridge-repo", type=Path, help="Path to openclaw-host-bridge")
    pin_parser.add_argument("--runtime-distribution-repo", type=Path, help="Path to openclaw-runtime-distribution")
    pin_parser.add_argument("--platform-repo", type=Path, help="Path to platform-engineering")
    pin_parser.add_argument("--telegram-ref", default="HEAD", help="Git ref to pin for Telegram")
    pin_parser.add_argument("--host-bridge-ref", default="HEAD", help="Git ref to pin for host bridge")
    pin_parser.add_argument(
        "--runtime-distribution-ref",
        default="HEAD",
        help="Git ref to pin for the runtime distribution repo",
    )
    pin_parser.add_argument("--platform-ref", default="HEAD", help="Git ref to pin for platform-engineering")
    pin_parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow pinning from a dirty repo by resolving only the selected commit ref",
    )
    pin_parser.add_argument(
        "--skip-origin-check",
        action="store_true",
        help="Skip origin/repository identity verification for local checkouts",
    )
    pin_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the resolved pins and expected publish tag without writing files",
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate that derived environment files match versions.yaml.",
    )
    validate_parser.add_argument("environment", help="Environment name, for example stage or prod")
    add_repo_root_arg(validate_parser)
    validate_parser.add_argument(
        "--require-deterministic-tag",
        action="store_true",
        help="Also require gateway.image.tag to match the deterministic source-bundle tag.",
    )

    record_parser = subparsers.add_parser(
        "record",
        help="Record a built image digest into an environment contract after optional pre-pull.",
    )
    record_parser.add_argument("environment", help="Environment name, for example stage or prod")
    add_repo_root_arg(record_parser)
    record_parser.add_argument(
        "--tag",
        help="Published gateway image tag. Defaults to the deterministic tag from the current source pins.",
    )
    record_parser.add_argument("--digest", required=True, help="Published gateway image digest, for example sha256:...")
    record_parser.add_argument(
        "--platform-sha",
        help=(
            "Platform-engineering commit used by the build workflow. "
            "Defaults to the existing environment pin when omitted."
        ),
    )
    record_parser.add_argument(
        "--skip-prepull",
        action="store_true",
        help="Skip the mandatory external pre-pull step before recording the digest.",
    )
    record_parser.add_argument(
        "--kubectl",
        default="k3s kubectl",
        help="kubectl command prefix used to access the cluster for external pre-pull.",
    )
    record_parser.add_argument(
        "--timeout",
        default="90m",
        help="How long to wait for the external pre-pull daemonset rollout.",
    )
    record_parser.add_argument(
        "--required-check",
        action="append",
        default=[],
        dest="required_checks",
        help="repeatable required verification check id for stage candidates; defaults to the catalog baseline",
    )
    record_parser.add_argument(
        "--capability",
        action="append",
        default=[],
        dest="capabilities",
        help="repeatable capability tag for stage candidates; defaults to the tags implied by the required checks",
    )
    record_parser.add_argument(
        "--note",
        default="",
        help="human note stored with the recorded stage candidate when recording stage",
    )

    promote_parser = subparsers.add_parser(
        "promote",
        help="Copy a validated source environment candidate into the target environment contract.",
    )
    promote_parser.add_argument("source_environment")
    promote_parser.add_argument("target_environment")
    add_repo_root_arg(promote_parser)

    verification_parser = subparsers.add_parser(
        "verification",
        help="Manage or validate structured stage verification evidence.",
    )
    verification_parser.add_argument("action", choices=("status", "reset", "record", "validate"))
    add_repo_root_arg(verification_parser)
    verification_parser.add_argument("--status", choices=("pending",), help="reset target state")
    verification_parser.add_argument("--note", default="", help="human note for verification changes")
    verification_parser.add_argument(
        "--verified-by",
        default="",
        help="operator or reviewer who performed the verification",
    )
    verification_parser.add_argument(
        "--evidence-ref",
        default="",
        help="link, runbook ref, or log reference for the verification evidence",
    )
    verification_parser.add_argument(
        "--check-result",
        action="append",
        default=[],
        dest="check_results",
        help="repeatable check result in the form check-id=status",
    )
    verification_parser.add_argument(
        "--check-results",
        dest="check_results_blob",
        default="",
        help="comma or newline separated check-id=status entries",
    )

    readiness_parser = subparsers.add_parser(
        "readiness",
        help="Manage or validate stage promotion readiness.",
    )
    readiness_parser.add_argument("action", choices=("status", "reset", "approve", "validate"))
    add_repo_root_arg(readiness_parser)
    readiness_parser.add_argument("--status", choices=("inactive", "pending"), help="reset target state")
    readiness_parser.add_argument("--note", default="", help="human note for readiness changes")
    readiness_parser.add_argument("--approved-by", default="", help="GitHub actor or operator name")

    prod_verification_parser = subparsers.add_parser(
        "prod-verification",
        help="Manage or validate structured post-promotion prod smoke/UAT evidence.",
    )
    prod_verification_parser.add_argument("action", choices=("status", "reset", "record", "validate"))
    add_repo_root_arg(prod_verification_parser)
    prod_verification_parser.add_argument("--status", choices=("pending",), help="reset target state")
    prod_verification_parser.add_argument("--note", default="", help="human note for verification changes")
    prod_verification_parser.add_argument(
        "--verified-by",
        default="",
        help="operator or reviewer who performed the prod smoke verification",
    )
    prod_verification_parser.add_argument(
        "--evidence-ref",
        default="",
        help="link, runbook ref, or log reference for the prod smoke evidence",
    )
    prod_verification_parser.add_argument(
        "--check-result",
        action="append",
        default=[],
        dest="check_results",
        help="repeatable check result in the form check-id=status",
    )
    prod_verification_parser.add_argument(
        "--check-results",
        dest="check_results_blob",
        default="",
        help="comma or newline separated check-id=status entries",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.command == "metadata":
        versions = load_versions(args.repo_root, args.environment)
        metadata = build_metadata(versions)
        if args.github_output:
            write_github_output(args.github_output, metadata)
        if args.json:
            print(json.dumps(metadata, indent=2, sort_keys=True))
        else:
            for key, value in metadata.items():
                print(f"{key}={value}")
        return 0

    if args.command == "tag":
        versions = load_versions(args.repo_root, args.environment)
        print(compute_publish_tag(versions))
        return 0

    if args.command == "pin":
        return pin_gateway_source_repos(
            args.environment,
            repo_root=args.repo_root,
            workspace_root=args.workspace_root,
            telegram_repo=args.telegram_repo,
            host_bridge_repo=args.host_bridge_repo,
            runtime_distribution_repo=args.runtime_distribution_repo,
            platform_repo=args.platform_repo,
            telegram_ref=args.telegram_ref,
            host_bridge_ref=args.host_bridge_ref,
            runtime_distribution_ref=args.runtime_distribution_ref,
            platform_ref=args.platform_ref,
            allow_dirty=args.allow_dirty,
            skip_origin_check=args.skip_origin_check,
            dry_run=args.dry_run,
        )

    if args.command == "validate":
        versions, errors = validate_environment_contract(
            args.environment,
            args.repo_root,
            require_deterministic_tag=args.require_deterministic_tag,
        )
        if errors:
            raise SystemExit("\n".join(errors))
        image = versions["gateway"]["image"]
        source = versions["sourceRepos"]
        image_ref = image["repository"] + (f"@{image['digest']}" if image["digest"] else f":{image['tag']}")
        print(
            f"{args.environment} contract valid: {image_ref} "
            f"(telegram={source['telegramEnhanced']['commit']}, "
            f"hostBridge={source['hostBridge']['commit']}, "
            f"runtimeDistribution={source['runtimeDistribution']['commit']}, "
            f"platform={source['platformEngineering']['commit']})"
        )
        return 0

    if args.command == "record":
        return record_gateway_image(
            args.environment,
            digest=args.digest,
            repo_root=args.repo_root,
            tag=args.tag,
            platform_sha=args.platform_sha,
            skip_prepull=args.skip_prepull,
            kubectl=args.kubectl,
            timeout=args.timeout,
            required_checks=args.required_checks,
            capabilities=args.capabilities,
            note=args.note,
        )

    if args.command == "promote":
        return promote_environment(args.source_environment, args.target_environment, repo_root=args.repo_root)

    if args.command == "verification":
        if args.action == "status":
            print_stage_status(args.repo_root)
            return 0
        if args.action == "reset":
            if not args.status:
                raise SystemExit("--status is required for verification reset")
            data = reset_stage_verification(args.repo_root, status=args.status, note=args.note)
            print(f"stage verification reset to {data['status']}")
            return 0
        if args.action == "record":
            if not args.verified_by:
                raise SystemExit("--verified-by is required for verification record")
            if not args.evidence_ref:
                raise SystemExit("--evidence-ref is required for verification record")
            raw_results = list(args.check_results)
            if args.check_results_blob:
                raw_results.append(args.check_results_blob)
            data = record_stage_verification(
                args.repo_root,
                verified_by=args.verified_by,
                evidence_ref=args.evidence_ref,
                note=args.note,
                raw_results=raw_results,
            )
            print(
                "stage verification recorded for "
                f"{data['candidateRef']['sourceBundleRef']} with {len(data['checks'])} checks"
            )
            return 0
        data = validate_stage_verification(args.repo_root)
        print(
            "stage verification valid for "
            f"{data['candidateRef']['sourceBundleRef']} with {len(data['checks'])} checks"
        )
        return 0

    if args.command == "prod-verification":
        if args.action == "status":
            print_prod_verification_status(args.repo_root)
            return 0
        if args.action == "reset":
            if not args.status:
                raise SystemExit("--status is required for prod-verification reset")
            data = reset_prod_verification(args.repo_root, status=args.status, note=args.note)
            print(f"prod verification reset to {data['status']}")
            return 0
        if args.action == "record":
            if not args.verified_by:
                raise SystemExit("--verified-by is required for prod-verification record")
            if not args.evidence_ref:
                raise SystemExit("--evidence-ref is required for prod-verification record")
            raw_results = list(args.check_results)
            if args.check_results_blob:
                raw_results.append(args.check_results_blob)
            data = record_prod_verification(
                args.repo_root,
                verified_by=args.verified_by,
                evidence_ref=args.evidence_ref,
                note=args.note,
                raw_results=raw_results,
            )
            print(
                "prod verification recorded for "
                f"{data['candidateRef']['sourceBundleRef']} with {len(data['checks'])} checks"
            )
            return 0
        data = validate_prod_verification(args.repo_root)
        print(
            "prod verification valid for "
            f"{data['candidateRef']['sourceBundleRef']} with {len(data['checks'])} checks"
        )
        return 0

    if args.action == "status":
        print_stage_status(args.repo_root)
        return 0
    if args.action == "reset":
        if not args.status:
            raise SystemExit("--status is required for readiness reset")
        data = reset_stage_promotion_readiness(args.repo_root, args.status, args.note)
        print(f"stage readiness reset to {data['status']}")
        return 0
    if args.action == "approve":
        if not args.approved_by:
            raise SystemExit("--approved-by is required for readiness approve")
        data = approve_stage_promotion_readiness(args.repo_root, args.approved_by, args.note)
        print(
            "stage readiness approved for "
            f"{data['approvedCandidate']['image']['repository']}@{data['approvedCandidate']['image']['digest']}"
        )
        return 0

    data = validate_stage_promotion_readiness(args.repo_root)
    print(
        "stage readiness valid for "
        f"{data['approvedCandidate']['image']['repository']}@{data['approvedCandidate']['image']['digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
