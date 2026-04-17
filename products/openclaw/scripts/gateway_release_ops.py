#!/usr/bin/env python3
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from gateway_contract import build_gateway_image_ref, compute_publish_tag
from gateway_environment import (
    telegram_overlay_state,
    is_placeholder,
    load_yaml,
    sync_environment,
    validate_environment_contract,
    write_yaml,
)
from prepull_gateway_image import prepull_image
from prod_verification import reset_prod_verification
from stage_readiness import (
    current_stage_components,
    record_stage_release_candidate,
    reset_stage_promotion_readiness,
    reset_stage_release_candidate,
    reset_stage_verification,
    validate_stage_promotion_readiness,
)


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
GITHUB_REPO_RE = re.compile(
    r"(?:git@|https://|ssh://git@)?github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$"
)


@dataclass(frozen=True)
class RepoPin:
    key: str
    label: str
    default_path_name: str
    ref_arg: str


REPO_PINS = (
    RepoPin("telegramEnhanced", "telegram repo", "openclaw-telegram-enhanced", "telegram_ref"),
    RepoPin("hostBridge", "host bridge repo", "openclaw-host-bridge", "host_bridge_ref"),
    RepoPin(
        "runtimeDistribution",
        "runtime distribution repo",
        "openclaw-runtime-distribution",
        "runtime_distribution_ref",
    ),
    RepoPin("platformEngineering", "platform repo", "platform-engineering", "platform_ref"),
)


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def normalize_repository_url(value: str | None) -> str | None:
    if not value:
        return None
    match = GITHUB_REPO_RE.search(value.strip())
    if match:
        return f"github.com/{match.group('owner')}/{match.group('repo')}"
    return value.strip().removesuffix(".git")


def ensure_repo_identity(repo: Path, expected_repository: str, label: str, skip_origin_check: bool) -> None:
    if skip_origin_check:
        return
    origin = run_git(repo, "remote", "get-url", "origin")
    normalized_origin = normalize_repository_url(origin)
    normalized_expected = normalize_repository_url(expected_repository)
    if normalized_origin != normalized_expected:
        raise SystemExit(
            f"{label} origin mismatch: expected {normalized_expected!r}, got {normalized_origin!r} from {repo}"
        )


def ensure_clean_repo(repo: Path, label: str, allow_dirty: bool) -> None:
    status = run_git(repo, "status", "--short")
    if status and not allow_dirty:
        raise SystemExit(
            f"{label} is dirty at {repo}. Commit or stash changes before pinning, or pass --allow-dirty if you intentionally want HEAD only."
        )


def resolve_commit(repo: Path, ref: str, label: str) -> str:
    commit = run_git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise SystemExit(f"{label} ref {ref!r} did not resolve to a full commit SHA: {commit!r}")
    return commit


def pin_gateway_source_repos(
    environment: str,
    *,
    repo_root: Path,
    workspace_root: Path,
    telegram_repo: Path | None = None,
    host_bridge_repo: Path | None = None,
    runtime_distribution_repo: Path | None = None,
    platform_repo: Path | None = None,
    telegram_ref: str = "HEAD",
    host_bridge_ref: str = "HEAD",
    runtime_distribution_ref: str = "HEAD",
    platform_ref: str = "HEAD",
    allow_dirty: bool = False,
    skip_origin_check: bool = False,
    dry_run: bool = False,
) -> int:
    repo_root = repo_root.resolve()
    workspace_root = workspace_root.resolve()

    path_overrides = {
        "telegramEnhanced": telegram_repo,
        "hostBridge": host_bridge_repo,
        "runtimeDistribution": runtime_distribution_repo,
        "platformEngineering": platform_repo or repo_root,
    }
    ref_overrides = {
        "telegramEnhanced": telegram_ref,
        "hostBridge": host_bridge_ref,
        "runtimeDistribution": runtime_distribution_ref,
        "platformEngineering": platform_ref,
    }

    versions_path = repo_root / "environments" / environment / "versions.yaml"
    versions = load_yaml(versions_path)
    source_repos = versions["sourceRepos"]

    resolved = []
    for pin in REPO_PINS:
        repo_path = (path_overrides[pin.key] or (workspace_root / pin.default_path_name)).resolve()
        if not repo_path.exists():
            raise SystemExit(f"Missing {pin.label} checkout at {repo_path}")
        ensure_repo_identity(
            repo_path,
            source_repos[pin.key]["repository"],
            pin.label,
            skip_origin_check=skip_origin_check,
        )
        ensure_clean_repo(repo_path, pin.label, allow_dirty=allow_dirty)
        commit = resolve_commit(repo_path, ref_overrides[pin.key], pin.label)
        resolved.append((pin, repo_path, commit))
        source_repos[pin.key]["commit"] = commit

    publish_tag = compute_publish_tag(versions)
    versions["gateway"]["image"]["tag"] = publish_tag
    versions["gateway"]["image"]["digest"] = ""

    print(f"Resolved source pins for {environment}:")
    for pin, repo_path, commit in resolved:
        print(f"- {pin.label}: {commit} ({repo_path})")
    print(f"- expected publish tag: {publish_tag}")
    print("- image digest cleared until the governed build output is recorded")

    if dry_run:
        print("Dry run only: no files written.")
        return 0

    write_yaml(versions_path, versions)
    changed, changed_paths = sync_environment(environment, repo_root)

    if changed:
        print("Synchronized derived environment files:")
        for path in changed_paths:
            print(f"- {path.relative_to(repo_root)}")

    _, errors = validate_environment_contract(
        environment,
        repo_root,
        require_deterministic_tag=True,
    )
    if errors:
        raise SystemExit("\n".join(errors))

    if environment == "stage":
        readiness_status = "pending" if current_stage_components(repo_root) else "inactive"
        reset_stage_release_candidate(
            repo_root,
            status="pending-build",
            note="Stage source pins changed; build and record a new stage candidate before verification or approval.",
        )
        reset_stage_verification(
            repo_root,
            status="pending",
            note="Stage source pins changed; re-run stage rehearsal checks after recording the new candidate.",
        )
        reset_stage_promotion_readiness(
            repo_root,
            status=readiness_status,
            note="Stage source pins changed; build, verify, and re-approve the next stage candidate before promoting to prod.",
        )
    elif environment == "prod":
        reset_prod_verification(
            repo_root,
            status="pending",
            note="Prod source pins changed; record the next prod candidate and post-promotion prod smoke before treating prod as complete.",
        )

    print(f"Pinned {environment} source repos in {versions_path.relative_to(repo_root)}")
    return 0


