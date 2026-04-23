#!/usr/bin/env python3
import json
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

TELEGRAM_OVERLAY_STATUSES = {"inactive", "pending-build", "candidate"}
TELEGRAM_OVERLAY_VOLUME_NAME = "telegram-overlay-runtime"
TELEGRAM_OVERLAY_INIT_CONTAINER_NAME = "telegram-overlay-runtime"
TELEGRAM_OVERLAY_GATEWAY_MOUNT_PATH = "/app/extensions/telegram"
TELEGRAM_OVERLAY_VOLUME_ROOT = "/work"
TELEGRAM_OVERLAY_SUBPATH = "telegram"
PROD_RUNTIME_ACTIVE_STATES = {"live"}
PROD_TRAFFIC_ACTIVE_STATES = {"live"}
PROD_PROMOTION_ALLOWED_STATES = {"live", "traffic-stopped", "suspended"}


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def dump_yaml(data) -> str:
    return yaml.safe_dump(data, sort_keys=False)


def write_yaml(path: Path, data):
    path.write_text(dump_yaml(data), encoding="utf-8")


def load_prod_lifecycle_state(repo_root: Path) -> str:
    path = repo_root / "environments" / "prod" / "openclaw-lifecycle.yaml"
    if not path.exists():
        return "live"
    data = load_yaml(path) or {}
    return str(data.get("state") or "live")


def prod_runtime_active_for_state(state: str) -> bool:
    return state in PROD_RUNTIME_ACTIVE_STATES


def prod_traffic_active_for_state(state: str) -> bool:
    return state in PROD_TRAFFIC_ACTIVE_STATES


def prod_promotion_allowed_for_state(state: str) -> bool:
    return state in PROD_PROMOTION_ALLOWED_STATES


def _set_extra_env(gateway_values: dict, name: str, value: str) -> None:
    entries = gateway_values.setdefault("extraEnv", [])
    if not isinstance(entries, list):
        raise ValueError("gateway extraEnv must be a list")
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == name:
            entry["value"] = value
            return
    entries.append({"name": name, "value": value})


def _remove_extra_env(gateway_values: dict, name: str) -> None:
    entries = gateway_values.get("extraEnv", [])
    gateway_values["extraEnv"] = [
        entry
        for entry in entries
        if not (isinstance(entry, dict) and entry.get("name") == name)
    ]


def _set_named_list_entry(container: dict, key: str, entry_key: str, entry: dict) -> None:
    entries = list(container.get(key, []))
    filtered = [
        current
        for current in entries
        if not (isinstance(current, dict) and current.get(entry_key) == entry[entry_key])
    ]
    filtered.append(entry)
    container[key] = filtered


def _remove_named_list_entry(container: dict, key: str, entry_key: str, entry_value: str) -> None:
    entries = list(container.get(key, []))
    container[key] = [
        current
        for current in entries
        if not (isinstance(current, dict) and current.get(entry_key) == entry_value)
    ]


def _set_pod_annotation(gateway_values: dict, key: str, value: str) -> None:
    annotations = gateway_values.setdefault("podAnnotations", {})
    if not isinstance(annotations, dict):
        raise ValueError("gateway podAnnotations must be a mapping")
    annotations[key] = value


def _remove_pod_annotation(gateway_values: dict, key: str) -> None:
    annotations = gateway_values.get("podAnnotations")
    if isinstance(annotations, dict):
        annotations.pop(key, None)


def load_platform_operator_catalog(repo_root: Path) -> dict:
    return load_yaml(repo_root / "docs" / "runbooks" / "platform-operator-catalog.yaml")


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


def _init_container_map(gateway_values: dict) -> dict[str, dict]:
    return {
        entry["name"]: entry
        for entry in gateway_values.get("extraInitContainers", [])
        if isinstance(entry, dict) and "name" in entry
    }


def _volume_map(gateway_values: dict) -> dict[str, dict]:
    return {
        entry["name"]: entry
        for entry in gateway_values.get("extraVolumes", [])
        if isinstance(entry, dict) and "name" in entry
    }


def telegram_overlay_state(versions: dict) -> dict:
    experiments = versions.get("experiments") or {}
    overlay = experiments.get("telegramOverlay") or {}
    return {
        "status": overlay.get("status") or "inactive",
        "qualifiedBaseImage": overlay.get("qualifiedBaseImage") or "",
        "publish": dict(overlay.get("publish") or {}),
        "source": dict(overlay.get("source") or {}),
        "image": dict(overlay.get("image") or {}),
    }


