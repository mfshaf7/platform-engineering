#!/usr/bin/env python3
"""Activate and prove the Console's local cross-domain read boundary."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml


PRODUCT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PRODUCT_ROOT.parents[1]
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/home/mfshaf7/projects"))
POLICY_PATH = PRODUCT_ROOT / "cross-domain-activation-policy.yaml"
STATE_ROOT = Path.home() / ".local/state/platform-engineering/governance-console-cross-domain"
PRIVATE_ROOT = STATE_ROOT / "private"
RECEIPT_ROOT = STATE_ROOT / "receipts"
UNIT_ROOT = Path.home() / ".config/systemd/user"
CALLER_ID = "governance-operations-console"
UNIT_PREFIX = "governance-console-cross-domain"
WGCF_SECRET = "governance-console-history-reader"
REPO_PATH_OVERRIDES: dict[str, Path] = {}


class ActivationError(RuntimeError):
    pass


def run(
    args: list[str],
    *,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=capture, check=False)
    if check and result.returncode:
        detail = (result.stderr or result.stdout or "command failed").strip().splitlines()[-1]
        raise ActivationError(f"{args[0]} failed: {detail}")
    return result


def load_policy() -> dict[str, Any]:
    value = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 2:
        raise ActivationError("cross-domain activation policy is invalid")
    for owner in ("oos", "wgcf"):
        required = {
            "repo", "revision", "profile", "namespace", "service",
            "remote_port", "local_port",
        }
        if not required.issubset(value.get("owners", {}).get(owner, {})):
            raise ActivationError(f"cross-domain activation policy is incomplete for {owner}")
    return value


def parse_repo_paths(entries: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for entry in entries:
        if "=" not in entry:
            raise ActivationError("--repo-path must use repo=/absolute/path")
        name, raw_path = entry.split("=", 1)
        path = Path(raw_path).expanduser()
        if not name or not path.is_absolute() or not path.is_dir():
            raise ActivationError("--repo-path must use an existing absolute repository path")
        result[name] = path.resolve()
    return result


def operator() -> str:
    return os.environ.get("DEVINT_OPERATOR", os.environ.get("USER", "")).strip()


def repo_path(name: str) -> Path:
    return REPO_PATH_OVERRIDES.get(name, WORKSPACE_ROOT / name)


def git_head(path: Path) -> str:
    return run(["git", "-C", str(path), "rev-parse", "HEAD"]).stdout.strip()


def require_revision(name: str, revision: str) -> None:
    path = repo_path(name)
    if not path.is_dir() or git_head(path) != revision:
        raise ActivationError(f"{name} is not at the Security-approved revision {revision}")
    if run(["git", "-C", str(path), "status", "--porcelain"]).stdout.strip():
        raise ActivationError(f"{name} must be clean before activation")


def require_clean_platform_source() -> None:
    if run(["git", "-C", str(REPO_ROOT), "status", "--porcelain"]).stdout.strip():
        raise ActivationError("the executing Platform checkout must be clean before activation")


def require_architecture_binding(policy: dict[str, Any], review_content: str) -> None:
    architecture = policy.get("architecture", {})
    current = architecture.get("current", {})
    predecessor = architecture.get("predecessor", {})
    if (
        architecture.get("relationship") != "exact-supersession"
        or architecture.get("artifact_id") != "architecture-packet:delivery-1203-v1"
        or current.get("digest") == predecessor.get("digest")
    ):
        raise ActivationError("the architecture packet lineage binding is invalid")
    for label, reference in (("current", current), ("predecessor", predecessor)):
        digest = reference.get("digest", "")
        uri = reference.get("uri", "")
        if (
            not isinstance(digest, str)
            or not digest.startswith("sha256:")
            or len(digest) != 71
            or uri != f"wgcf://artifacts/delivery-art/sha256/{digest.removeprefix('sha256:')}"
        ):
            raise ActivationError(f"the {label} architecture packet reference is invalid")
        if uri not in review_content:
            raise ActivationError(
                f"the Security review does not bind the {label} architecture packet"
            )
    approved_revisions = [
        policy["console"]["revision"],
        *(owner["revision"] for owner in policy["owners"].values()),
        policy["authority"]["workspace_governance_revision"],
    ]
    missing = [revision for revision in approved_revisions if revision not in review_content]
    if missing:
        raise ActivationError("the Security review does not bind every configured source revision")


def manifest_path(profile: str) -> Path:
    return WORKSPACE_ROOT / ".dev-integration" / profile / operator() / "current-session.yaml"


def require_manifest(owner: dict[str, Any]) -> None:
    path = manifest_path(owner["profile"])
    if not path.is_file():
        raise ActivationError(f"{owner['profile']} has no current dev-integration session")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    source = value.get("source_repos", {}).get(owner["repo"], {}) if isinstance(value, dict) else {}
    if source.get("head_sha") != owner["revision"] or source.get("dirty") is not False:
        raise ActivationError(
            f"{owner['profile']} is not running the approved {owner['repo']} source"
        )


def validate(policy: dict[str, Any]) -> None:
    if not operator():
        raise ActivationError("the dev-integration operator is unavailable")
    for command in ("git", "k3s", "npm", "systemctl"):
        if run(["bash", "-lc", f"command -v {command}"], check=False).returncode:
            raise ActivationError(f"required command is unavailable: {command}")
    require_clean_platform_source()
    require_revision(policy["console"]["repo"], policy["console"]["revision"])
    for owner in policy["owners"].values():
        require_revision(owner["repo"], owner["revision"])
        require_manifest(owner)
    require_revision("workspace-governance", policy["authority"]["workspace_governance_revision"])
    security = repo_path("security-architecture")
    revision = policy["authority"]["security_revision"]
    review = policy["authority"]["security_review_ref"]
    if run(
        ["git", "-C", str(security), "cat-file", "-e", f"{revision}^{{commit}}"],
        check=False,
    ).returncode:
        raise ActivationError("the Security activation revision is unavailable")
    if run(
        ["git", "-C", str(security), "cat-file", "-e", f"{revision}:{review}"],
        check=False,
    ).returncode:
        raise ActivationError(
            "the Security activation review is unavailable at the approved revision"
        )
    review_content = run(
        ["git", "-C", str(security), "show", f"{revision}:{review}"]
    ).stdout
    require_architecture_binding(policy, review_content)


def read_oos_secret(policy: dict[str, Any]) -> str:
    path = manifest_path(policy["owners"]["oos"]["profile"]).parent / "broker.env"
    if not path.is_file():
        raise ActivationError("the OOS runtime credential source is unavailable")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("CALLER_AUTH_SECRETS_JSON="):
            value = json.loads(line.split("=", 1)[1])
            secret = value.get(CALLER_ID, "")
            if isinstance(secret, str) and len(secret) >= 32:
                return secret
    raise ActivationError("the dedicated Console OOS credential is unavailable")


def wgcf_secret() -> str:
    path = PRIVATE_ROOT / "wgcf-caller-secret"
    if path.exists():
        secret = path.read_text(encoding="utf-8").strip()
    else:
        PRIVATE_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
        secret = secrets.token_urlsafe(36)
        path.write_text(secret + "\n", encoding="utf-8")
        path.chmod(0o600)
    if len(secret) < 32:
        raise ActivationError("the WGCF Console credential is invalid")
    return secret


def namespace(template: str) -> str:
    return template.replace("{operator}", operator())


def kubectl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["k3s", "kubectl", *args], check=check)


def install_wgcf_binding(policy: dict[str, Any], secret: str) -> None:
    owner = policy["owners"]["wgcf"]
    ns = namespace(owner["namespace"])
    rendered = kubectl(
        "-n", ns, "create", "secret", "generic", WGCF_SECRET,
        f"--from-literal=WGCF_GOVERNANCE_HISTORY_CALLER_ID={CALLER_ID}",
        f"--from-literal=WGCF_GOVERNANCE_HISTORY_CALLER_SECRET={secret}",
        "--dry-run=client", "-o", "yaml",
    ).stdout
    applied = subprocess.run(
        ["k3s", "kubectl", "apply", "-f", "-"], input=rendered, text=True,
        capture_output=True, check=False,
    )
    if applied.returncode:
        raise ActivationError("WGCF reader credential installation failed")
    kubectl(
        "-n", ns, "set", "env", f"deployment/{owner['deployment']}",
        f"--from=secret/{WGCF_SECRET}",
    )
    kubectl("-n", ns, "rollout", "status", f"deployment/{owner['deployment']}", "--timeout=180s")


def wgcf_binding_present(policy: dict[str, Any]) -> bool:
    owner = policy["owners"]["wgcf"]
    ns = namespace(owner["namespace"])
    if kubectl("-n", ns, "get", "secret", WGCF_SECRET, check=False).returncode != 0:
        return False
    result = kubectl(
        "-n", ns, "get", f"deployment/{owner['deployment']}", "-o", "json",
        check=False,
    )
    if result.returncode:
        return False
    deployment = json.loads(result.stdout)
    expected = {
        "WGCF_GOVERNANCE_HISTORY_CALLER_ID",
        "WGCF_GOVERNANCE_HISTORY_CALLER_SECRET",
    }
    observed = {
        item.get("name")
        for container in deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        for item in container.get("env", [])
        if isinstance(item, dict)
    }
    return expected.issubset(observed)


def unit_name(role: str) -> str:
    return f"{UNIT_PREFIX}-{role}.service"


def write_private_env(policy: dict[str, Any], oos_secret: str, history_secret: str) -> Path:
    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = PRIVATE_ROOT / "console.env"
    path.write_text(
        "\n".join([
            f"OOS_BASE_URL=http://127.0.0.1:{policy['owners']['oos']['local_port']}",
            f"OOS_CALLER_ID={CALLER_ID}",
            f"OOS_CALLER_SECRET={oos_secret}",
            f"WGCF_BASE_URL=http://127.0.0.1:{policy['owners']['wgcf']['local_port']}",
            f"WGCF_CALLER_ID={CALLER_ID}",
            f"WGCF_CALLER_SECRET={history_secret}",
        ]) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def write_units(policy: dict[str, Any], env_path: Path) -> None:
    UNIT_ROOT.mkdir(parents=True, exist_ok=True)
    k3s_path = shutil.which("k3s")
    npm_path = shutil.which("npm")
    if not k3s_path or not npm_path:
        raise ActivationError("validated runtime executable path is unavailable")
    for role in ("oos", "wgcf"):
        owner = policy["owners"][role]
        content = f"""[Unit]
