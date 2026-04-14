#!/usr/bin/env python3
import argparse
from pathlib import Path
import re

import yaml


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def write_yaml(path: Path, data):
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record a newly built gateway image tag and digest into an environment contract."
    )
    parser.add_argument("environment", help="Environment name, for example prod or stage")
    parser.add_argument("--tag", required=True, help="Published gateway image tag")
    parser.add_argument("--digest", required=True, help="Published gateway image digest, for example sha256:...")
    parser.add_argument(
        "--platform-sha",
        help=(
            "Platform-engineering commit used by the build workflow. "
            "Defaults to the existing environment pin when omitted."
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root",
    )
    args = parser.parse_args()

    env_root = args.repo_root / "environments" / args.environment
    versions_path = env_root / "versions.yaml"
    versions = load_yaml(versions_path)

    repository = versions["gateway"]["image"]["repository"]
    expected_prefix = f"{versions['gateway']['publish']['tagPrefix']}-"

    if not args.tag.startswith(expected_prefix):
        raise SystemExit(
            f"gateway tag must start with {expected_prefix!r} for {args.environment}, got {args.tag!r}"
        )
    if not SHA256_RE.fullmatch(args.digest):
        raise SystemExit(
            f"gateway digest must look like sha256:<64 hex chars>, got {args.digest!r}"
        )
    if args.platform_sha and not re.fullmatch(r"^[0-9a-f]{40}$", args.platform_sha):
        raise SystemExit(
            f"platform sha must look like a 40-character git commit, got {args.platform_sha!r}"
        )

    image_ref = f"{repository}@{args.digest}"
    platform_sha = args.platform_sha or versions["sourceRepos"]["platformEngineering"]["commit"]

    versions["gateway"]["image"]["tag"] = args.tag
    versions["gateway"]["image"]["digest"] = args.digest
    versions["sourceRepos"]["platformEngineering"]["commit"] = platform_sha

    write_yaml(versions_path, versions)

    from sync_environment_contract import sync_environment

    sync_environment(args.environment, args.repo_root)

    print(f"Recorded {image_ref} for {args.environment} with platformSha={platform_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
