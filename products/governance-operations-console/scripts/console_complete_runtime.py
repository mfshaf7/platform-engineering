#!/usr/bin/env python3
"""Compose, verify, recover, and retire the complete local Console runtime."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

import platform_operation_provider as provider


PRODUCT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PRODUCT_ROOT.parents[1]
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/home/mfshaf7/projects"))
POLICY_PATH = PRODUCT_ROOT / "complete-runtime-policy.yaml"
STATE_ROOT = Path.home() / ".local/state/platform-engineering/governance-console-complete-runtime"
PRIVATE_ROOT = STATE_ROOT / "private"
RECEIPT_ROOT = STATE_ROOT / "receipts"
RESOLVED_POLICY_PATH = PRIVATE_ROOT / "provider-policy.yaml"
RESOLVED_ACTIVATION_POLICY_PATH = PRIVATE_ROOT / "cross-domain-policy.yaml"
UNIT_ROOT = Path.home() / ".config/systemd/user"
UNIT_NAME = "governance-console-platform-operation-provider.service"
SECRET_NAME = "governance-console-platform-operation-provider"
SERVICE_NAME = "governance-console-platform-operation-provider"
PROVIDER_PORT = 38491
REPO_PATH_OVERRIDES: dict[str, Path] = {}


class RuntimeError(RuntimeError):
    pass


def run(args: list[str], *, check: bool = True, input_value: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        input=input_value,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout or "command failed").strip().splitlines()[-1]
        raise RuntimeError(f"{Path(args[0]).name} failed: {detail}")
    return result


def ensure_private(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.stat().st_uid != os.geteuid():
        raise RuntimeError(f"private runtime path is unsafe: {path}")
    path.chmod(0o700)


def parse_repo_paths(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise RuntimeError("--repo-path must use repo=/absolute/path")
        name, raw = value.split("=", 1)
        path = Path(raw).expanduser()
        if not name or not path.is_absolute() or not path.is_dir():
            raise RuntimeError("--repo-path must use an existing absolute repository path")
        result[name] = path.resolve()
    return result


def repo_path(name: str) -> Path:
    return REPO_PATH_OVERRIDES.get(name, WORKSPACE_ROOT / name)


def git_head(name: str) -> str:
    return run(["git", "-C", str(repo_path(name)), "rev-parse", "HEAD"]).stdout.strip()


def git_tree(name: str) -> str:
    return run(["git", "-C", str(repo_path(name)), "rev-parse", "HEAD^{tree}"]).stdout.strip()


def require_clean_exact_source(name: str, revision: str) -> None:
    path = repo_path(name)
    if not re_full_commit(revision) or not path.is_dir() or git_head(name) != revision:
        raise RuntimeError(f"{name} is not at the exact reviewed revision")
    if run(["git", "-C", str(path), "status", "--porcelain"]).stdout.strip():
        raise RuntimeError(f"{name} must be clean before complete runtime activation")


def re_full_commit(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


def validate_policy(policy_path: Path = POLICY_PATH) -> dict[str, Any]:
    policy = provider.load_policy(policy_path)
    delivery = policy.get("delivery", {})
    architecture = delivery.get("architecture", {})
    if delivery.get("delivery_id") != "delivery-1275" or delivery.get("work_item_ref") != "openproject://work_packages/1291":
        raise RuntimeError("complete runtime Delivery binding is invalid")
    digest = architecture.get("digest", "")
    if (
        architecture.get("artifact_id") != "architecture-packet:delivery-1275-v1"
        or not provider.DIGEST.fullmatch(str(digest))
        or architecture.get("uri") != f"wgcf://artifacts/delivery-art/sha256/{str(digest).removeprefix('sha256:')}"
    ):
        raise RuntimeError("complete runtime architecture binding is invalid")
    runtime = policy.get("runtime", {})
    required = {
        "console_port", "namespace_pattern", "oos_deployment", "provider_port",
        "provider_service", "provider_unit", "session_profile",
    }
    if not isinstance(runtime, dict) or not required.issubset(runtime):
        raise RuntimeError("complete runtime configuration is incomplete")
    if runtime["provider_port"] != PROVIDER_PORT or runtime["provider_unit"] != UNIT_NAME:
        raise RuntimeError("complete runtime provider identity is invalid")
    provider_policy = policy["platform_operation_provider"]
    if provider_policy != {
        "caller_id": "operator-orchestration-service",
        "operator_id": "operator:workspace-owner",
        "profile_id": "accepted-idea-delivery",
        "composition_id": "refinement-catalog",
        "subject_ref": "profile:accepted-idea-delivery",
        "security_gate_id": "gate:platform-operation-security",
    }:
        raise RuntimeError("complete runtime Platform-operation boundary is invalid")
    security = policy["security"]
    required_repos = {
        "governance-operations-console",
        "operator-orchestration-service",
        "platform-engineering",
        "workspace-governance",
        "workspace-governance-control-fabric",
    }
    if (
        security.get("owner_repo") != "security-architecture"
        or security.get("decision_ref") != "docs/reviews/components/2026-10-15-governance-console-platform-operation.yaml"
        or security.get("review_ref") != "docs/reviews/components/2026-10-15-governance-console-platform-operation.md"
        or set(security.get("required_reviewed_repos", [])) != required_repos
    ):
        raise RuntimeError("complete runtime Security decision selector is invalid")
    if security.get("status") == "accepted":
        current = provider.git_head(REPO_ROOT)
        provider.require_security_activation(policy, current)
        revisions = security.get("reviewed_revisions")
        if not isinstance(revisions, dict) or set(revisions) != required_repos:
            raise RuntimeError("complete runtime Security revision set is incomplete")
    elif security.get("status") != "pending":
        raise RuntimeError("complete runtime Security status is invalid")
    return policy


def _git_file(repo: Path, revision: str, path: str) -> str:
    return run(["git", "-C", str(repo), "show", f"{revision}:{path}"]).stdout


def resolve_security_decision(policy: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    security = policy["security"]
    security_repo = repo_path(security["owner_repo"])
    security_revision = git_head(security["owner_repo"])
    if run(["git", "-C", str(security_repo), "status", "--porcelain"]).stdout.strip():
        raise RuntimeError("Security authority must be clean before activation")
    branch = run(["git", "-C", str(security_repo), "symbolic-ref", "--short", "HEAD"], check=False)
    remote = run(["git", "-C", str(security_repo), "rev-parse", "refs/remotes/origin/main"], check=False)
    if branch.returncode or branch.stdout.strip() != "main" or remote.returncode or remote.stdout.strip() != security_revision:
        raise RuntimeError("Security decision must come from current clean origin/main")
    try:
        decision = yaml.safe_load(_git_file(security_repo, security_revision, security["decision_ref"]))
        review = _git_file(security_repo, security_revision, security["review_ref"])
    except (RuntimeError, yaml.YAMLError):
        raise RuntimeError("the exact composed-runtime Security decision is unavailable") from None
    required_fields = {
        "schema_version", "decision_id", "gate_id", "status", "delivery_id",
        "work_item_ref", "architecture", "review_ref", "reviewed_revisions",
        "reviewed_trees",
    }
    if not isinstance(decision, dict) or set(decision) != required_fields:
        raise RuntimeError("the composed-runtime Security decision contract is invalid")
    if (
        decision["schema_version"] != 1
        or decision["decision_id"] != "delivery-1275-platform-operation"
        or decision["gate_id"] != security["gate_id"]
        or decision["status"] != "accepted"
        or decision["delivery_id"] != "delivery-1275"
        or decision["work_item_ref"] != "openproject://work_packages/1303"
        or decision["review_ref"] != security["review_ref"]
        or decision["architecture"] != policy["delivery"]["architecture"]
    ):
        raise RuntimeError("the composed-runtime Security decision is missing, stale, revoked, or outside scope")
    revisions = decision["reviewed_revisions"]
    trees = decision["reviewed_trees"]
    required_repos = set(security["required_reviewed_repos"])
    if (
        not isinstance(revisions, dict)
        or set(revisions) != required_repos
        or not all(re_full_commit(value) for value in revisions.values())
        or not isinstance(trees, dict)
        or set(trees) != {"platform-engineering"}
        or not re_full_commit(trees.get("platform-engineering"))
    ):
        raise RuntimeError("the composed-runtime Security source set is incomplete")
    for name, revision in revisions.items():
        if name == "platform-engineering":
            if git_tree(name) != trees[name]:
                raise RuntimeError("platform-engineering is not the exact Security-reviewed source tree")
            if run(["git", "-C", str(repo_path(name)), "status", "--porcelain"]).stdout.strip():
                raise RuntimeError("platform-engineering must be clean before activation")
        else:
            require_clean_exact_source(name, revision)
    required_review_tokens = [
        policy["delivery"]["architecture"]["uri"],
        policy["delivery"]["architecture"]["digest"],
        *(f"{name}@{revision}" for name, revision in revisions.items()),
        f"platform-engineering-tree@{trees['platform-engineering']}",
    ]
    if any(token not in review for token in required_review_tokens):
        raise RuntimeError("the Security review does not bind the complete exact source set")
    decision_digest = provider.canonical_digest(decision)
    resolved = json.loads(json.dumps(policy))
    resolved["security"].update({
        "status": "accepted",
        "decision_uri": f"security-architecture://git/{security_revision}/{security['decision_ref']}",
        "decision_digest": decision_digest,
        "platform_revision": revisions["platform-engineering"],
        "platform_tree": trees["platform-engineering"],
        "reviewed_revisions": revisions,
        "security_revision": security_revision,
    })
    activation = resolved_activation_policy(resolved)
    return resolved, activation


def resolved_activation_policy(policy: dict[str, Any]) -> dict[str, Any]:
    revisions = policy["security"]["reviewed_revisions"]
    runtime = policy["runtime"]
    return {
        "schema_version": 2,
        "lane": "dev-integration",
        "activation": {
            "delivery_id": "delivery-1275",
            "work_item_ref": "openproject://work_packages/1291",
            "security_gate_id": policy["security"]["gate_id"],
        },
        "proof_scope": {
            "includes": [
                "complete-console-runtime",
                "authenticated-platform-operation-provider",
                "automatic-session-and-runtime-credential-lifecycle",
                "restart-rollback-cleanup-and-teardown",
            ],
            "excludes": ["browser-owner-credentials", "direct-console-platform-authority", "stage-or-production-readiness"],
        },
        "architecture": {
            "artifact_id": policy["delivery"]["architecture"]["artifact_id"],
            "current": {
                "uri": policy["delivery"]["architecture"]["uri"],
                "digest": policy["delivery"]["architecture"]["digest"],
            },
            "relationship": "exact-security-binding",
            "security_review_revisions": list(revisions.values()),
        },
        "console": {"repo": "governance-operations-console", "revision": revisions["governance-operations-console"], "port": runtime["console_port"]},
        "owners": {
            "oos": {
                "repo": "operator-orchestration-service", "revision": revisions["operator-orchestration-service"],
                "profile": runtime["session_profile"], "namespace": runtime["namespace_pattern"],
                "service": "operator-orchestration-service", "deployment": runtime["oos_deployment"],
                "remote_port": 8080, "local_port": 38180,
            },
            "wgcf": {
                "repo": "workspace-governance-control-fabric", "revision": revisions["workspace-governance-control-fabric"],
                "profile": "governance-control-fabric", "namespace": "devint-governance-control-fabric-{operator}",
                "service": "workspace-governance-control-fabric-api", "deployment": "workspace-governance-control-fabric-api",
                "remote_port": 8080, "local_port": 38181,
                "workspace_continuity_projection_enabled": True,
            },
        },
        "authority": {
            "workspace_governance_revision": revisions["workspace-governance"],
            "security_revision": policy["security"]["security_revision"],
            "security_review_ref": policy["security"]["review_ref"],
        },
        "credentials": {
            "console_oos": {"caller_id": "governance-operations-console", "custody": "accepted-idea-delivery-private-runtime"},
            "console_wgcf": {"caller_id": "governance-operations-console", "custody": "platform-operator-private-state", "binding": "governance-console-history-reader"},
            "browser_credentials_allowed": False,
        },
        "session": {
            "policy": "session-projection-policy.yaml", "operator_id": policy["platform_operation_provider"]["operator_id"],
            "profile": runtime["session_profile"], "projection": "private/operator-identity.json",
            "issue_receipt": "receipts/operator-identity-issue.json", "revoke_receipt": "receipts/operator-identity-revoke.json",
        },
        "receipts": {"directory": "governance-console-complete-runtime/receipts", "maximum_age_seconds": 120},
    }


def write_resolved_policies(policy: dict[str, Any], activation: dict[str, Any]) -> None:
    ensure_private(STATE_ROOT)
    ensure_private(PRIVATE_ROOT)
    for path, value in ((RESOLVED_POLICY_PATH, policy), (RESOLVED_ACTIVATION_POLICY_PATH, activation)):
        path.write_text(yaml.safe_dump(value, sort_keys=True), encoding="utf-8")
        path.chmod(0o600)


def require_materialized_policy(policy: dict[str, Any], activation: dict[str, Any]) -> None:
    expected = (
        yaml.safe_dump(policy, sort_keys=True),
        yaml.safe_dump(activation, sort_keys=True),
    )
    paths = (RESOLVED_POLICY_PATH, RESOLVED_ACTIVATION_POLICY_PATH)
    if any(not path.is_file() for path in paths) or tuple(
        path.read_text(encoding="utf-8") for path in paths
    ) != expected:
        raise RuntimeError("the active runtime does not match the current Security decision; restart or activate it")


def require_activation_allowed(policy: dict[str, Any]) -> None:
    try:
        provider.require_security_activation(policy, provider.git_head(REPO_ROOT))
    except provider.ProviderError as exc:
        raise RuntimeError(str(exc)) from None


def operator() -> str:
    value = os.environ.get("DEVINT_OPERATOR", os.environ.get("USER", "")).strip()
    if not value or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for ch in value):
        raise RuntimeError("dev-integration operator identity is invalid")
    return value


def namespace(policy: dict[str, Any]) -> str:
    return policy["runtime"]["namespace_pattern"].replace("{operator}", operator())


def composition_command(policy: dict[str, Any], action: str) -> list[str]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "dev_integration.py"),
        action,
        "--composition",
        policy["platform_operation_provider"]["composition_id"],
        "--workspace-root",
        str(WORKSPACE_ROOT),
    ]
    for name, path in sorted(REPO_PATH_OVERRIDES.items()):
        command.extend(["--repo-path", f"{name}={path}"])
    return command


def cross_domain_command(action: str) -> list[str]:
    command = [
        sys.executable,
        str(PRODUCT_ROOT / "scripts" / "console_cross_domain_activation.py"),
        "--policy",
        str(RESOLVED_ACTIVATION_POLICY_PATH),
        action,
    ]
    for name, path in sorted(REPO_PATH_OVERRIDES.items()):
        command.extend(["--repo-path", f"{name}={path}"])
    return command


def cni_gateway() -> str:
    value = json.loads(run(["ip", "-j", "-4", "addr", "show", "cni0"]).stdout)
    addresses = [
        entry["local"]
        for interface in value
        for entry in interface.get("addr_info", [])
        if entry.get("family") == "inet" and isinstance(entry.get("local"), str)
    ]
    if len(addresses) != 1:
        raise RuntimeError("the local k3s cni0 gateway is unavailable or ambiguous")
    address = ipaddress.ip_address(addresses[0])
    if not address.is_private or address.is_loopback:
        raise RuntimeError("the local k3s cni0 gateway is outside the admitted private boundary")
    return str(address)


def credential() -> str:
    ensure_private(STATE_ROOT)
    ensure_private(PRIVATE_ROOT)
    path = PRIVATE_ROOT / "provider-caller-secret"
    if path.exists():
        if path.is_symlink() or path.stat().st_uid != os.geteuid():
            raise RuntimeError("provider credential path is unsafe")
        secret = path.read_text(encoding="utf-8").strip()
    else:
        secret = secrets.token_urlsafe(48)
        path.write_text(secret + "\n", encoding="utf-8")
    path.chmod(0o600)
    if len(secret) < 32:
        raise RuntimeError("provider credential is invalid")
    return secret


def write_provider_unit(policy: dict[str, Any], gateway: str, secret: str) -> None:
    ensure_private(STATE_ROOT)
    ensure_private(PRIVATE_ROOT)
    UNIT_ROOT.mkdir(parents=True, exist_ok=True)
    env_path = PRIVATE_ROOT / "provider.env"
    env_path.write_text(f"PLATFORM_OPERATION_PROVIDER_CALLER_SECRET={secret}\n", encoding="utf-8")
    env_path.chmod(0o600)
    python = shutil.which("python3")
    if not python:
        raise RuntimeError("python3 is unavailable for the Platform provider")
    state = STATE_ROOT / "provider"
    unit = f"""[Unit]
