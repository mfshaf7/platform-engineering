#!/usr/bin/env python3
import argparse
from pathlib import Path

from stage_promotion_readiness import reset_stage_promotion_readiness

SUSPEND_SENTINEL = "suspend-sentinel-configmap.yaml"

COMPONENT_RESOURCE_MAP = {
    "gateway": "openclaw-gateway-app.yaml",
    "secrets": "platform-secrets-app.yaml",
    "version": "platform-version-app.yaml",
    "observability": "observability-app.yaml",
    "dashboards": "platform-dashboards-app.yaml",
}

COMPONENT_DEPENDENCIES = {
    "gateway": {"secrets"},
    "dashboards": {"observability"},
}

REVERSE_COMPONENT_DEPENDENCIES = {}
for component, dependencies in COMPONENT_DEPENDENCIES.items():
    for dependency in dependencies:
        REVERSE_COMPONENT_DEPENDENCIES.setdefault(dependency, set()).add(component)

RESOURCE_COMPONENT_MAP = {resource: component for component, resource in COMPONENT_RESOURCE_MAP.items()}


def discover_stage_resources(stage_argocd_root: Path) -> list[str]:
    resources = []
    for path in sorted(stage_argocd_root.glob("*.yaml")):
        if path.name in {"kustomization.yaml", SUSPEND_SENTINEL}:
            continue
        resources.append(path.name)
    return resources


def load_resources(path: Path) -> list[str]:
    resources = []
    in_resources = False
    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
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


def parse_components(raw: str | None, available_components: set[str]) -> set[str]:
    if raw is None:
        return set(available_components)
    items = {part.strip() for part in raw.split(",") if part.strip()}
    if not items:
        raise SystemExit("components must not be empty when provided")
    if "all" in items:
        return set(available_components)
    unknown = sorted(items - available_components)
    if unknown:
        raise SystemExit(
            "unknown components: "
            + ", ".join(unknown)
            + " (valid: all, " + ", ".join(sorted(available_components)) + ")"
        )
    return items


def expand_components(components: set[str], dependency_map: dict[str, set[str]]) -> set[str]:
    expanded = set(components)
    pending = list(components)
    while pending:
        component = pending.pop()
        for dependency in dependency_map.get(component, set()):
            if dependency not in expanded:
                expanded.add(dependency)
                pending.append(dependency)
    return expanded


def resources_for_components(components: set[str]) -> list[str]:
    return [
        resource
        for resource in COMPONENT_RESOURCE_MAP.values()
        if RESOURCE_COMPONENT_MAP[resource] in components
    ]


def components_for_resources(resources: list[str]) -> set[str]:
    return {
        RESOURCE_COMPONENT_MAP[resource]
        for resource in resources
        if resource in RESOURCE_COMPONENT_MAP
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "state",
        choices=("resume", "suspend", "status"),
        help="Desired stage environment state",
    )
    parser.add_argument(
        "--components",
        help=(
            "Comma-separated stage components to target. "
            "Use 'all' or omit to target the full stage environment. "
            "Known components: gateway,secrets,version,observability,dashboards"
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root",
    )
    args = parser.parse_args()

    stage_argocd_root = args.repo_root / "environments" / "stage" / "argocd"
    kustomization_path = stage_argocd_root / "kustomization.yaml"
    managed_resources = discover_stage_resources(stage_argocd_root)

    if not managed_resources:
        raise SystemExit(f"No stage Argo resources found in {stage_argocd_root}")

    available_components = set(COMPONENT_RESOURCE_MAP)
    current_resources = load_resources(kustomization_path)
    current_components = components_for_resources(current_resources)

    if args.state == "status":
        if current_resources == [SUSPEND_SENTINEL]:
            print("suspended")
        else:
            active = ",".join(sorted(current_components)) or "none"
            print(f"active:{active}")
        return 0

    requested_components = parse_components(args.components, available_components)
    target_components = expand_components(requested_components, COMPONENT_DEPENDENCIES)

    if args.state == "resume":
        desired_components = current_components | target_components
        affected_components = target_components
    else:
        suspended_components = expand_components(requested_components, REVERSE_COMPONENT_DEPENDENCIES)
        desired_components = current_components - suspended_components
        affected_components = suspended_components

    desired_resources = resources_for_components(desired_components)
    if not desired_resources:
        desired_resources = [SUSPEND_SENTINEL]

    if current_resources == desired_resources:
        scope = ",".join(sorted(affected_components)) or "none"
        print(f"Stage components already {args.state}d for {scope}")
        return 0

    write_kustomization(kustomization_path, desired_resources)

    active = ",".join(sorted(desired_components)) or "none"
    if desired_resources == [SUSPEND_SENTINEL]:
        reset_stage_promotion_readiness(
            args.repo_root,
            status="inactive",
            note="Stage suspended; explicit resume and approval are required before the next prod promotion.",
        )
    else:
        reset_stage_promotion_readiness(
            args.repo_root,
            status="pending",
            note=f"Stage lifecycle changed; active components now {active}. Re-approve stage before promoting to prod.",
        )

    print(
        f"Stage state={args.state} target={','.join(sorted(requested_components))} "
        f"active={active} resources={len(desired_resources)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
