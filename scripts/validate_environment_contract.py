#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys

import yaml


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def is_placeholder(value: str) -> bool:
    return value == "" or "replace-me" in value


def build_gateway_image_ref(repository: str, tag: str, digest: str) -> str:
    if digest and not is_placeholder(digest):
        return f"{repository}@{digest}"
    return f"{repository}:{tag}"


def expect_equal(errors, label, actual, expected):
    if actual != expected:
        errors.append(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("environment", help="Environment name, for example stage or prod")
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root",
    )
    args = parser.parse_args()

    env_root = args.repo_root / "environments" / args.environment
    versions = load_yaml(env_root / "versions.yaml")
    gateway_values = load_yaml(env_root / "values" / "openclaw-gateway.yaml")
    platform_values = load_yaml(env_root / "values" / "platform-version.yaml")

    gateway_image = versions["gateway"]["image"]
    source_repos = versions["sourceRepos"]
    gateway_env = gateway_values["env"]
    platform_versions = platform_values["versions"]

    expected_gateway_image = build_gateway_image_ref(
        gateway_image["repository"],
        gateway_image["tag"],
        gateway_image["digest"],
    )

    errors = []
    expect_equal(
        errors,
        "gateway image repository",
        gateway_values["image"]["repository"],
        gateway_image["repository"],
    )
    expect_equal(
        errors,
        "gateway image tag",
        gateway_values["image"]["tag"],
        gateway_image["tag"],
    )
    expect_equal(
        errors,
        "gateway image digest",
        gateway_values["image"]["digest"],
        gateway_image["digest"],
    )
    expect_equal(
        errors,
        "platform version gateway image",
        platform_versions["gatewayImage"],
        expected_gateway_image,
    )
    expect_equal(
        errors,
        "telegram SHA in gateway values",
        gateway_env["OPENCLAW_TELEGRAM_SHA"],
        source_repos["telegramEnhanced"]["commit"],
    )
    expect_equal(
        errors,
        "host bridge SHA in gateway values",
        gateway_env["OPENCLAW_HOST_BRIDGE_SHA"],
        source_repos["hostBridge"]["commit"],
    )
    expect_equal(
        errors,
        "platform SHA in gateway values",
        gateway_env["OPENCLAW_PLATFORM_SHA"],
        source_repos["platformEngineering"]["commit"],
    )
    expect_equal(
        errors,
        "telegram SHA in platform version values",
        platform_versions["telegramSha"],
        source_repos["telegramEnhanced"]["commit"],
    )
    expect_equal(
        errors,
        "host bridge SHA in platform version values",
        platform_versions["hostBridgeSha"],
        source_repos["hostBridge"]["commit"],
    )
    expect_equal(
        errors,
        "isolated deployment SHA in platform version values",
        platform_versions["isolatedDeploymentSha"],
        source_repos["isolatedDeployment"]["commit"],
    )
    expect_equal(
        errors,
        "platform SHA in platform version values",
        platform_versions["platformSha"],
        source_repos["platformEngineering"]["commit"],
    )

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(
        f"{args.environment} contract valid: "
        f"{expected_gateway_image} "
        f"(telegram={source_repos['telegramEnhanced']['commit']}, "
        f"hostBridge={source_repos['hostBridge']['commit']}, "
        f"isolatedDeployment={source_repos['isolatedDeployment']['commit']}, "
        f"platform={source_repos['platformEngineering']['commit']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
