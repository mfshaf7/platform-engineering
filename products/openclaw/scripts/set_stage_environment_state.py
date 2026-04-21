#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.request import Request, urlopen

from stage_readiness import reset_stage_promotion_readiness, reset_stage_verification

SUSPEND_SENTINEL = "suspend-sentinel-configmap.yaml"
DEFAULT_STAGE_BRIDGE_SERVICE_NAME = "openclaw-host-bridge-stage.service"
DEFAULT_STAGE_BRIDGE_HEALTH_URL = "http://127.0.0.1:48731/healthz"
DEFAULT_STAGE_BRIDGE_REQUEST_URL = "http://127.0.0.1:48731/v1/bridge"
DEFAULT_STAGE_GATEWAY_BRIDGE_URL = "http://172.27.88.8:48731"
DEFAULT_STAGE_WSL_DISTRO = "Platform-Core"
READ_ONLY_SYSTEMCTL_ACTIONS = frozenset({"is-active", "is-enabled", "show", "status", "cat"})
DEFAULT_WINDOWS_POWERSHELL_CANDIDATES = tuple(
    candidate
    for candidate in (
        os.environ.get("OPENCLAW_WINDOWS_POWERSHELL"),
        os.environ.get("OPENCLAW_POWERSHELL_BIN"),
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        "/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/powershell.exe",
        "/mnt/c/Program Files/PowerShell/7/pwsh.exe",
        "/mnt/c/Program Files/PowerShell/7-preview/pwsh.exe",
        "powershell.exe",
        "pwsh.exe",
    )
    if candidate
)

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


def stage_bridge_request_url() -> str:
    return os.environ.get("OPENCLAW_STAGE_BRIDGE_REQUEST_URL", DEFAULT_STAGE_BRIDGE_REQUEST_URL)


def stage_gateway_bridge_url() -> str:
    return os.environ.get("OPENCLAW_STAGE_GATEWAY_BRIDGE_URL", DEFAULT_STAGE_GATEWAY_BRIDGE_URL)


def stage_wsl_distro_name() -> str:
    return (
        os.environ.get("OPENCLAW_STAGE_WSL_DISTRO")
        or os.environ.get("WSL_DISTRO_NAME")
        or DEFAULT_STAGE_WSL_DISTRO
    )


def running_inside_wsl() -> bool:
    return bool(os.environ.get("WSL_DISTRO_NAME")) or "microsoft" in os.uname().release.lower()


def resolve_windows_powershell_binary() -> str:
    for candidate in DEFAULT_WINDOWS_POWERSHELL_CANDIDATES:
        expanded = os.path.expanduser(candidate)
        if os.path.isabs(expanded):
            if Path(expanded).exists():
                return expanded
            continue
        resolved = shutil.which(expanded)
        if resolved:
            return resolved
    raise FileNotFoundError("No Windows PowerShell binary available for stage bridge control")


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