def record_gateway_image(
    environment: str,
    *,
    digest: str,
    repo_root: Path,
    tag: str | None = None,
    platform_sha: str | None = None,
    skip_prepull: bool = False,
    kubectl: str = "k3s kubectl",
    timeout: str = "90m",
    required_checks: list[str] | None = None,
    capabilities: list[str] | None = None,
    note: str = "",
) -> int:
    env_root = repo_root / "environments" / environment
    versions_path = env_root / "versions.yaml"
    versions = load_yaml(versions_path)

    repository = versions["gateway"]["image"]["repository"]
    expected_prefix = f"{versions['gateway']['publish']['tagPrefix']}-"
    expected_tag = compute_publish_tag(versions)
    tag = tag or expected_tag

    if not tag.startswith(expected_prefix):
        raise SystemExit(
            f"gateway tag must start with {expected_prefix!r} for {environment}, got {tag!r}"
        )
    if tag != expected_tag:
        raise SystemExit(
            f"gateway tag must match the current source-bundle tag for {environment}: expected {expected_tag!r}, got {tag!r}"
        )
    if not SHA256_RE.fullmatch(digest):
        raise SystemExit(
            f"gateway digest must look like sha256:<64 hex chars>, got {digest!r}"
        )
    if platform_sha and not re.fullmatch(r"^[0-9a-f]{40}$", platform_sha):
        raise SystemExit(
            f"platform sha must look like a 40-character git commit, got {platform_sha!r}"
        )

    image_ref = f"{repository}@{digest}"
    platform_sha = platform_sha or versions["sourceRepos"]["platformEngineering"]["commit"]

    if environment in {"prod", "stage"} and not skip_prepull:
        prepull_image(
            environment,
            image_ref=image_ref,
            kubectl=kubectl,
            timeout=timeout,
        )

    versions["gateway"]["image"]["tag"] = tag
    versions["gateway"]["image"]["digest"] = digest
    versions["sourceRepos"]["platformEngineering"]["commit"] = platform_sha

    write_yaml(versions_path, versions)

    sync_environment(environment, repo_root)
    _, errors = validate_environment_contract(
        environment,
        repo_root,
        require_deterministic_tag=True,
    )
    if errors:
        raise SystemExit("\n".join(errors))

    if environment == "stage":
        candidate_note = note or "Governed stage candidate recorded from the current stage source bundle."
        candidate = record_stage_release_candidate(
            repo_root,
            note=candidate_note,
            required_checks=required_checks,
            capabilities=capabilities,
        )
        reset_stage_verification(
            repo_root,
            status="pending",
            note="New stage candidate recorded; rehearse the current candidate before approval.",
        )
        reset_stage_promotion_readiness(
            repo_root,
            status="pending",
            note="New stage candidate recorded; verification and approval are required before promoting to prod.",
        )
        print(
            f"Recorded stage candidate {candidate['candidate']['sourceBundleRef']} with required checks "
            + ", ".join(candidate["candidate"]["requiredChecks"])
        )
    elif environment == "prod":
        reset_prod_verification(
            repo_root,
            status="pending",
            note="Prod contract changed; record post-promotion prod smoke/UAT before treating the rollout as complete.",
        )
        print("Reset prod verification to pending for the current prod contract")

    print(f"Recorded {image_ref} for {environment} with platformSha={platform_sha}")
    return 0


