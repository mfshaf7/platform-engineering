#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
from pathlib import Path

import yaml

SUSPEND_SENTINEL = "suspend-sentinel-configmap.yaml"
READINESS_RELATIVE_PATH = Path("environments/stage/promotion-readiness.yaml")
VERSIONS_RELATIVE_PATH = Path("environments/stage/versions.yaml")
KUSTOMIZATION_RELATIVE_PATH = Path("environments/stage/argocd/kustomization.yaml")
DEFAULT_REQUIRED_STAGE_COMPONENTS = ("gateway", "secrets", "version")
COMPONENT_RESOURCE_MAP = {
    "gateway": "openclaw-gateway-app.yaml",
    "secrets": "platform-secrets-app.yaml",
    "version": "platform-version-app.yaml",
    "observability": "observability-app.yaml",
    "dashboards": "platform-dashboards-app.yaml",
}
RESOURCE_COMPONENT_MAP = {resource: component for component, resource in COMPONENT_RESOURCE_MAP.items()}


def readiness_path(repo_root: Path) -> Path:
    return repo_root / READINESS_RELATIVE_PATH


def versions_path(repo_root: Path) -> Path:
    return repo_root / VERSIONS_RELATIVE_PATH


def kustomization_path(repo_root: Path) -> Path:
    return repo_root / KUSTOMIZATION_RELATIVE_PATH


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


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


def components_for_resources(resources: list[str]) -> set[str]:
    return {
        RESOURCE_COMPONENT_MAP[resource]
        for resource in resources
        if resource in RESOURCE_COMPONENT_MAP
    }


def current_stage_components(repo_root: Path) -> set[str]:
    resources = load_resources(kustomization_path(repo_root))
    if resources == [SUSPEND_SENTINEL]:
        return set()
    return components_for_resources(resources)


def snapshot_stage_candidate(repo_root: Path) -> dict:
    versions = load_yaml(versions_path(repo_root))
    source = versions["sourceRepos"]
    image = versions["gateway"]["image"]
    return {
        "image": {
            "repository": image["repository"],
            "tag": image["tag"],
            "digest": image["digest"],
        },
        "sourceRepos": {
            "telegramEnhanced": source["telegramEnhanced"]["commit"],
            "hostBridge": source["hostBridge"]["commit"],
            "isolatedDeployment": source["isolatedDeployment"]["commit"],
            "platformEngineering": source["platformEngineering"]["commit"],
        },
    }


def default_readiness(status: str = "inactive", note: str = "") -> dict:
    return {
        "status": status,
        "requiredComponents": list(DEFAULT_REQUIRED_STAGE_COMPONENTS),
        "approvedAt": None,
        "approvedBy": None,
        "note": note,
        "approvedCandidate": {
            "image": {
                "repository": None,
                "tag": None,
                "digest": None,
            },
            "sourceRepos": {
                "telegramEnhanced": None,
                "hostBridge": None,
                "isolatedDeployment": None,
                "platformEngineering": None,
            },
        },
    }


def required_components(data: dict) -> tuple[str, ...]:
    configured = tuple(data.get("requiredComponents") or DEFAULT_REQUIRED_STAGE_COMPONENTS)
    return configured or DEFAULT_REQUIRED_STAGE_COMPONENTS


def reset_stage_promotion_readiness(repo_root: Path, status: str, note: str) -> dict:
    data = default_readiness(status=status, note=note)
    existing = load_yaml(readiness_path(repo_root)) if readiness_path(repo_root).exists() else {}
    configured = existing.get("requiredComponents")
    if configured:
        data["requiredComponents"] = list(configured)
    write_yaml(readiness_path(repo_root), data)
    return data


def approve_stage_promotion_readiness(repo_root: Path, approved_by: str, note: str) -> dict:
    existing = load_yaml(readiness_path(repo_root)) if readiness_path(repo_root).exists() else {}
    expected_components = set(required_components(existing))
    components = current_stage_components(repo_root)
    missing = sorted(expected_components - components)
    if missing:
        raise SystemExit(
            "stage is not promotion-ready; missing required active components: " + ", ".join(missing)
        )
    data = default_readiness(status="approved", note=note)
    data["requiredComponents"] = list(required_components(existing))
    data["approvedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    data["approvedBy"] = approved_by
    data["approvedCandidate"] = snapshot_stage_candidate(repo_root)
    write_yaml(readiness_path(repo_root), data)
    return data


def validate_stage_promotion_readiness(repo_root: Path) -> dict:
    data = load_yaml(readiness_path(repo_root))
    status = data.get("status")
    if status != "approved":
        raise SystemExit(f"stage promotion readiness is {status or 'unset'}; approval is required before promoting to prod")
    components = current_stage_components(repo_root)
    missing = sorted(set(required_components(data)) - components)
    if missing:
        raise SystemExit(
            "stage promotion readiness is stale; required active components missing: " + ", ".join(missing)
        )
    current_candidate = snapshot_stage_candidate(repo_root)
    approved_candidate = data.get("approvedCandidate") or {}
    if approved_candidate != current_candidate:
        raise SystemExit(
            "stage promotion readiness is stale; the approved candidate no longer matches environments/stage/versions.yaml"
        )
    return data


def print_status(repo_root: Path) -> None:
    data = load_yaml(readiness_path(repo_root)) if readiness_path(repo_root).exists() else default_readiness()
    status = data.get("status", "unset")
    note = data.get("note") or "none"
    approved_by = data.get("approvedBy") or "none"
    approved_at = data.get("approvedAt") or "none"
    components = ",".join(sorted(current_stage_components(repo_root))) or "none"
    required = ",".join(required_components(data))
    print(
        f"status={status} active={components} required={required} approved_by={approved_by} approved_at={approved_at} note={note}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("status", "reset", "approve", "validate"))
    parser.add_argument("--status", choices=("inactive", "pending"), help="reset target state")
    parser.add_argument("--note", default="", help="human note for readiness changes")
    parser.add_argument("--approved-by", default="", help="GitHub actor or operator name")
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root",
    )
    args = parser.parse_args()

    if args.command == "status":
        print_status(args.repo_root)
        return 0

    if args.command == "reset":
        if not args.status:
            raise SystemExit("--status is required for reset")
        data = reset_stage_promotion_readiness(args.repo_root, args.status, args.note)
        print(f"stage readiness reset to {data['status']}")
        return 0

    if args.command == "approve":
        if not args.approved_by:
            raise SystemExit("--approved-by is required for approve")
        data = approve_stage_promotion_readiness(args.repo_root, args.approved_by, args.note)
        print(
            "stage readiness approved for "
            f"{data['approvedCandidate']['image']['repository']}@{data['approvedCandidate']['image']['digest']}"
        )
        return 0

    data = validate_stage_promotion_readiness(args.repo_root)
    print(
        "stage readiness valid for "
        f"{data['approvedCandidate']['image']['repository']}@{data['approvedCandidate']['image']['digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
