#!/usr/bin/env python3
import argparse
from pathlib import Path

import yaml


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def dump_yaml(data) -> str:
    return yaml.safe_dump(data, sort_keys=False)


def write_yaml(path: Path, data):
    path.write_text(dump_yaml(data), encoding="utf-8")


def build_gateway_image_ref(repository: str, tag: str, digest: str) -> str:
    if digest:
        return f"{repository}@{digest}"
    return f"{repository}:{tag}"


def sync_environment(environment: str, repo_root: Path) -> tuple[bool, list[Path]]:
    env_root = repo_root / "environments" / environment
    versions_path = env_root / "versions.yaml"
    gateway_values_path = env_root / "values" / "openclaw-gateway.yaml"
    platform_values_path = env_root / "values" / "platform-version.yaml"

    versions = load_yaml(versions_path)
    gateway_values = load_yaml(gateway_values_path)
    platform_values = load_yaml(platform_values_path)

    source_repos = versions["sourceRepos"]
    gateway_image = versions["gateway"]["image"]

    gateway_values["image"]["repository"] = gateway_image["repository"]
    gateway_values["image"]["tag"] = gateway_image["tag"]
    gateway_values["image"]["digest"] = gateway_image["digest"]
    gateway_values["env"]["OPENCLAW_TELEGRAM_SHA"] = source_repos["telegramEnhanced"]["commit"]
    gateway_values["env"]["OPENCLAW_HOST_BRIDGE_SHA"] = source_repos["hostBridge"]["commit"]
    gateway_values["env"]["OPENCLAW_PLATFORM_SHA"] = source_repos["platformEngineering"]["commit"]

    platform_values["versions"]["gatewayImage"] = build_gateway_image_ref(
        gateway_image["repository"],
        gateway_image["tag"],
        gateway_image["digest"],
    )
    platform_values["versions"]["telegramSha"] = source_repos["telegramEnhanced"]["commit"]
    platform_values["versions"]["hostBridgeSha"] = source_repos["hostBridge"]["commit"]
    platform_values["versions"]["isolatedDeploymentSha"] = source_repos["isolatedDeployment"]["commit"]
    platform_values["versions"]["platformSha"] = source_repos["platformEngineering"]["commit"]

    changed = []
    for path, data in (
        (gateway_values_path, gateway_values),
        (platform_values_path, platform_values),
    ):
        rendered = dump_yaml(data)
        if path.read_text(encoding="utf-8") != rendered:
            changed.append(path)
            write_yaml(path, data)

    return (len(changed) > 0, changed)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize environment values files from versions.yaml pins."
    )
    parser.add_argument("environment", nargs="+", help="Environment name(s), for example stage prod")
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero instead of writing when drift is detected",
    )
    args = parser.parse_args()

    drifted = []
    for env in args.environment:
        changed, paths = sync_environment(env, args.repo_root)
        if changed:
            drifted.append((env, paths))
            if args.check:
                print(f"{env} environment contract drift detected:")
                for path in paths:
                    print(f"- {path.relative_to(args.repo_root)}")
        else:
            print(f"{env} environment contract already synchronized")

    if args.check and drifted:
        print("Run scripts/sync_environment_contract.py <environment> to update the generated values files.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