def telegram_overlay_image_ref(overlay: dict) -> str:
    image = overlay.get("image") or {}
    repository = image.get("repository") or ""
    tag = image.get("tag") or ""
    digest = image.get("digest") or ""
    if not repository:
        return "disabled"
    return build_gateway_image_ref(repository, tag, digest, treat_placeholder_as_missing=False)


def telegram_overlay_runtime_active(environment: str, overlay: dict) -> bool:
    return (
        overlay.get("status") == "candidate"
        and not is_placeholder((overlay.get("image") or {}).get("digest"))
        and not is_placeholder((overlay.get("source") or {}).get("commit"))
        and not is_placeholder(overlay.get("qualifiedBaseImage"))
    )


def sync_telegram_overlay(environment: str, versions: dict, gateway_values: dict, platform_values: dict) -> None:
    overlay = telegram_overlay_state(versions)
    active = telegram_overlay_runtime_active(environment, overlay)
    overlay_status = overlay["status"]
    overlay_source = overlay["source"].get("commit") or ""
    overlay_image_ref = telegram_overlay_image_ref(overlay)
    overlay_base_image = overlay.get("qualifiedBaseImage") or ""

    _set_pod_annotation(gateway_values, "openclaw.io/telegram-overlay-status", overlay_status)
    _set_pod_annotation(
        gateway_values,
        "openclaw.io/telegram-overlay-source-sha",
        overlay_source or "disabled",
    )
    _set_pod_annotation(
        gateway_values,
        "openclaw.io/telegram-overlay-image",
        overlay_image_ref if active else "disabled",
    )
    _set_pod_annotation(
        gateway_values,
        "openclaw.io/telegram-overlay-qualified-base-image",
        overlay_base_image or "disabled",
    )

    platform_values["versions"]["telegramOverlayStatus"] = overlay_status
    platform_values["versions"]["telegramOverlaySourceSha"] = overlay_source or "disabled"
    platform_values["versions"]["telegramOverlayImage"] = overlay_image_ref if active else "disabled"
    platform_values["versions"]["telegramOverlayQualifiedBaseImage"] = overlay_base_image or "disabled"

    if active:
        _set_extra_env(gateway_values, "OPENCLAW_TELEGRAM_OVERLAY_SOURCE_SHA", overlay_source)
        _set_named_list_entry(
            gateway_values,
            "extraInitContainers",
            "name",
            {
                "name": TELEGRAM_OVERLAY_INIT_CONTAINER_NAME,
                "image": overlay_image_ref,
                "imagePullPolicy": "IfNotPresent",
                "command": [
                    "sh",
                    "-lc",
                    "rm -rf /work/telegram && mkdir -p /work/telegram && cp -a /telegram-overlay/telegram/. /work/telegram/",
                ],
                "volumeMounts": [
                    {
                        "name": TELEGRAM_OVERLAY_VOLUME_NAME,
                        "mountPath": TELEGRAM_OVERLAY_VOLUME_ROOT,
                    }
                ],
            },
        )
        _set_named_list_entry(
            gateway_values,
            "extraVolumeMounts",
            "mountPath",
            {
                "name": TELEGRAM_OVERLAY_VOLUME_NAME,
                "mountPath": TELEGRAM_OVERLAY_GATEWAY_MOUNT_PATH,
                "subPath": TELEGRAM_OVERLAY_SUBPATH,
                "readOnly": True,
            },
        )
        _set_named_list_entry(
            gateway_values,
            "extraVolumes",
            "name",
            {
                "name": TELEGRAM_OVERLAY_VOLUME_NAME,
                "emptyDir": {},
            },
        )
        return

    _remove_extra_env(gateway_values, "OPENCLAW_TELEGRAM_OVERLAY_SOURCE_SHA")
    _remove_named_list_entry(
        gateway_values,
        "extraInitContainers",
        "name",
        TELEGRAM_OVERLAY_INIT_CONTAINER_NAME,
    )
    _remove_named_list_entry(
        gateway_values,
        "extraVolumeMounts",
        "mountPath",
        TELEGRAM_OVERLAY_GATEWAY_MOUNT_PATH,
    )
    _remove_named_list_entry(
        gateway_values,
        "extraVolumes",
        "name",
        TELEGRAM_OVERLAY_VOLUME_NAME,
    )


