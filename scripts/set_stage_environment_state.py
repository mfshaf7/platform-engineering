#!/usr/bin/env python3
import argparse
from pathlib import Path

def discover_stage_resources(stage_argocd_root: Path) -> list[str]:
    resources = []
    for path in sorted(stage_argocd_root.glob("*.yaml")):
        if path.name == "kustomization.yaml":
            continue
        resources.append(path.name)
    return resources


def load_resources(path: Path) -> list[str]:
    resources = []
    in_resources = False
    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            stripped = line.strip()
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "state",
        choices=("resume", "suspend", "status"),
        help="Desired stage environment state",
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

    current_resources = load_resources(kustomization_path)

    if args.state == "status":
        print("resumed" if current_resources else "suspended")
        return 0

    desired_resources = managed_resources if args.state == "resume" else []
    if current_resources == desired_resources:
        print(f"Stage environment already {args.state}d")
        return 0

    write_kustomization(kustomization_path, desired_resources)

    print(
        f"Stage environment set to {args.state} "
        f"({len(desired_resources)} Argo resources)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
