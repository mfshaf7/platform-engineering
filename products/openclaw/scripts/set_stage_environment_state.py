#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen

from stage_readiness import reset_stage_promotion_readiness

SUSPEND_SENTINEL = "suspend-sentinel-configmap.yaml"
DEFAULT_STAGE_BRIDGE_SERVICE_NAME = "openclaw-host-bridge-stage.service"
DEFAULT_STAGE_BRIDGE_HEALTH_URL = "http://127.0.0.1:48731/healthz"
DEFAULT_STAGE_GATEWAY_BRIDGE_URL = "http://172.27.88.8:48731"

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


def stage_bridge_service_name() -> str:
    return os.environ.get("OPENCLAW_STAGE_BRIDGE_SERVICE_NAME", DEFAULT_STAGE_BRIDGE_SERVICE_NAME)


def stage_bridge_health_url() -> str:
    return os.environ.get("OPENCLAW_STAGE_BRIDGE_HEALTH_URL", DEFAULT_STAGE_BRIDGE_HEALTH_URL)


def stage_gateway_bridge_url() -> str:
    return os.environ.get("OPENCLAW_STAGE_GATEWAY_BRIDGE_URL", DEFAULT_STAGE_GATEWAY_BRIDGE_URL)


def stage_bridge_policy_path(repo_root: Path) -> Path:
    override = os.environ.get("OPENCLAW_STAGE_BRIDGE_POLICY_PATH")
    if override:
        return Path(override).expanduser()
    return repo_root.parent / "openclaw-host-bridge" / "config" / "policy.stage.local.json"


def stage_openclaw_config_path() -> Path:
    override = os.environ.get("OPENCLAW_STAGE_OPENCLAW_CONFIG_PATH")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".openclaw-stage" / "openclaw.stage.k3s.json"


def run_systemctl(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    command = ["systemctl", *args]
    if os.geteuid() != 0:
        command = ["sudo", *command]
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def validate_stage_bridge_inputs(repo_root: Path) -> None:
    policy_path = stage_bridge_policy_path(repo_root)
    config_path = stage_openclaw_config_path()
    if not policy_path.exists():
        raise SystemExit(
            f"missing stage bridge policy file: {policy_path}. "
            "Create the local stage bridge policy before resuming the stage gateway."
        )
    if not config_path.exists():
        raise SystemExit(
            f"missing stage OpenClaw config: {config_path}. "
            "Create the local stage config before resuming the stage gateway."
        )

    config = json.loads(config_path.read_text(encoding="utf-8"))
    bridge_url = (
        ((config.get("plugins") or {}).get("entries") or {}).get("host-control") or {}
    ).get("config", {}).get("bridgeUrl")
    expected = stage_gateway_bridge_url()
    if bridge_url != expected:
        raise SystemExit(
            f"stage host-control bridgeUrl mismatch in {config_path}: "
            f"expected {expected!r}, got {bridge_url!r}"
        )


def wait_for_stage_bridge_ready(timeout_seconds: int = 20) -> None:
    deadline = time.monotonic() + timeout_seconds
    health_url = stage_bridge_health_url()
    expected_service = stage_bridge_service_name()
    last_error = None
    while time.monotonic() < deadline:
        try:
            result = run_systemctl("is-active", expected_service, capture_output=True)
            if result.stdout.strip() != "active":
                last_error = f"{expected_service} is {result.stdout.strip() or 'inactive'}"
                time.sleep(1)
                continue
        except subprocess.CalledProcessError as exc:
            last_error = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            time.sleep(1)
            continue

        try:
            with urlopen(health_url, timeout=2) as response:
                payload = json.load(response)
            if payload.get("ok") is True:
                return
            last_error = f"{health_url} returned ok={payload.get('ok')!r}"
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(1)

    raise SystemExit(
        f"stage bridge failed to become healthy at {health_url} within {timeout_seconds}s: {last_error}"
    )


def ensure_stage_bridge_running(repo_root: Path) -> None:
    validate_stage_bridge_inputs(repo_root)
    run_systemctl("start", stage_bridge_service_name())
    wait_for_stage_bridge_ready()


def ensure_stage_bridge_stopped() -> None:
    run_systemctl("stop", stage_bridge_service_name())


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
        default=Path(__file__).resolve().parents[3],
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

    current_gateway_active = "gateway" in current_components
    desired_gateway_active = "gateway" in desired_components

    if args.state == "resume" and desired_gateway_active:
        ensure_stage_bridge_running(args.repo_root)

    changed = current_resources != desired_resources
    if changed:
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

    if args.state == "suspend" and not desired_gateway_active:
        ensure_stage_bridge_stopped()

    if not changed:
        scope = ",".join(sorted(affected_components)) or "none"
        bridge_note = ""
        if args.state == "resume" and desired_gateway_active:
            bridge_note = f" stage_bridge={stage_bridge_service_name()}:active"
        elif args.state == "suspend" and not desired_gateway_active:
            bridge_note = f" stage_bridge={stage_bridge_service_name()}:stopped"
        print(f"Stage components already {args.state}d for {scope}{bridge_note}")
        return 0

    active = ",".join(sorted(desired_components)) or "none"
    print(
        f"Stage state={args.state} target={','.join(sorted(requested_components))} "
        f"active={active} resources={len(desired_resources)} "
        f"stage_bridge={'active' if desired_gateway_active else 'stopped'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
