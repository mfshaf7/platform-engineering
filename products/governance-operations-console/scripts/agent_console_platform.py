#!/usr/bin/env python3
"""Validate and verify the Platform-owned Agent Console runtime boundary."""

from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml


PRODUCT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PRODUCT_ROOT.parents[1]
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/home/mfshaf7/projects"))
POLICY_PATH = PRODUCT_ROOT / "agent-console-commissioning-policy.yaml"
STATE_ROOT = Path.home() / ".local/state/platform-engineering/agent-console"


class AgentConsolePlatformError(RuntimeError):
    pass


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if check and result.returncode:
        detail = (result.stderr or result.stdout or "command failed").strip().splitlines()[-1]
        raise AgentConsolePlatformError(f"{args[0]} failed: {detail}")
    return result


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise AgentConsolePlatformError("Agent Console commissioning policy is invalid")
    return value


def _require_text(mapping: dict[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AgentConsolePlatformError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def _git_head(repo: Path, ref: str = "HEAD") -> str:
    return run(["git", "-C", str(repo), "rev-parse", ref]).stdout.strip()


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    activation = policy.get("activation") or {}
    model = policy.get("model") or {}
    runtime = policy.get("runtime") or {}
    security = policy.get("security") or {}
    if activation.get("security_gate_id") != "gate:agent-console-operating-acceptance":
        raise AgentConsolePlatformError("Agent Console operating Security gate is not exact")
    if activation.get("composition_id") != "refinement-catalog":
        raise AgentConsolePlatformError("Agent Console must reuse refinement-catalog")
    expected_model = {
        "profile_id": "agent-console-assistant-v1",
        "caller_id": "operator-orchestration-service/agent-console",
        "task_kind": "assistant_response",
        "contract_ref": "oos.agent-console.interaction.v1",
        "contract_version": "1.0",
        "provider_output_schema_ref": (
            "platform-engineering/security/schemas/agent-console-response.schema.json"
        ),
    }
    if model != expected_model:
        raise AgentConsolePlatformError("Agent Console governed model binding is not exact")
    for key in (
        "oos_profile", "oos_namespace_pattern", "oos_service",
        "gateway_profile", "gateway_namespace_pattern", "gateway_service", "caller_id",
    ):
        _require_text(runtime, key, "runtime")
    if runtime["caller_id"] != "governance-operations-console":
        raise AgentConsolePlatformError("Agent Console runtime caller is not exact")
    for key in ("oos_local_port", "gateway_local_port"):
        if not isinstance(runtime.get(key), int) or runtime[key] <= 0:
            raise AgentConsolePlatformError(f"runtime.{key} must be a positive integer")
    if security.get("owner_repo") != "security-architecture":
        raise AgentConsolePlatformError("Agent Console Security owner is not exact")
    _require_text(security, "review_ref", "security")
    required_repos = security.get("exact_revision_repos")
    if not isinstance(required_repos, list) or set(required_repos) != {
        "context-governance-gateway",
        "operator-orchestration-service",
        "platform-engineering",
        "governance-operations-console",
        "workspace-governance",
    }:
        raise AgentConsolePlatformError("Agent Console exact-revision review set is incomplete")

    from sys import path as module_path
    runtime_root = REPO_ROOT / "dev-integration/profiles/governed-ai-gateway/runtime"
    module_path.insert(0, str(runtime_root))
    from model_profile_resolver import resolve_model_profile_registry

    resolved = resolve_model_profile_registry(
        REPO_ROOT / "security/governed-ai-model-profiles.yaml",
        REPO_ROOT / "security/governed-ai-access-plane.yaml",
        environment="dev-integration",
    )["profiles"][model["profile_id"]]
    task = resolved["task_contracts"][model["task_kind"]]
    if (
        resolved["profile_status"] != "active"
        or resolved["binding_status"] != "active"
        or resolved["profile_activation_allowed"] is not True
        or resolved["allowed_callers"] != [model["caller_id"]]
        or task["contract_ref"] != model["contract_ref"]
        or task["contract_version"] != model["contract_version"]
        or task["provider_output_schema_ref"] != model["provider_output_schema_ref"]
    ):
        raise AgentConsolePlatformError("resolved Agent Console profile does not match policy")

    for repo_name, minimum in (policy.get("source_minimums") or {}).items():
        if not isinstance(minimum, str) or len(minimum) != 40:
            raise AgentConsolePlatformError(f"invalid source minimum for {repo_name}")
        repo = WORKSPACE_ROOT / repo_name
        if repo.is_dir() and run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", minimum, "HEAD"],
            check=False,
        ).returncode:
            raise AgentConsolePlatformError(f"{repo_name} does not contain its required source minimum")
    return resolved


def _read_broker_caller_secret(operator: str, caller_id: str) -> str:
    path = (
        WORKSPACE_ROOT / ".dev-integration/accepted-idea-delivery" / operator / "broker.env"
    )
    try:
        line = next(
            item for item in path.read_text(encoding="utf-8").splitlines()
            if item.startswith("CALLER_AUTH_SECRETS_JSON=")
        )
        secret = json.loads(line.split("=", 1)[1])[caller_id]
    except (OSError, StopIteration, KeyError, json.JSONDecodeError) as exc:
        raise AgentConsolePlatformError(
            "accepted-idea-delivery does not expose the private Console caller binding"
        ) from exc
    if not isinstance(secret, str) or not secret:
        raise AgentConsolePlatformError("Console caller binding is empty")
    return secret


def _request(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    method: str | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method or ("POST" if data is not None else "GET"),
    )
    try:
        with urlopen(request, timeout=90) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    except (URLError, TimeoutError) as exc:
        raise AgentConsolePlatformError(f"runtime endpoint unavailable: {url}") from exc


def _wait_ready(url: str) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            status, _ = _request(url)
            if status == 200:
                return
        except AgentConsolePlatformError:
            pass
        time.sleep(0.5)
    raise AgentConsolePlatformError(f"runtime did not become ready: {url}")


@contextmanager
def port_forward(namespace: str, service: str, local_port: int) -> Iterator[None]:
    process = subprocess.Popen(
        [
            "k3s", "kubectl", "-n", namespace, "port-forward",
            f"service/{service}", f"{local_port}:8080", "--address", "127.0.0.1",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _require_security_review(policy: dict[str, Any]) -> dict[str, str]:
    security = policy["security"]
    review = WORKSPACE_ROOT / security["owner_repo"] / security["review_ref"]
    if not review.is_file():
        raise AgentConsolePlatformError("Agent Console exact-revision Security review is missing")
    content = review.read_text(encoding="utf-8")
    if policy["activation"]["security_gate_id"] not in content:
        raise AgentConsolePlatformError("Security review does not accept the operating gate")
    revisions: dict[str, str] = {}
    for repo_name in security["exact_revision_repos"]:
        repo = WORKSPACE_ROOT / repo_name
        revision = _git_head(repo)
        if revision not in content:
            raise AgentConsolePlatformError(
                f"Security review does not bind current {repo_name} revision"
            )
        revisions[repo_name] = revision
    return revisions


def verify_operating(policy: dict[str, Any]) -> Path:
    resolved = validate_policy(policy)
    revisions = _require_security_review(policy)
    runtime = policy["runtime"]
    operator = os.environ.get("DEVINT_OPERATOR", os.environ.get("USER", "")).strip()
    if not operator:
        raise AgentConsolePlatformError("operator identity is unavailable")
    operator_id = f"operator:{operator}"
    caller_id = runtime["caller_id"]
    caller_secret = _read_broker_caller_secret(operator, caller_id)
    oos_base = f"http://127.0.0.1:{runtime['oos_local_port']}"
    gateway_base = f"http://127.0.0.1:{runtime['gateway_local_port']}"
    now = datetime.now(UTC)
    token = hashlib.sha256(now.isoformat().encode("utf-8")).hexdigest()[:16]
    session_id = f"agent-console-proof-{token}"
    content = "Synthetic model-safe Agent Console operating verification context."
    headers = {
        "x-oos-caller-id": caller_id,
        "x-oos-caller-secret": caller_secret,
        "x-oos-operator-id": operator_id,
    }

    namespaces = {
        "oos": runtime["oos_namespace_pattern"].format(operator=operator),
        "gateway": runtime["gateway_namespace_pattern"].format(operator=operator),
    }
    with ExitStack() as stack:
        stack.enter_context(port_forward(namespaces["oos"], runtime["oos_service"], runtime["oos_local_port"]))
        stack.enter_context(port_forward(namespaces["gateway"], runtime["gateway_service"], runtime["gateway_local_port"]))
        _wait_ready(f"{oos_base}/readyz")
        _wait_ready(f"{gateway_base}/readyz")
        opened_at = now.isoformat().replace("+00:00", "Z")
        status, created = _request(
            f"{oos_base}/v1/agent-console/sessions",
            headers=headers,
            payload={
                "schema_version": 1,
                "session_id": session_id,
                "operator_id": operator_id,
                "agent": {"logical_agent_id": "agent-console", "instance_id": f"proof-{token}"},
                "interaction_mode": "workspace",
                "opened_at": opened_at,
                "idempotency_key": f"session-{token}",
            },
        )
        if status != 201 or created.get("state") != "active":
            raise AgentConsolePlatformError("Agent Console positive session creation failed")
        requested_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        status, invoked = _request(
            f"{oos_base}/v1/agent-console/sessions/{session_id}/invocations",
            headers=headers,
            payload={
                "schema_version": 1,
                "invocation_id": f"invocation-{token}",
                "correlation_id": f"correlation-{token}",
                "idempotency_key": f"invocation-key-{token}",
                "requested_at": requested_at,
                "prompt": "Return one short confirmation that this context is governed.",
                "candidate": {
                    "candidate_id": f"candidate-{token}",
                    "scope": "workspace",
                    "source_authority": "platform-engineering",
                    "source_mode": "synthetic",
                    "source_ref": "platform://agent-console/operating-proof",
                    "source_revision": revisions["platform-engineering"],
                    "captured_at": requested_at,
                    "content": content,
                    "content_digest": "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest(),
                },
                "budget_tokens": 256,
            },
        )
        latest = invoked.get("latest_invocation") or {}
        if (
            status != 200
            or latest.get("state") != "completed"
            or not isinstance((latest.get("result") or {}).get("text"), str)
            or (latest.get("model") or {}).get("profile_id") != policy["model"]["profile_id"]
        ):
            raise AgentConsolePlatformError("Agent Console governed invocation failed")
        audit_status, audit = _request(f"{gateway_base}/v1/audit/events/latest")
        latest_audit = audit.get("latest") or {}
        if (
            audit_status != 200
            or (latest_audit.get("caller_identity") or {}).get("caller_id") != policy["model"]["caller_id"]
            or latest_audit.get("task_kind") != policy["model"]["task_kind"]
            or latest_audit.get("provider_schema_valid") is not True
        ):
            raise AgentConsolePlatformError("Agent Console gateway audit evidence is incomplete")
        denied_status, denied = _request(
            f"{gateway_base}/v1/governed-ai/invoke",
            payload={
                "profile_id": policy["model"]["profile_id"],
                "caller_identity": {
                    "caller_id": "unapproved/agent-console",
                    "caller_repo": "unapproved",
                    "caller_workflow": "agent-console",
                    "decision_or_correlation_id": f"denied-{token}",
                    "requested_profile_id": policy["model"]["profile_id"],
                },
                "operator_identity": {"operator_id": operator_id},
                "task": {
                    "kind": "unapproved_task",
                    "contract_ref": policy["model"]["contract_ref"],
                    "version": policy["model"]["contract_version"],
                },
                "provider_output_schema_ref": "invalid/schema.json",
                "input": {},
            },
        )
        reasons = denied.get("reasons") or []
        if denied_status != 403 or denied.get("policy_decision") != "deny" or "caller-not-allowed" not in reasons:
            raise AgentConsolePlatformError("Agent Console negative admission proof failed")
        closed_status, closed = _request(
            f"{oos_base}/v1/agent-console/sessions/{session_id}/close",
            headers=headers,
            payload={
                "closed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "expected_revision": invoked["revision"],
            },
        )
        if closed_status != 200 or closed.get("state") != "closed":
            raise AgentConsolePlatformError("Agent Console session cleanup failed")

    receipt_root = STATE_ROOT / policy["receipts"]["directory"]
    receipt_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt_root.chmod(0o700)
    receipt_path = receipt_root / policy["receipts"]["operating_filename"]
    receipt = {
        "schema_version": 1,
        "action": "agent-console-operating-verification",
        "outcome": "passed",
        "delivery_ref": policy["activation"]["work_item_ref"],
        "security_gate_id": policy["activation"]["security_gate_id"],
        "composition_id": policy["activation"]["composition_id"],
        "profile_id": resolved["profile_id"],
        "caller_id": policy["model"]["caller_id"],
        "positive": {"session_state": "closed", "invocation_state": "completed", "audit_valid": True},
        "negative": {"http_status": denied_status, "policy_decision": "deny", "reasons": sorted(reasons)},
        "source_revisions": revisions,
        "verified_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt_path.chmod(0o600)
    return receipt_path


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--policy", type=Path, default=POLICY_PATH)
    value.add_argument("action", choices=("validate", "verify-operating"))
    return value


def main() -> int:
    args = parser().parse_args()
    policy = load_policy(args.policy)
    if args.action == "validate":
        resolved = validate_policy(policy)
        print(
            "Agent Console Platform contract valid: "
            f"profile={resolved['profile_id']} composition={policy['activation']['composition_id']}"
        )
        return 0
    receipt = verify_operating(policy)
    print(f"Agent Console operating verification passed; receipt={receipt}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AgentConsolePlatformError as exc:
        print(f"refused: {exc}", file=os.sys.stderr)
        raise SystemExit(2) from exc