Description=Governance Console {role.upper()} dev-integration tunnel
After=network.target

[Service]
ExecStart={k3s_path} kubectl -n {namespace(owner['namespace'])} port-forward service/{owner['service']} {owner['local_port']}:{owner['remote_port']} --address 127.0.0.1
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
"""
        (UNIT_ROOT / unit_name(role)).write_text(content, encoding="utf-8")
    console_root = repo_path(policy["console"]["repo"])
    console = f"""[Unit]
Description=Governance Operations Console cross-domain dev-integration
Wants={unit_name('oos')} {unit_name('wgcf')}
After={unit_name('oos')} {unit_name('wgcf')}

[Service]
WorkingDirectory={console_root}
EnvironmentFile={env_path}
Environment=PATH={Path(npm_path).parent}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart={npm_path} run dev
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
"""
    (UNIT_ROOT / unit_name("console")).write_text(console, encoding="utf-8")
    run(["systemctl", "--user", "daemon-reload"])


def enable_units() -> None:
    units = [unit_name("oos"), unit_name("wgcf"), unit_name("console")]
    run(["systemctl", "--user", "enable", *units])
    run(["systemctl", "--user", "reset-failed", *units], check=False)
    run(["systemctl", "--user", "restart", *units])


def active_runtime_boundary(policy: dict[str, Any], env_path: Path | None = None) -> dict[str, Any]:
    selected_env = env_path or (PRIVATE_ROOT / "console.env")
    return {
        "console_private_environment_mode": (
            oct(selected_env.stat().st_mode & 0o777) if selected_env.is_file() else None
        ),
        "owner_sessions_preserved": all(
            manifest_path(item["profile"]).is_file()
            for item in policy["owners"].values()
        ),
        "services_active": all(
            run(
                ["systemctl", "--user", "is-active", "--quiet", unit_name(role)],
                check=False,
            ).returncode == 0
            for role in ("oos", "wgcf", "console")
        ),
        "wgcf_reader_binding_present": wgcf_binding_present(policy),
    }


def http_json(url: str) -> dict[str, Any]:
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=15) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ActivationError(f"live Console proof failed: {type(exc).__name__}") from None
    if not isinstance(value, dict):
        raise ActivationError("live Console proof returned an invalid payload")
    return value


def wait_for_activity(policy: dict[str, Any]) -> dict[str, Any]:
    url = f"http://127.0.0.1:{policy['console']['port']}/api/governance-activity"
    deadline = time.monotonic() + 180
    last = "Console did not become ready"
    while time.monotonic() < deadline:
        try:
            value = http_json(url)
            if value.get("mode") != "live" or value.get("status") not in {"current", "partial"}:
                last = "Console activity was not live and readable"
            else:
                current_owners = {
                    item.get("owner") for item in value.get("sources", [])
                    if isinstance(item, dict) and item.get("state") == "current"
                }
                if {
                    "operator-orchestration-service",
                    "workspace-governance-control-fabric",
                }.issubset(current_owners):
                    raw = json.dumps(value).casefold()
                    if "synthetic-scenario" in raw or "prototype-local" in raw:
                        raise ActivationError("live Console proof included fixture authority")
                    return value
                last = "Console activity did not expose both canonical owners"
        except ActivationError as exc:
            last = str(exc)
        time.sleep(2)
    raise ActivationError(last)


def receipt(
    action: str,
    policy: dict[str, Any],
    activity: dict[str, Any] | None = None,
    *,
    negative_proof: dict[str, Any] | None = None,
    runtime_boundary: dict[str, Any] | None = None,
) -> Path:
    RECEIPT_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "console-cross-domain-activation-receipt",
        "action": action,
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "lane": "dev-integration",
        "operator": operator(),
        "activation": policy["activation"],
        "architecture": policy["architecture"],
        "proof_scope": policy["proof_scope"],
        "source_revisions": {
            "platform-engineering": git_head(REPO_ROOT),
            policy["console"]["repo"]: policy["console"]["revision"],
            policy["owners"]["oos"]["repo"]: policy["owners"]["oos"]["revision"],
            policy["owners"]["wgcf"]["repo"]: policy["owners"]["wgcf"]["revision"],
            "workspace-governance": policy["authority"]["workspace_governance_revision"],
            "security-architecture": policy["authority"]["security_revision"],
        },
        "credential_boundary": {
            "browser_credentials_allowed": policy["credentials"]["browser_credentials_allowed"],
            "console_oos_caller_id": policy["credentials"]["console_oos"]["caller_id"],
            "console_wgcf_caller_id": policy["credentials"]["console_wgcf"]["caller_id"],
            "credentials_embedded": False,
        },
        "result": "succeeded",
    }
    if activity is not None:
        payload["live_proof"] = {
            "mode": activity.get("mode"),
            "status": activity.get("status"),
            "source_owners": sorted({
                item.get("owner") for item in activity.get("sources", [])
                if isinstance(item, dict)
            }),
            "current_source_owners": sorted({
                item.get("owner") for item in activity.get("sources", [])
                if isinstance(item, dict) and item.get("state") == "current"
            }),
            "event_count": len(activity.get("events", [])),
            "observed_at": activity.get("observedAt"),
            "truncated": activity.get("truncated"),
        }
    if negative_proof is not None:
        payload["negative_proof"] = negative_proof
    if runtime_boundary is not None:
        payload["runtime_boundary"] = runtime_boundary
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    payload["content_digest"] = f"sha256:{digest}"
    path = RECEIPT_ROOT / f"{timestamp}-{action}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def activate(policy: dict[str, Any]) -> Path:
    validate(policy)
    history_secret = wgcf_secret()
    install_wgcf_binding(policy, history_secret)
    env_path = write_private_env(policy, read_oos_secret(policy), history_secret)
    write_units(policy, env_path)
    enable_units()
    activity = wait_for_activity(policy)
    return receipt(
        "activate",
        policy,
        activity,
        runtime_boundary=active_runtime_boundary(policy, env_path),
    )


def status(policy: dict[str, Any]) -> Path:
    validate(policy)
    for role in ("oos", "wgcf", "console"):
        active = run(
            ["systemctl", "--user", "is-active", "--quiet", unit_name(role)],
            check=False,
        )
        if active.returncode:
            raise ActivationError(f"{role} activation service is not active")
    return receipt(
        "status",
        policy,
        wait_for_activity(policy),
        runtime_boundary=active_runtime_boundary(policy),
    )


def restart(policy: dict[str, Any]) -> Path:
    validate(policy)
    run([
        "systemctl", "--user", "restart",
        unit_name("oos"), unit_name("wgcf"), unit_name("console"),
    ])
    return receipt(
        "restart",
        policy,
        wait_for_activity(policy),
        runtime_boundary=active_runtime_boundary(policy),
    )


def rehearse(policy: dict[str, Any]) -> Path:
    validate(policy)
    run(["systemctl", "--user", "stop", unit_name("wgcf")])
    deadline = time.monotonic() + 60
    negative: dict[str, Any] | None = None
    try:
        while time.monotonic() < deadline:
            try:
                value = http_json(
                    f"http://127.0.0.1:{policy['console']['port']}/api/governance-activity"
                )
            except ActivationError:
                time.sleep(1)
                continue
            raw = json.dumps(value).casefold()
            unavailable = [
                source for source in value.get("sources", [])
                if isinstance(source, dict)
                and source.get("owner") == "workspace-governance-control-fabric"
                and source.get("state") == "unavailable"
            ]
            if (
                value.get("mode") == "live"
                and value.get("status") == "partial"
                and unavailable
                and "synthetic-scenario" not in raw
                and "prototype-local" not in raw
            ):
                negative = {
                    "disconnected_owner": "workspace-governance-control-fabric",
                    "mode": value.get("mode"),
                    "status": value.get("status"),
                    "fixture_fallback": False,
                    "error_code": unavailable[0].get("errorCode"),
                }
                break
            time.sleep(1)
        if negative is None:
            raise ActivationError(
                "configured owner disconnection did not fail visibly without fixture fallback"
            )
    finally:
        run(["systemctl", "--user", "start", unit_name("wgcf"), unit_name("console")])
    positive = wait_for_activity(policy)
    return receipt(
        "rehearse",
        policy,
        positive,
        negative_proof=negative,
        runtime_boundary=active_runtime_boundary(policy),
    )


def rollback(policy: dict[str, Any], *, remove_files: bool = False) -> Path:
    for role in ("console", "wgcf", "oos"):
        run(["systemctl", "--user", "disable", "--now", unit_name(role)], check=False)
    owner = policy["owners"]["wgcf"]
    ns = namespace(owner["namespace"])
    kubectl(
        "-n", ns, "set", "env", f"deployment/{owner['deployment']}",
        "WGCF_GOVERNANCE_HISTORY_CALLER_ID-", "WGCF_GOVERNANCE_HISTORY_CALLER_SECRET-",
    )
    kubectl("-n", ns, "delete", "secret", WGCF_SECRET, "--ignore-not-found=true")
    kubectl("-n", ns, "rollout", "status", f"deployment/{owner['deployment']}", "--timeout=180s")
    oos = policy["owners"]["oos"]
    kubectl(
        "-n", namespace(oos["namespace"]), "rollout", "status",
        "deployment/operator-orchestration-service", "--timeout=180s",
    )
    for item in policy["owners"].values():
        if not manifest_path(item["profile"]).is_file():
            raise ActivationError(f"rollback removed owner session state for {item['profile']}")
    if remove_files:
        for role in ("console", "wgcf", "oos"):
            (UNIT_ROOT / unit_name(role)).unlink(missing_ok=True)
        for name in ("console.env", "wgcf-caller-secret"):
            (PRIVATE_ROOT / name).unlink(missing_ok=True)
        run(["systemctl", "--user", "daemon-reload"])
    binding_absent = not wgcf_binding_present(policy)
    services_inactive = all(
        run(
            ["systemctl", "--user", "is-active", "--quiet", unit_name(role)],
            check=False,
        ).returncode != 0
        for role in ("console", "wgcf", "oos")
    )
    private_files_absent = all(
        not (PRIVATE_ROOT / name).exists()
        for name in ("console.env", "wgcf-caller-secret")
    )
    if not binding_absent or not services_inactive or (remove_files and not private_files_absent):
        raise ActivationError("rollback or cleanup live readback is incomplete")
    return receipt(
        "cleanup" if remove_files else "rollback",
        policy,
        runtime_boundary={
            "owner_sessions_preserved": True,
            "private_files_removed": private_files_absent,
            "services_active": False,
            "wgcf_reader_binding_present": False,
        },
    )


def main() -> int:
    global REPO_PATH_OVERRIDES
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("validate", "activate", "status", "restart", "rehearse", "rollback", "cleanup"),
    )
    parser.add_argument(
        "--repo-path",
        action="append",
        default=[],
        metavar="REPO=/ABSOLUTE/PATH",
        help="select a clean exact-revision checkout without changing the workspace primary checkout",
    )
    args = parser.parse_args()
    try:
        REPO_PATH_OVERRIDES = parse_repo_paths(args.repo_path)
        policy = load_policy()
        if args.action == "validate":
            validate(policy)
            print("cross-domain activation inputs valid")
            return 0
        path = {
            "activate": activate,
            "status": status,
            "restart": restart,
            "rehearse": rehearse,
            "rollback": lambda value: rollback(value),
            "cleanup": lambda value: rollback(value, remove_files=True),
        }[args.action](policy)
        print(f"cross-domain {args.action} succeeded: {path}")
        return 0
    except ActivationError as exc:
        print(f"cross-domain {args.action} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