Description=Governance Console Platform operation provider
After=network.target k3s.service

[Service]
WorkingDirectory={REPO_ROOT}
EnvironmentFile={env_path}
ExecStart={python} {PRODUCT_ROOT / 'scripts' / 'platform_operation_provider.py'} --policy {RESOLVED_POLICY_PATH} --state-root {state} serve --listen-host {gateway} --listen-port {policy['runtime']['provider_port']}
Restart=on-failure
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
"""
    target = UNIT_ROOT / UNIT_NAME
    target.write_text(unit, encoding="utf-8")
    run(["systemctl", "--user", "daemon-reload"])
    run(["systemctl", "--user", "enable", "--now", UNIT_NAME])


def apply_kubernetes_binding(policy: dict[str, Any], gateway: str, secret: str) -> None:
    ns = namespace(policy)
    runtime = policy["runtime"]
    security = policy["security"]
    oos_revision = security["reviewed_revisions"]["operator-orchestration-service"]
    secret_values = {
        "OOS_PLATFORM_OPERATION_CALLER_OPERATOR_BINDINGS_JSON": json.dumps(
            {"governance-operations-console": policy["platform_operation_provider"]["operator_id"]},
            separators=(",", ":"),
        ),
        "OOS_PLATFORM_OPERATION_ENABLED": "true",
        "OOS_PLATFORM_OPERATION_PROVIDER_ALLOW_HTTP": "true",
        "OOS_PLATFORM_OPERATION_PROVIDER_BASE_URL": (
            f"http://{runtime['provider_service']}.{ns}.svc.cluster.local:{runtime['provider_port']}"
        ),
        "OOS_PLATFORM_OPERATION_PROVIDER_CALLER_ID": policy["platform_operation_provider"]["caller_id"],
        "OOS_PLATFORM_OPERATION_PROVIDER_CALLER_SECRET": secret,
        "OOS_PLATFORM_OPERATION_SECURITY_DECISION_DIGEST": security["decision_digest"],
        "OOS_PLATFORM_OPERATION_SECURITY_DECISION_REVISION": oos_revision,
        "OOS_PLATFORM_OPERATION_SECURITY_DECISION_URI": security["decision_uri"],
        "OOS_PLATFORM_OPERATION_STATE_ROOT": "/var/lib/oos/platform-operation",
    }
    secret_manifest = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": SECRET_NAME, "namespace": ns},
        "stringData": secret_values,
        "type": "Opaque",
    }
    service_manifest = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": runtime["provider_service"], "namespace": ns},
        "spec": {"ports": [{"name": "http", "port": runtime["provider_port"], "targetPort": runtime["provider_port"]}]},
    }
    endpoints_manifest = {
        "apiVersion": "v1",
        "kind": "Endpoints",
        "metadata": {"name": runtime["provider_service"], "namespace": ns},
        "subsets": [{
            "addresses": [{"ip": gateway}],
            "ports": [{"name": "http", "port": runtime["provider_port"], "protocol": "TCP"}],
        }],
    }
    manifest = "---\n".join(yaml.safe_dump(item, sort_keys=True) for item in (secret_manifest, service_manifest, endpoints_manifest))
    run(["k3s", "kubectl", "apply", "-f", "-"], input_value=manifest)
    run([
        "k3s", "kubectl", "-n", ns, "set", "env",
        f"deployment/{runtime['oos_deployment']}", f"--from=secret/{SECRET_NAME}",
    ])
    run([
        "k3s", "kubectl", "-n", ns, "rollout", "restart",
        f"deployment/{runtime['oos_deployment']}",
    ])
    run([
        "k3s", "kubectl", "-n", ns, "rollout", "status",
        f"deployment/{runtime['oos_deployment']}", "--timeout=300s",
    ])


def provider_catalog(policy: dict[str, Any], secret: str) -> dict[str, Any]:
    request = Request(
        f"http://{cni_gateway()}:{policy['runtime']['provider_port']}/v1/console-operations/catalog",
        headers={
            "accept": "application/json",
            "x-platform-caller-id": policy["platform_operation_provider"]["caller_id"],
            "x-platform-caller-secret": secret,
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Platform provider catalog is unavailable: {type(exc).__name__}") from None
    if not isinstance(value, dict) or value.get("freshness") != "current":
        raise RuntimeError("Platform provider catalog is not current")
    return value


def console_operations(policy: dict[str, Any]) -> dict[str, Any]:
    try:
        with urlopen(
            Request(
                f"http://127.0.0.1:{policy['runtime']['console_port']}/api/environment-operations",
                headers={"accept": "application/json"},
            ),
            timeout=15,
        ) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Console Platform-operation readback is unavailable: {type(exc).__name__}") from None
    if (
        not isinstance(value, dict)
        or value.get("mode") != "live"
        or value.get("status") != "current"
        or not value.get("catalog", {}).get("subjects")
    ):
        raise RuntimeError("Console Platform-operation readback is incomplete")
    return value


def write_active_marker(policy: dict[str, Any]) -> None:
    ensure_private(STATE_ROOT)
    marker = STATE_ROOT / "active.json"
    payload = {
        "schema_version": 1,
        "platform_revision": provider.git_head(REPO_ROOT),
        "platform_tree": provider.git_tree(REPO_ROOT),
        "security_decision_digest": policy["security"]["decision_digest"],
        "security_decision_uri": policy["security"]["decision_uri"],
        "activated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    marker.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    marker.chmod(0o600)


def remove_active_marker() -> None:
    (STATE_ROOT / "active.json").unlink(missing_ok=True)


def receipt(action: str, policy: dict[str, Any], proof: dict[str, Any]) -> Path:
    ensure_private(RECEIPT_ROOT)
    payload = {
        "schema_version": 1,
        "artifact_type": "governance-console-complete-runtime-receipt",
        "action": action,
        "delivery": policy["delivery"],
        "security": {
            "gate_id": policy["security"]["gate_id"],
            "decision_uri": policy["security"].get("decision_uri"),
            "decision_digest": policy["security"].get("decision_digest"),
            "reviewed_revisions": policy["security"].get("reviewed_revisions", {}),
        },
        "credential_values_embedded": False,
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "proof": proof,
    }
    payload["content_digest"] = provider.canonical_digest(payload)
    target = RECEIPT_ROOT / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{action}.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    target.chmod(0o600)
    return target


def activate(policy: dict[str, Any]) -> Path:
    policy, activation = resolve_security_decision(policy)
    write_resolved_policies(policy, activation)
    require_activation_allowed(policy)
    run(composition_command(policy, "up"))
    secret = credential()
    gateway = cni_gateway()
    write_provider_unit(policy, gateway, secret)
    apply_kubernetes_binding(policy, gateway, secret)
    run(cross_domain_command("activate"))
    write_active_marker(policy)
    return status(policy, action="activate")


def status(policy: dict[str, Any], *, action: str = "status") -> Path:
    policy, activation = resolve_security_decision(policy)
    require_materialized_policy(policy, activation)
    require_activation_allowed(policy)
    run(composition_command(policy, "status"))
    if run(["systemctl", "--user", "is-active", "--quiet", UNIT_NAME], check=False).returncode:
        raise RuntimeError("Platform operation provider service is not active")
    run(cross_domain_command("status"))
    catalog = provider_catalog(policy, credential())
    console = console_operations(policy)
    return receipt(action, policy, {
        "composition": policy["platform_operation_provider"]["composition_id"],
        "composition_current": True,
        "console_mode": console["mode"],
        "console_status": console["status"],
        "platform_catalog_id": catalog["catalog_id"],
        "platform_catalog_source_version": catalog["source_version"],
        "platform_subject_count": len(catalog["subjects"]),
        "provider_active": True,
    })


def restart(policy: dict[str, Any]) -> Path:
    policy, activation = resolve_security_decision(policy)
    write_resolved_policies(policy, activation)
    require_activation_allowed(policy)
    run(["systemctl", "--user", "restart", UNIT_NAME])
    ns = namespace(policy)
    run([
        "k3s", "kubectl", "-n", ns, "rollout", "restart",
        f"deployment/{policy['runtime']['oos_deployment']}",
    ])
    run([
        "k3s", "kubectl", "-n", ns, "rollout", "status",
        f"deployment/{policy['runtime']['oos_deployment']}", "--timeout=300s",
    ])
    run(cross_domain_command("restart"))
    return status(policy, action="restart")


def remove_kubernetes_binding(policy: dict[str, Any]) -> list[str]:
    ns = namespace(policy)
    deployment = f"deployment/{policy['runtime']['oos_deployment']}"
    names = [
        "OOS_PLATFORM_OPERATION_CALLER_OPERATOR_BINDINGS_JSON",
        "OOS_PLATFORM_OPERATION_ENABLED",
        "OOS_PLATFORM_OPERATION_PROVIDER_ALLOW_HTTP",
        "OOS_PLATFORM_OPERATION_PROVIDER_BASE_URL",
        "OOS_PLATFORM_OPERATION_PROVIDER_CALLER_ID",
        "OOS_PLATFORM_OPERATION_PROVIDER_CALLER_SECRET",
        "OOS_PLATFORM_OPERATION_SECURITY_DECISION_DIGEST",
        "OOS_PLATFORM_OPERATION_SECURITY_DECISION_REVISION",
        "OOS_PLATFORM_OPERATION_SECURITY_DECISION_URI",
        "OOS_PLATFORM_OPERATION_STATE_ROOT",
    ]
    failures: list[str] = []
    if run(["k3s", "kubectl", "-n", ns, "set", "env", deployment, *(f"{name}-" for name in names)], check=False).returncode:
        failures.append("oos-environment-removal")
    if run([
        "k3s", "kubectl", "-n", ns, "delete",
        f"secret/{SECRET_NAME}", f"service/{SERVICE_NAME}", f"endpoints/{SERVICE_NAME}",
        "--ignore-not-found=true",
    ], check=False).returncode:
        failures.append("provider-kubernetes-binding-removal")
    return failures


def rollback(policy: dict[str, Any], *, cleanup: bool = False) -> Path:
    failures: list[str] = []
    if RESOLVED_ACTIVATION_POLICY_PATH.is_file():
        if run(cross_domain_command("cleanup" if cleanup else "rollback"), check=False).returncode:
            failures.append("console-cross-domain-cleanup")
    failures.extend(remove_kubernetes_binding(policy))
    if run(["systemctl", "--user", "disable", "--now", UNIT_NAME], check=False).returncode:
        failures.append("provider-service-disable")
    remove_active_marker()
    if cleanup:
        (UNIT_ROOT / UNIT_NAME).unlink(missing_ok=True)
        for name in ("provider.env", "provider-caller-secret"):
            (PRIVATE_ROOT / name).unlink(missing_ok=True)
        RESOLVED_POLICY_PATH.unlink(missing_ok=True)
        RESOLVED_ACTIVATION_POLICY_PATH.unlink(missing_ok=True)
        run(["systemctl", "--user", "daemon-reload"], check=False)
    if failures:
        raise RuntimeError(f"complete runtime rollback is incomplete: {', '.join(failures)}")
    return receipt("cleanup" if cleanup else "rollback", policy, {
        "composition_preserved": True,
        "console_services_active": False,
        "credential_binding_present": False,
        "provider_active": False,
    })


def teardown(policy: dict[str, Any]) -> Path:
    rollback(policy, cleanup=True)
    run(composition_command(policy, "down"))
    return receipt("teardown", policy, {
        "composition_suspended": True,
        "owner_state_preserved": True,
        "provider_active": False,
        "temporary_credentials_removed": True,
    })


def wrong_credential_denied(policy: dict[str, Any]) -> bool:
    request = Request(
        f"http://{cni_gateway()}:{policy['runtime']['provider_port']}/v1/console-operations/catalog",
        headers={
            "accept": "application/json",
            "x-platform-caller-id": policy["platform_operation_provider"]["caller_id"],
            "x-platform-caller-secret": "invalid-credential-value-that-is-never-valid",
        },
    )
    try:
        urlopen(request, timeout=10)
    except HTTPError as exc:
        return exc.code == 403
    except (URLError, TimeoutError):
        return False
    return False


def stale_marker_denied(policy: dict[str, Any], secret: str) -> bool:
    marker = STATE_ROOT / "active.json"
    original = marker.read_text(encoding="utf-8")
    value = json.loads(original)
    value["security_decision_digest"] = "sha256:" + "0" * 64
    marker.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    marker.chmod(0o600)
    try:
        catalog = provider_catalog(policy, secret)
        capabilities = {
            item["action"]: item
            for subject in catalog["subjects"]
            for item in subject["capabilities"]
        }
        return capabilities["dev-integration.smoke"]["available"] is False
    finally:
        marker.write_text(original, encoding="utf-8")
        marker.chmod(0o600)


def revoked_gate_denied(policy: dict[str, Any]) -> bool:
    revoked = json.loads(json.dumps(policy))
    revoked["security"]["status"] = "revoked"
    path = PRIVATE_ROOT / "revoked-provider-policy.yaml"
    path.write_text(yaml.safe_dump(revoked, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)
    try:
        result = run([
            sys.executable,
            str(PRODUCT_ROOT / "scripts" / "platform_operation_provider.py"),
            "--policy", str(path),
            "--state-root", str(STATE_ROOT / "revoked-provider"),
            "serve", "--listen-host", "127.0.0.1", "--listen-port", "0",
        ], check=False)
        return result.returncode != 0
    finally:
        path.unlink(missing_ok=True)


def wait_for_provider(policy: dict[str, Any], secret: str, timeout_seconds: int = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            provider_catalog(policy, secret)
            return
        except RuntimeError:
            time.sleep(0.25)
    raise RuntimeError("Platform operation provider did not recover after process loss")


def verify_operating(policy: dict[str, Any]) -> Path:
    activate_receipt = activate(policy)
    resolved, _ = resolve_security_decision(policy)
    secret = credential()
    if not wrong_credential_denied(resolved):
        raise RuntimeError("invalid provider credential did not fail closed")
    if not stale_marker_denied(resolved, secret):
        raise RuntimeError("stale runtime state did not withhold effect capabilities")
    if not revoked_gate_denied(resolved):
        raise RuntimeError("revoked Security gate did not block provider startup")
    run(["systemctl", "--user", "kill", "--signal=KILL", UNIT_NAME])
    wait_for_provider(resolved, secret)
    restart_receipt = restart(policy)
    rollback_receipt = rollback(resolved)
    if run(["systemctl", "--user", "is-active", "--quiet", UNIT_NAME], check=False).returncode == 0:
        raise RuntimeError("rollback left the Platform provider active")
    teardown_receipt = teardown(resolved)
    restored_receipt = activate(policy)
    return receipt("verify-operating", resolve_security_decision(policy)[0], {
        "activation_receipt": str(activate_receipt),
        "invalid_credential_denied": True,
        "revoked_gate_denied": True,
        "stale_state_denied": True,
        "process_loss_recovered": True,
        "restart_receipt": str(restart_receipt),
        "rollback_receipt": str(rollback_receipt),
        "teardown_receipt": str(teardown_receipt),
        "restored_activation_receipt": str(restored_receipt),
        "normal_availability_restored": True,
    })


def main() -> int:
    global REPO_PATH_OVERRIDES
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("validate", "activate", "status", "restart", "rollback", "cleanup", "teardown", "verify-operating"),
    )
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    parser.add_argument("--repo-path", action="append", default=[])
    args = parser.parse_args()
    try:
        REPO_PATH_OVERRIDES = parse_repo_paths(args.repo_path)
        policy = validate_policy(args.policy)
        if args.action == "validate":
            posture = "activation-ready" if policy["security"]["status"] == "accepted" else "security-pending"
            print(f"complete Console runtime source valid: {posture}")
            return 0
        actions = {
            "activate": activate,
            "status": status,
            "restart": restart,
            "rollback": rollback,
            "cleanup": lambda value: rollback(value, cleanup=True),
            "teardown": teardown,
            "verify-operating": verify_operating,
        }
        result = actions[args.action](policy)
        print(f"complete Console runtime {args.action} succeeded: {result}")
        return 0
    except (RuntimeError, provider.ProviderError) as exc:
        print(f"complete Console runtime {args.action} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
