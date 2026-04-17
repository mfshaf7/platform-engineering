#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from gateway_environment import dump_yaml, load_yaml, sync_environment, write_yaml


PROD_LIFECYCLE_RELATIVE_PATH = Path("environments/prod/openclaw-lifecycle.yaml")
PROD_KUSTOMIZATION_RELATIVE_PATH = Path("environments/prod/argocd/kustomization.yaml")
PROD_LIFECYCLE_CONFIGMAP_RELATIVE_PATH = Path(
    "environments/prod/argocd/openclaw-prod-lifecycle-configmap.yaml"
)
PROD_VERIFICATION_RELATIVE_PATH = Path("environments/prod/verification.yaml")
VALID_PROD_LIFECYCLE_STATES = {"live", "suspended"}
LIFECYCLE_CONFIGMAP_RESOURCE = "openclaw-prod-lifecycle-configmap.yaml"
PROD_MANAGED_RESOURCES = (
    "openclaw-gateway-app.yaml",
    "platform-secrets-app.yaml",
    "platform-version-app.yaml",
)
PROD_LIVE_RESOURCES = (
    "platform-dashboards-app.yaml",
    LIFECYCLE_CONFIGMAP_RESOURCE,
    "openclaw-gateway-app.yaml",
    "platform-postgresql-secrets-app.yaml",
    "platform-postgresql-app.yaml",
    "openproject-secrets-app.yaml",
    "openproject-app.yaml",
    "platform-secrets-app.yaml",
    "platform-version-app.yaml",
    "observability-app.yaml",
)
PROD_SUSPENDED_RESOURCES = (
    "platform-dashboards-app.yaml",
    LIFECYCLE_CONFIGMAP_RESOURCE,
    "platform-postgresql-secrets-app.yaml",
    "platform-postgresql-app.yaml",
    "openproject-secrets-app.yaml",
    "openproject-app.yaml",
    "observability-app.yaml",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def prod_lifecycle_path(repo_root: Path) -> Path:
    return repo_root / PROD_LIFECYCLE_RELATIVE_PATH


def prod_kustomization_path(repo_root: Path) -> Path:
    return repo_root / PROD_KUSTOMIZATION_RELATIVE_PATH


def prod_lifecycle_configmap_path(repo_root: Path) -> Path:
    return repo_root / PROD_LIFECYCLE_CONFIGMAP_RELATIVE_PATH


def prod_verification_path(repo_root: Path) -> Path:
    return repo_root / PROD_VERIFICATION_RELATIVE_PATH


def default_prod_lifecycle() -> dict:
    return {
        "schemaVersion": 1,
        "product": "openclaw",
        "environment": "prod",
        "state": "live",
        "changedAt": "2026-04-17T00:00:00Z",
        "changedBy": "platform-engineering",
        "reason": "default-live-state",
        "incidentRef": None,
        "note": "Prod OpenClaw is live unless it is deliberately suspended through the governed prod lifecycle control.",
        "managedResources": list(PROD_MANAGED_RESOURCES),
    }


def load_prod_lifecycle(repo_root: Path) -> dict:
    path = prod_lifecycle_path(repo_root)
    if not path.exists():
        return default_prod_lifecycle()
    data = load_yaml(path) or {}
    if not data.get("managedResources"):
        data["managedResources"] = list(PROD_MANAGED_RESOURCES)
    return data


def current_prod_state(repo_root: Path) -> str:
    return str(load_prod_lifecycle(repo_root).get("state") or "live")


def prod_runtime_active(repo_root: Path) -> bool:
    return current_prod_state(repo_root) == "live"


def expected_prod_resources(state: str) -> list[str]:
    return list(PROD_LIVE_RESOURCES if state == "live" else PROD_SUSPENDED_RESOURCES)


def lifecycle_configmap_payload(lifecycle: dict) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": "openclaw-prod-lifecycle",
            "namespace": "argocd",
        },
        "data": {
            "product": "openclaw",
            "environment": "prod",
            "state": str(lifecycle.get("state") or ""),
            "changedAt": str(lifecycle.get("changedAt") or ""),
            "changedBy": str(lifecycle.get("changedBy") or ""),
            "reason": str(lifecycle.get("reason") or ""),
            "incidentRef": str(lifecycle.get("incidentRef") or ""),
            "note": str(lifecycle.get("note") or ""),
        },
    }


