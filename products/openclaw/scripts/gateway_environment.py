#!/usr/bin/env python3
from pathlib import Path

import yaml

from gateway_contract import build_gateway_image_ref, compute_publish_tag


ENVIRONMENT_PROFILES = {
    "stage": {
        "openclaw_env": "stage",
        "config_path": "/home/node/.openclaw/openclaw.stage.k3s.json",
        "config_mount_path": "/home/node/.openclaw/openclaw.stage.k3s.json",
        "config_mount_subpath": "openclaw.stage.k3s.json",
        "host_path": "/home/mfshaf7/.openclaw-stage",
        "term": "xterm-256color",
    },
    "prod": {
        "openclaw_env": "prod",
        "config_path": "/home/node/.openclaw/openclaw.k3s.json",
        "config_mount_path": "/home/node/.openclaw/openclaw.k3s.json",
        "config_mount_subpath": "openclaw.k3s.json",
        "host_path": "/home/mfshaf7/.openclaw",
        "host_network": True,
        "dns_policy": "ClusterFirstWithHostNet",
        "term": "xterm-256color",
    },
}


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def dump_yaml(data) -> str:
    return yaml.safe_dump(data, sort_keys=False)


def write_yaml(path: Path, data):
    path.write_text(dump_yaml(data), encoding="utf-8")


def is_placeholder(value: str | None) -> bool:
    return value in {"", None} or "replace-me" in str(value)


def _extra_env_map(gateway_values: dict) -> dict[str, str]:
    return {
        entry["name"]: entry.get("value")
        for entry in gateway_values.get("extraEnv", [])
        if isinstance(entry, dict) and "name" in entry
    }


def _volume_mount_map(gateway_values: dict) -> dict[str, dict]:
    return {
        entry["mountPath"]: entry
        for entry in gateway_values.get("extraVolumeMounts", [])
        if isinstance(entry, dict) and "mountPath" in entry
    }


def _volume_host_path_map(gateway_values: dict) -> dict[str, str]:
    return {
        entry["name"]: entry["hostPath"]["path"]
        for entry in gateway_values.get("extraVolumes", [])
        if (
            isinstance(entry, dict)
            and "name" in entry
            and isinstance(entry.get("hostPath"), dict)
            and "path" in entry["hostPath"]
        )
    }


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
    gateway_values["replicaCount"] = versions["gateway"]["replicas"]
    gateway_values["env"]["OPENCLAW_TELEGRAM_SHA"] = source_repos["telegramEnhanced"]["commit"]
    gateway_values["env"]["OPENCLAW_HOST_BRIDGE_SHA"] = source_repos["hostBridge"]["commit"]
    gateway_values["env"]["OPENCLAW_PLATFORM_SHA"] = source_repos["platformEngineering"]["commit"]

    platform_values["versions"]["gatewayImage"] = build_gateway_image_ref(
        gateway_image["repository"],
        gateway_image["tag"],
        gateway_image["digest"],
        treat_placeholder_as_missing=False,
    )
    platform_values["versions"]["telegramSha"] = source_repos["telegramEnhanced"]["commit"]
    platform_values["versions"]["hostBridgeSha"] = source_repos["hostBridge"]["commit"]
    platform_values["versions"]["runtimeDistributionSha"] = source_repos["runtimeDistribution"]["commit"]
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


def expect_equal(errors, label, actual, expected):
    if actual != expected:
        errors.append(f"{label}: expected {expected!r}, got {actual!r}")


def validate_environment_profile(errors: list[str], environment: str, gateway_values: dict) -> None:
    profile = ENVIRONMENT_PROFILES.get(environment)
    if not profile:
        return

    extra_env = _extra_env_map(gateway_values)
    volume_mounts = _volume_mount_map(gateway_values)
    volume_host_paths = _volume_host_path_map(gateway_values)

    expect_equal(errors, "gateway OPENCLAW_ENV", gateway_values["env"].get("OPENCLAW_ENV"), profile["openclaw_env"])
    expect_equal(errors, "gateway OPENCLAW_CONFIG_PATH", extra_env.get("OPENCLAW_CONFIG_PATH"), profile["config_path"])
    expect_equal(errors, "gateway TERM", extra_env.get("TERM"), profile["term"])
    expect_equal(
        errors,
        "gateway openclaw-home host path",
        volume_host_paths.get("openclaw-home"),
        profile["host_path"],
    )

    config_mount = volume_mounts.get(profile["config_mount_path"])
    if config_mount is None:
        errors.append(f"gateway config mount missing: expected {profile['config_mount_path']!r}")
    else:
        expect_equal(
            errors,
            "gateway config subPath",
            config_mount.get("subPath"),
            profile["config_mount_subpath"],
        )

    if "host_network" in profile:
        expect_equal(errors, "gateway hostNetwork", gateway_values.get("hostNetwork"), profile["host_network"])
    if "dns_policy" in profile:
        expect_equal(errors, "gateway dnsPolicy", gateway_values.get("dnsPolicy"), profile["dns_policy"])


def validate_environment_contract(
    environment: str,
    repo_root: Path,
    *,
    require_deterministic_tag: bool = False,
) -> tuple[dict, list[str]]:
    env_root = repo_root / "environments" / environment
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
        treat_placeholder_as_missing=True,
    )
    expected_publish_tag = compute_publish_tag(versions)

    errors = []
    if require_deterministic_tag:
        expect_equal(
            errors,
            "gateway publish tag from source bundle",
            gateway_image["tag"],
            expected_publish_tag,
        )
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
        "gateway replica count",
        gateway_values["replicaCount"],
        versions["gateway"]["replicas"],
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
        "runtime distribution SHA in platform version values",
        platform_versions["runtimeDistributionSha"],
        source_repos["runtimeDistribution"]["commit"],
    )
    expect_equal(
        errors,
        "platform SHA in platform version values",
        platform_versions["platformSha"],
        source_repos["platformEngineering"]["commit"],
    )
    validate_environment_profile(errors, environment, gateway_values)

    return versions, errors