def sync_environment(environment: str, repo_root: Path) -> tuple[bool, list[Path]]:
    env_root = repo_root / "environments" / environment
    versions_path = env_root / "versions.yaml"
    gateway_values_path = env_root / "values" / "openclaw-gateway.yaml"
    platform_values_path = env_root / "values" / "platform-version.yaml"

    versions = load_yaml(versions_path)
    gateway_values = load_yaml(gateway_values_path)
    platform_values = load_yaml(platform_values_path)
    platform_operator_catalog = load_platform_operator_catalog(repo_root)

    source_repos = versions["sourceRepos"]
    gateway_image = versions["gateway"]["image"]

    gateway_values["image"]["repository"] = gateway_image["repository"]
    gateway_values["image"]["tag"] = gateway_image["tag"]
    gateway_values["image"]["digest"] = gateway_image["digest"]
    gateway_values["replicaCount"] = versions["gateway"]["replicas"]
    gateway_values["env"]["OPENCLAW_TELEGRAM_SHA"] = source_repos["telegramEnhanced"]["commit"]
    gateway_values["env"]["OPENCLAW_HOST_BRIDGE_SHA"] = source_repos["hostBridge"]["commit"]
    gateway_values["env"]["OPENCLAW_PLATFORM_SHA"] = source_repos["platformEngineering"]["commit"]
    _set_extra_env(
        gateway_values,
        "OPENCLAW_PLATFORM_OPERATOR_CATALOG_JSON",
        json.dumps(platform_operator_catalog, separators=(",", ":")),
    )

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
    sync_telegram_overlay(environment, versions, gateway_values, platform_values)
    _remove_extra_env(gateway_values, "OPENCLAW_RUNTIME_LIFECYCLE_STATE")
    if environment == "prod":
        prod_state = load_prod_lifecycle_state(repo_root)
        platform_values["versions"]["openclawProdLifecycleState"] = prod_state
        platform_values["versions"]["openclawProdRuntimeActive"] = (
            "true" if prod_runtime_active_for_state(prod_state) else "false"
        )
        platform_values["versions"]["openclawProdTrafficActive"] = (
            "true" if prod_traffic_active_for_state(prod_state) else "false"
        )
        platform_values["versions"]["openclawProdPromotionAllowed"] = (
            "true" if prod_promotion_allowed_for_state(prod_state) else "false"
        )
    else:
        platform_values["versions"].pop("openclawProdLifecycleState", None)
        platform_values["versions"].pop("openclawProdRuntimeActive", None)
        platform_values["versions"].pop("openclawProdTrafficActive", None)
        platform_values["versions"].pop("openclawProdPromotionAllowed", None)

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
    platform_operator_catalog = load_platform_operator_catalog(repo_root)

    gateway_image = versions["gateway"]["image"]
    source_repos = versions["sourceRepos"]
    gateway_env = gateway_values["env"]
    platform_versions = platform_values["versions"]
    extra_env = _extra_env_map(gateway_values)
    overlay = telegram_overlay_state(versions)
    overlay_active = telegram_overlay_runtime_active(environment, overlay)
    overlay_source = overlay["source"].get("commit") or ""
    overlay_image_ref = telegram_overlay_image_ref(overlay)
    init_containers = _init_container_map(gateway_values)
    volume_mounts = _volume_mount_map(gateway_values)
    volumes = _volume_map(gateway_values)
    prod_state = load_prod_lifecycle_state(repo_root) if environment == "prod" else None

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
        "platform operator catalog in gateway extraEnv",
        extra_env.get("OPENCLAW_PLATFORM_OPERATOR_CATALOG_JSON"),
        json.dumps(platform_operator_catalog, separators=(",", ":")),
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
    if environment == "prod":
        expect_equal(
            errors,
            "prod lifecycle state in platform version values",
            platform_versions.get("openclawProdLifecycleState"),
            prod_state,
        )
        expect_equal(
            errors,
            "prod runtime active in platform version values",
            platform_versions.get("openclawProdRuntimeActive"),
            "true" if prod_runtime_active_for_state(prod_state or "live") else "false",
        )
        expect_equal(
            errors,
            "prod traffic active in platform version values",
            platform_versions.get("openclawProdTrafficActive"),
            "true" if prod_traffic_active_for_state(prod_state or "live") else "false",
        )
        expect_equal(
            errors,
            "prod promotion allowed in platform version values",
            platform_versions.get("openclawProdPromotionAllowed"),
            "true" if prod_promotion_allowed_for_state(prod_state or "live") else "false",
        )
    if overlay["status"] not in TELEGRAM_OVERLAY_STATUSES:
        errors.append(
            f"telegram overlay status must be one of {sorted(TELEGRAM_OVERLAY_STATUSES)!r}, got {overlay['status']!r}"
        )
    overlay_base_image = overlay.get("qualifiedBaseImage") or ""
    if overlay["status"] in {"pending-build", "candidate"}:
        if is_placeholder(overlay_source):
            errors.append("telegram overlay source commit must be pinned while the overlay lane is active")
        if is_placeholder(overlay_base_image):
            errors.append("telegram overlay qualified base image must be pinned while the overlay lane is active")
        else:
            expect_equal(
                errors,
                "telegram overlay qualified base image",
                overlay_base_image,
                versions["gateway"]["build"]["baseImage"],
            )
    if overlay["status"] == "candidate":
        overlay_image = overlay.get("image") or {}
        if is_placeholder(overlay_image.get("repository")):
            errors.append("telegram overlay image repository must be pinned while the overlay lane is candidate")
        if is_placeholder(overlay_image.get("tag")):
            errors.append("telegram overlay image tag must be pinned while the overlay lane is candidate")
        if is_placeholder(overlay_image.get("digest")):
            errors.append("telegram overlay image digest must be pinned while the overlay lane is candidate")
    expect_equal(
        errors,
        "telegram overlay status in platform version values",
        platform_versions.get("telegramOverlayStatus"),
        overlay["status"],
    )
    expect_equal(
        errors,
        "telegram overlay source SHA in platform version values",
        platform_versions.get("telegramOverlaySourceSha"),
        overlay_source or "disabled",
    )
    expect_equal(
        errors,
        "telegram overlay image in platform version values",
        platform_versions.get("telegramOverlayImage"),
        overlay_image_ref if overlay_active else "disabled",
    )
    expect_equal(
        errors,
        "telegram overlay qualified base image in platform version values",
        platform_versions.get("telegramOverlayQualifiedBaseImage"),
        overlay_base_image or "disabled",
    )
    pod_annotations = gateway_values.get("podAnnotations") or {}
    expect_equal(
        errors,
        "telegram overlay status pod annotation",
        pod_annotations.get("openclaw.io/telegram-overlay-status"),
        overlay["status"],
    )
    expect_equal(
        errors,
        "telegram overlay source pod annotation",
        pod_annotations.get("openclaw.io/telegram-overlay-source-sha"),
        overlay_source or "disabled",
    )
    expect_equal(
        errors,
        "telegram overlay image pod annotation",
        pod_annotations.get("openclaw.io/telegram-overlay-image"),
        overlay_image_ref if overlay_active else "disabled",
    )
    expect_equal(
        errors,
        "telegram overlay qualified base image pod annotation",
        pod_annotations.get("openclaw.io/telegram-overlay-qualified-base-image"),
        overlay_base_image or "disabled",
    )
    overlay_init = init_containers.get(TELEGRAM_OVERLAY_INIT_CONTAINER_NAME)
    overlay_mount = volume_mounts.get(TELEGRAM_OVERLAY_GATEWAY_MOUNT_PATH)
    overlay_volume = volumes.get(TELEGRAM_OVERLAY_VOLUME_NAME)
    if overlay_active:
        expect_equal(
            errors,
            "telegram overlay source env",
            extra_env.get("OPENCLAW_TELEGRAM_OVERLAY_SOURCE_SHA"),
            overlay_source,
        )
        if overlay_init is None:
            errors.append("telegram overlay init container missing while the overlay lane is active")
        else:
            expect_equal(errors, "telegram overlay init image", overlay_init.get("image"), overlay_image_ref)
        if overlay_mount is None:
            errors.append("telegram overlay volume mount missing while the overlay lane is active")
        else:
            expect_equal(errors, "telegram overlay subPath", overlay_mount.get("subPath"), TELEGRAM_OVERLAY_SUBPATH)
        if overlay_volume is None or "emptyDir" not in overlay_volume:
            errors.append("telegram overlay volume missing emptyDir while the overlay lane is active")
    else:
        if extra_env.get("OPENCLAW_TELEGRAM_OVERLAY_SOURCE_SHA") is not None:
            errors.append("telegram overlay source env should be absent while the overlay lane is inactive")
        if overlay_init is not None:
            errors.append("telegram overlay init container should be absent while the overlay lane is inactive")
        if overlay_mount is not None:
            errors.append("telegram overlay mount should be absent while the overlay lane is inactive")
        if overlay_volume is not None:
            errors.append("telegram overlay volume should be absent while the overlay lane is inactive")
    validate_environment_profile(errors, environment, gateway_values)

    return versions, errors