def load_resources(path: Path) -> list[str]:
    resources = []
    in_resources = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped == "resources:":
            in_resources = True
            continue
        if in_resources and stripped.startswith("- "):
            resources.append(stripped[2:].strip())
            continue
        if in_resources and stripped:
            break
    return resources


def write_kustomization(path: Path, resources: list[str]) -> None:
    lines = [
        "apiVersion: kustomize.config.k8s.io/v1beta1",
        "kind: Kustomization",
        "resources:",
    ]
    for resource in resources:
        lines.append(f"  - {resource}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sync_prod_lifecycle(repo_root: Path) -> tuple[dict, list[Path]]:
    lifecycle = load_prod_lifecycle(repo_root)
    expected_resources = expected_prod_resources(str(lifecycle.get("state") or "live"))
    changed_paths: list[Path] = []

    kustomization_path = prod_kustomization_path(repo_root)
    current_resources = load_resources(kustomization_path)
    if current_resources != expected_resources:
        write_kustomization(kustomization_path, expected_resources)
        changed_paths.append(kustomization_path)

    configmap_path = prod_lifecycle_configmap_path(repo_root)
    rendered_configmap = dump_yaml(lifecycle_configmap_payload(lifecycle))
    current_configmap = configmap_path.read_text(encoding="utf-8") if configmap_path.exists() else ""
    if current_configmap != rendered_configmap:
        write_yaml(configmap_path, lifecycle_configmap_payload(lifecycle))
        changed_paths.append(configmap_path)

    _, synced_paths = sync_environment("prod", repo_root)
    for path in synced_paths:
        if path not in changed_paths:
            changed_paths.append(path)

    return lifecycle, changed_paths


def validate_prod_lifecycle(repo_root: Path) -> tuple[dict, list[str]]:
    lifecycle = load_prod_lifecycle(repo_root)
    errors: list[str] = []

    state = str(lifecycle.get("state") or "")
    if state not in VALID_PROD_LIFECYCLE_STATES:
        errors.append(
            "prod lifecycle state must be one of "
            + ", ".join(sorted(VALID_PROD_LIFECYCLE_STATES))
            + f", got {state!r}"
        )

    managed_resources = list(lifecycle.get("managedResources") or [])
    if managed_resources != list(PROD_MANAGED_RESOURCES):
        errors.append(
            "prod lifecycle managedResources must match the governed OpenClaw prod slice: "
            + ", ".join(PROD_MANAGED_RESOURCES)
        )

    expected_resources = expected_prod_resources(state or "live")
    current_resources = load_resources(prod_kustomization_path(repo_root))
    if current_resources != expected_resources:
        errors.append(
            "prod Argo kustomization does not match the governed OpenClaw prod lifecycle state"
        )

    configmap_path = prod_lifecycle_configmap_path(repo_root)
    expected_configmap = dump_yaml(lifecycle_configmap_payload(lifecycle))
    current_configmap = configmap_path.read_text(encoding="utf-8") if configmap_path.exists() else ""
    if current_configmap != expected_configmap:
        errors.append("prod lifecycle configmap does not match environments/prod/openclaw-lifecycle.yaml")

    verification = load_yaml(prod_verification_path(repo_root)) or {}
    verification_status = verification.get("status")
    if state == "suspended" and verification_status != "inactive":
        errors.append("prod verification must be inactive while prod OpenClaw is suspended")
    if state == "live" and verification_status == "inactive":
        errors.append("prod verification must not remain inactive while prod OpenClaw is live")

    return lifecycle, errors
