#!/usr/bin/env python3
import argparse
from pathlib import Path

import yaml


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def write_yaml(path: Path, data):
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def is_placeholder(value: str) -> bool:
    return value == "" or "replace-me" in value


def require_real_value(name: str, value: str):
    if is_placeholder(value):
        raise SystemExit(f"{name} must be pinned before promotion, got {value!r}")


def build_gateway_image_ref(repository: str, tag: str, digest: str) -> str:
    if digest and not is_placeholder(digest):
        return f"{repository}@{digest}"
    return f"{repository}:{tag}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_environment")
    parser.add_argument("target_environment")
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root",
    )
    args = parser.parse_args()

    source_root = args.repo_root / "environments" / args.source_environment
    target_root = args.repo_root / "environments" / args.target_environment

    source_versions = load_yaml(source_root / "versions.yaml")
    target_versions = load_yaml(target_root / "versions.yaml")
    target_gateway_values = load_yaml(target_root / "values" / "openclaw-gateway.yaml")
    target_platform_values = load_yaml(target_root / "values" / "platform-version.yaml")

    source_gateway_image = source_versions["gateway"]["image"]
    source_repos = source_versions["sourceRepos"]

    require_real_value("source gateway image repository", source_gateway_image["repository"])
    require_real_value("source gateway image tag", source_gateway_image["tag"])
    require_real_value("source gateway image digest", source_gateway_image["digest"])
    require_real_value("source telegram SHA", source_repos["telegramEnhanced"]["commit"])
    require_real_value("source host bridge SHA", source_repos["hostBridge"]["commit"])
    require_real_value("source isolated deployment SHA", source_repos["isolatedDeployment"]["commit"])
    require_real_value("source platform SHA", source_repos["platformEngineering"]["commit"])

    target_versions["gateway"]["image"] = dict(source_gateway_image)
    target_versions["sourceRepos"]["telegramEnhanced"]["commit"] = source_repos["telegramEnhanced"]["commit"]
    target_versions["sourceRepos"]["hostBridge"]["commit"] = source_repos["hostBridge"]["commit"]
    target_versions["sourceRepos"]["isolatedDeployment"]["commit"] = source_repos["isolatedDeployment"]["commit"]
    target_versions["sourceRepos"]["platformEngineering"]["commit"] = source_repos["platformEngineering"]["commit"]

    target_gateway_values["image"]["repository"] = source_gateway_image["repository"]
    target_gateway_values["image"]["tag"] = source_gateway_image["tag"]
    target_gateway_values["image"]["digest"] = source_gateway_image["digest"]
    target_gateway_values["env"]["OPENCLAW_TELEGRAM_SHA"] = source_repos["telegramEnhanced"]["commit"]
    target_gateway_values["env"]["OPENCLAW_HOST_BRIDGE_SHA"] = source_repos["hostBridge"]["commit"]
    target_gateway_values["env"]["OPENCLAW_PLATFORM_SHA"] = source_repos["platformEngineering"]["commit"]

    target_platform_values["versions"]["gatewayImage"] = build_gateway_image_ref(
        source_gateway_image["repository"],
        source_gateway_image["tag"],
        source_gateway_image["digest"],
    )
    target_platform_values["versions"]["telegramSha"] = source_repos["telegramEnhanced"]["commit"]
    target_platform_values["versions"]["hostBridgeSha"] = source_repos["hostBridge"]["commit"]
    target_platform_values["versions"]["isolatedDeploymentSha"] = source_repos["isolatedDeployment"]["commit"]
    target_platform_values["versions"]["platformSha"] = source_repos["platformEngineering"]["commit"]

    write_yaml(target_root / "versions.yaml", target_versions)
    write_yaml(target_root / "values" / "openclaw-gateway.yaml", target_gateway_values)
    write_yaml(target_root / "values" / "platform-version.yaml", target_platform_values)

    print(
        f"Promoted {args.source_environment} gateway image "
        f"{build_gateway_image_ref(source_gateway_image['repository'], source_gateway_image['tag'], source_gateway_image['digest'])} "
        f"into {args.target_environment}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