def run_systemctl_via_windows_wsl_root(
    *args: str,
    repo_root: Path,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    if not running_inside_wsl():
        raise RuntimeError("Windows-to-WSL root bridge control is only available inside WSL")
    powershell_bin = resolve_windows_powershell_binary()
    bash_command = shlex.join(["systemctl", *args])
    wsl_command = " ".join(
        (
            "wsl.exe",
            "-d",
            shlex.quote(stage_wsl_distro_name()),
            "-u",
            "root",
            "--cd",
            shlex.quote(str(repo_root)),
            "/bin/bash",
            "-lc",
            shlex.quote(bash_command),
        )
    )
    return subprocess.run(
        [powershell_bin, "-NoProfile", "-Command", wsl_command],
        check=True,
        text=True,
        capture_output=capture_output,
    )


def run_systemctl(
    *args: str,
    capture_output: bool = False,
    repo_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = ["systemctl", *args]
    action = args[0] if args else ""
    if os.geteuid() == 0 or action in READ_ONLY_SYSTEMCTL_ACTIONS:
        return subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=capture_output,
        )

    if repo_root is not None:
        try:
            return run_systemctl_via_windows_wsl_root(
                *args,
                repo_root=repo_root,
                capture_output=capture_output,
            )
        except (FileNotFoundError, RuntimeError):
            pass

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
    telegram_native = (
        (((config.get("channels") or {}).get("telegram") or {}).get("commands") or {}).get("native")
    )
    if telegram_native is not True:
        raise SystemExit(
            f"stage Telegram native commands must be explicitly enabled in {config_path}: "
            "set channels.telegram.commands.native to true before resuming the stage gateway. "
            f"Current value: {telegram_native!r}"
        )

    bridge_url = (
        ((config.get("plugins") or {}).get("entries") or {}).get("host-control") or {}
    ).get("config", {}).get("bridgeUrl")
    expected = stage_gateway_bridge_url()
    if bridge_url != expected:
        raise SystemExit(
            f"stage host-control bridgeUrl mismatch in {config_path}: "
            f"expected {expected!r}, got {bridge_url!r}"
        )


def load_stage_gateway_token() -> str:
    config_path = stage_openclaw_config_path()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    token = (
        ((config.get("gateway") or {}).get("auth") or {}).get("token")
    )
    if not isinstance(token, str) or not token.strip():
        raise SystemExit(
            f"missing stage gateway auth token in {config_path}; expected gateway.auth.token for bridge request validation"
        )
    return token.strip()


def probe_stage_bridge_request_path(timeout_seconds: int = 5) -> None:
    payload = json.dumps(
        {
            "request_id": "stage-bridge-readiness-probe",
            "operation": "config.allowed_roots.list",
            "arguments": {},
            "actor": {
                "channel": "operator",
                "session_key": "stage-lifecycle-validator",
                "sender_id": "mfshaf7",
            },
        }
    ).encode("utf-8")
    request = Request(
        stage_bridge_request_url(),
        data=payload,
        method="POST",
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {load_stage_gateway_token()}",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = json.load(response)
    except HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8")
        except OSError:
            error_body = ""
        raise SystemExit(
            f"stage bridge authenticated request probe failed at {stage_bridge_request_url()}: "
            f"HTTP {exc.code} {error_body}".strip()
        ) from exc
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"stage bridge authenticated request probe failed at {stage_bridge_request_url()}: {exc}"
        ) from exc

    if body.get("ok") is not True:
        raise SystemExit(
            f"stage bridge authenticated request probe returned ok={body.get('ok')!r}: {body}"
        )


def read_systemctl_state(unit_name: str) -> str:
    try:
        result = run_systemctl("is-active", unit_name, capture_output=True)
        return result.stdout.strip() or "unknown"
    except subprocess.CalledProcessError as exc:
        return exc.stdout.strip() or exc.stderr.strip() or "inactive"


def collect_stage_bridge_status(repo_root: Path, verify_request_path: bool) -> dict[str, object]:
    service_name = stage_bridge_service_name()
    state = read_systemctl_state(service_name)
    status: dict[str, object] = {
        "service": service_name,
        "state": state,
        "health_ok": False,
        "request_ok": False,
        "issues": [],
    }

    if state != "active":
        status["issues"] = [f"{service_name} is {state}"]
        return status

    if not verify_request_path:
        return status

    issues: list[str] = []
    try:
        validate_stage_bridge_inputs(repo_root)
    except SystemExit as exc:
        issues.append(str(exc))
        status["issues"] = issues
        return status

    try:
        with urlopen(stage_bridge_health_url(), timeout=2) as response:
            payload = json.load(response)
        if payload.get("ok") is True:
            status["health_ok"] = True
        else:
            issues.append(f"{stage_bridge_health_url()} returned ok={payload.get('ok')!r}")
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        issues.append(f"{stage_bridge_health_url()} failed: {exc}")

    if status["health_ok"]:
        try:
            probe_stage_bridge_request_path()
            status["request_ok"] = True
        except SystemExit as exc:
            issues.append(str(exc))

    status["issues"] = issues
    return status


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
                probe_stage_bridge_request_path()
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
    run_systemctl("enable", stage_bridge_service_name(), repo_root=repo_root)
    run_systemctl("start", stage_bridge_service_name(), repo_root=repo_root)
    wait_for_stage_bridge_ready()


def ensure_stage_bridge_stopped(repo_root: Path) -> None:
    run_systemctl("stop", stage_bridge_service_name(), repo_root=repo_root)
    run_systemctl("disable", stage_bridge_service_name(), repo_root=repo_root)


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
    parser.add_argument(
        "--skip-bridge-control",
        action="store_true",
        help=(
            "Only change Git-managed stage lifecycle state. "
            "Skip local stage bridge service start/stop, for example in GitHub Actions."
        ),
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
            bridge_status = collect_stage_bridge_status(args.repo_root, verify_request_path=False)
            if bridge_status["state"] == "active":
                print(f"stage_bridge:unexpected-active service={bridge_status['service']}")
                return 1
        else:
            active = ",".join(sorted(current_components)) or "none"
            print(f"active:{active}")
            if "gateway" in current_components:
                bridge_status = collect_stage_bridge_status(args.repo_root, verify_request_path=True)
                if (
                    bridge_status["state"] == "active"
                    and bridge_status["health_ok"] is True
                    and bridge_status["request_ok"] is True
                ):
                    print(f"stage_bridge:ready service={bridge_status['service']}")
                    return 0
                issues = "; ".join(bridge_status["issues"]) or "unknown bridge failure"
                print(f"stage_bridge:degraded service={bridge_status['service']} issues={issues}")
                return 1
            bridge_status = collect_stage_bridge_status(args.repo_root, verify_request_path=False)
            if bridge_status["state"] == "active":
                print(f"stage_bridge:unexpected-active service={bridge_status['service']}")
                return 1
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

    if args.state == "resume" and desired_gateway_active and not args.skip_bridge_control:
        ensure_stage_bridge_running(args.repo_root)

    changed = current_resources != desired_resources
    if changed:
        write_kustomization(kustomization_path, desired_resources)

        active = ",".join(sorted(desired_components)) or "none"
        if desired_resources == [SUSPEND_SENTINEL]:
            reset_stage_verification(
                args.repo_root,
                status="pending",
                note="Stage suspended; re-run stage rehearsal checks after the next deliberate resume.",
            )
            reset_stage_promotion_readiness(
                args.repo_root,
                status="inactive",
                note="Stage suspended; explicit resume and approval are required before the next prod promotion.",
            )
        else:
            reset_stage_verification(
                args.repo_root,
                status="pending",
                note=f"Stage lifecycle changed; active components now {active}. Re-run stage rehearsal checks before the next approval.",
            )
            reset_stage_promotion_readiness(
                args.repo_root,
                status="pending",
                note=f"Stage lifecycle changed; active components now {active}. Re-approve stage before promoting to prod.",
            )

    if args.state == "suspend" and not desired_gateway_active and not args.skip_bridge_control:
        ensure_stage_bridge_stopped(args.repo_root)

    if not changed:
        scope = ",".join(sorted(affected_components)) or "none"
        bridge_note = ""
        if args.skip_bridge_control and desired_gateway_active:
            bridge_note = " stage_bridge=skipped"
        elif args.state == "resume" and desired_gateway_active:
            bridge_note = f" stage_bridge={stage_bridge_service_name()}:active"
        elif args.state == "suspend" and not desired_gateway_active:
            bridge_note = f" stage_bridge={stage_bridge_service_name()}:stopped"
        print(f"Stage components already {args.state}d for {scope}{bridge_note}")
        return 0

    active = ",".join(sorted(desired_components)) or "none"
    print(
        f"Stage state={args.state} target={','.join(sorted(requested_components))} "
        f"active={active} resources={len(desired_resources)} "
        f"stage_bridge={'skipped' if args.skip_bridge_control and desired_gateway_active else ('active' if desired_gateway_active else 'stopped')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
