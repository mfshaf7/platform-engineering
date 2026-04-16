#!/usr/bin/env python3
import hashlib
from pathlib import Path

import yaml


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_gateway_image_ref(repository: str, tag: str, digest: str, *, treat_placeholder_as_missing: bool = False) -> str:
    if digest and not (treat_placeholder_as_missing and is_placeholder(digest)):
        return f"{repository}@{digest}"
    return f"{repository}:{tag}"


def is_placeholder(value: str | None) -> bool:
    return value in {"", None} or "replace-me" in str(value)


def load_versions(repo_root: Path, environment: str) -> dict:
    return load_yaml(repo_root / "environments" / environment / "versions.yaml")


def source_bundle_components(versions: dict) -> list[str]:
    return [
        versions["sourceRepos"]["telegramEnhanced"]["commit"],
        versions["sourceRepos"]["hostBridge"]["commit"],
        versions["sourceRepos"]["isolatedDeployment"]["commit"],
        versions["gateway"]["build"]["baseImage"],
        versions["gateway"]["build"]["dockerfile"],
    ]


def compute_source_bundle_ref(versions: dict) -> str:
    source_bundle = "|".join(source_bundle_components(versions))
    return hashlib.sha256(source_bundle.encode("utf-8")).hexdigest()[:12]


def compute_publish_tag(versions: dict) -> str:
    return f"{versions['gateway']['publish']['tagPrefix']}-{compute_source_bundle_ref(versions)}"


def build_metadata(versions: dict) -> dict[str, str]:
    return {
        "telegram_ref": versions["sourceRepos"]["telegramEnhanced"]["commit"],
        "host_bridge_ref": versions["sourceRepos"]["hostBridge"]["commit"],
        "deployment_ref": versions["sourceRepos"]["isolatedDeployment"]["commit"],
        "publish_repository": versions["gateway"]["publish"]["repository"],
        "publish_tag_prefix": versions["gateway"]["publish"]["tagPrefix"],
        "publish_platforms": ",".join(versions["gateway"]["publish"]["platforms"]),
        "publish_tag": compute_publish_tag(versions),
        "source_bundle_ref": compute_source_bundle_ref(versions),
        "base_image": versions["gateway"]["build"]["baseImage"],
        "dockerfile": versions["gateway"]["build"]["dockerfile"],
    }


def write_github_output(path: Path, metadata: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        for key, value in metadata.items():
            fh.write(f"{key}={value}\n")