def require_real_value(name: str, value: str):
    if is_placeholder(value):
        raise SystemExit(f"{name} must be pinned before promotion, got {value!r}")


def promote_environment(source_environment: str, target_environment: str, *, repo_root: Path) -> int:
    source_root = repo_root / "environments" / source_environment
    target_root = repo_root / "environments" / target_environment

    source_versions = load_yaml(source_root / "versions.yaml")
    target_versions = load_yaml(target_root / "versions.yaml")
    source_overlay = telegram_overlay_state(source_versions)
    source_gateway_image = source_versions["gateway"]["image"]
    source_repos = source_versions["sourceRepos"]
    source_contract_errors = validate_environment_contract(
        source_environment,
        repo_root,
        require_deterministic_tag=True,
    )[1]

    if source_contract_errors:
        raise SystemExit(
            f"{source_environment} environment contract is invalid; fix it before promotion:\n- "
            + "\n- ".join(source_contract_errors)
        )

    if source_environment == "stage" and target_environment == "prod":
        validate_stage_promotion_readiness(repo_root)

    require_real_value("source gateway image repository", source_gateway_image["repository"])
    require_real_value("source gateway image tag", source_gateway_image["tag"])
    require_real_value("source gateway image digest", source_gateway_image["digest"])
    require_real_value("source telegram SHA", source_repos["telegramEnhanced"]["commit"])
    require_real_value("source host bridge SHA", source_repos["hostBridge"]["commit"])
    require_real_value("source runtime distribution SHA", source_repos["runtimeDistribution"]["commit"])
    require_real_value("source platform SHA", source_repos["platformEngineering"]["commit"])
    if source_overlay["status"] == "pending-build":
        raise SystemExit(
            "stage Telegram overlay lane is pinned but not recorded; build and record the overlay artifact before promoting stage to prod"
        )
    if source_overlay["status"] == "candidate":
        require_real_value(
            "source telegram overlay qualified base image",
            source_overlay["qualifiedBaseImage"],
        )
        require_real_value(
            "source telegram overlay source commit",
            source_overlay["source"]["commit"],
        )
        require_real_value(
            "source telegram overlay image repository",
            source_overlay["image"]["repository"],
        )
        require_real_value(
            "source telegram overlay image tag",
            source_overlay["image"]["tag"],
        )
        require_real_value(
            "source telegram overlay image digest",
            source_overlay["image"]["digest"],
        )
        if source_overlay["qualifiedBaseImage"] != source_versions["gateway"]["build"]["baseImage"]:
            raise SystemExit(
                "stage telegram overlay lane is qualified for a different OpenClaw base image than the current stage contract"
            )
        if target_versions["gateway"]["build"]["baseImage"] != source_overlay["qualifiedBaseImage"]:
            raise SystemExit(
                "prod base image does not match the stage-qualified Telegram overlay base image; qualify the same base line before promoting the overlay lane"
            )

    target_versions["gateway"]["build"] = dict(source_versions["gateway"]["build"])
    target_versions["gateway"]["image"] = dict(source_gateway_image)
    target_versions["sourceRepos"]["telegramEnhanced"]["commit"] = source_repos["telegramEnhanced"]["commit"]
    target_versions["sourceRepos"]["hostBridge"]["commit"] = source_repos["hostBridge"]["commit"]
    target_versions["sourceRepos"]["runtimeDistribution"]["commit"] = source_repos["runtimeDistribution"]["commit"]
    target_versions["sourceRepos"]["platformEngineering"]["commit"] = source_repos["platformEngineering"]["commit"]
    target_versions.setdefault("experiments", {})["telegramOverlay"] = {
        "status": source_overlay["status"],
        "qualifiedBaseImage": source_overlay["qualifiedBaseImage"],
        "publish": dict(source_overlay["publish"]),
        "source": dict(source_overlay["source"]),
        "image": dict(source_overlay["image"]),
    }

    write_yaml(target_root / "versions.yaml", target_versions)

    sync_environment(target_environment, repo_root)
    target_contract_errors = validate_environment_contract(
        target_environment,
        repo_root,
        require_deterministic_tag=True,
    )[1]
    if target_contract_errors:
        raise SystemExit(
            f"{target_environment} environment contract is invalid after promotion:\n- "
            + "\n- ".join(target_contract_errors)
        )
    if target_environment == "prod":
        reset_prod_verification(
            repo_root,
            status="pending",
            note="Prod contract changed via promotion; record post-promotion prod smoke/UAT before treating this rollout as complete.",
        )

    print(
        f"Promoted {source_environment} gateway image "
        f"{build_gateway_image_ref(source_gateway_image['repository'], source_gateway_image['tag'], source_gateway_image['digest'], treat_placeholder_as_missing=True)} "
        f"into {target_environment}"
    )
    return 0
