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
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root",
    )
    args = parser.parse_args()

    env_root = args.repo_root / "environments" / args.environment
    versions_path = env_root / "versions.yaml"
    gateway_values_path = env_root / "values" / "openclaw-gateway.yaml"
    platform_values_path = env_root / "values" / "platform-version.yaml"

    versions = load_yaml(versions_path)
    gateway_values = load_yaml(gateway_values_path)
    platform_values = load_yaml(platform_values_path)

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

    image_ref = f"{repository}@{args.digest}"

    versions["gateway"]["image"]["tag"] = args.tag
    versions["gateway"]["image"]["digest"] = args.digest

    gateway_values["image"]["repository"] = repository
    gateway_values["image"]["tag"] = args.tag
    gateway_values["image"]["digest"] = args.digest
    gateway_values["env"]["OPENCLAW_TELEGRAM_SHA"] = versions["sourceRepos"]["telegramEnhanced"]["commit"]
    gateway_values["env"]["OPENCLAW_HOST_BRIDGE_SHA"] = versions["sourceRepos"]["hostBridge"]["commit"]
    gateway_values["env"]["OPENCLAW_PLATFORM_SHA"] = versions["sourceRepos"]["platformEngineering"]["commit"]

    platform_values["versions"]["gatewayImage"] = image_ref
    platform_values["versions"]["isolatedDeploymentSha"] = versions["sourceRepos"]["isolatedDeployment"]["commit"]
    platform_values["versions"]["telegramSha"] = versions["sourceRepos"]["telegramEnhanced"]["commit"]
    platform_values["versions"]["hostBridgeSha"] = versions["sourceRepos"]["hostBridge"]["commit"]
    platform_values["versions"]["platformSha"] = versions["sourceRepos"]["platformEngineering"]["commit"]

    write_yaml(versions_path, versions)
    write_yaml(gateway_values_path, gateway_values)
    write_yaml(platform_values_path, platform_values)

    print(f"Recorded {image_ref} for {args.environment}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
