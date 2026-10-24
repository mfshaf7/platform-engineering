#!/usr/bin/env python3
"""Compose, verify, recover, and retire the complete local Console runtime."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import fcntl
import hashlib
import ipaddress
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

import platform_operation_provider as provider
import console_workflow_credentials as workflow_credentials
import console_record_authority as record_authority
import console_session_projection as session_projection
import console_model_management as model_management


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
REPOSITORY_REFRESH_SERVICE = "governance-console-repository-credentials.service"
REPOSITORY_REFRESH_TIMER = "governance-console-repository-credentials.timer"
SECRET_NAME = "governance-console-platform-operation-provider"
SERVICE_NAME = "governance-console-platform-operation-provider"
PROVIDER_PORT = 38491
CONSOLE_CALLER = "governance-operations-console"
CONSOLE_OPERATOR_FAMILIES = (
    "OOS_AGENT_CONSOLE_CALLER_OPERATOR_BINDINGS_JSON",
    "OOS_DELIVERY_WORK_SESSION_CALLER_OPERATOR_BINDINGS_JSON",
    "OOS_PLATFORM_OPERATION_CALLER_OPERATOR_BINDINGS_JSON",
    "OOS_PRODUCT_PUBLICATION_CALLER_OPERATOR_BINDINGS_JSON",
)
OOS_STATE_VOLUME_NAME = "governance-console-platform-operation-state"
OOS_STATE_MOUNT_PATH = "/var/lib/oos/platform-operation"
OOS_STATE_ROOT = STATE_ROOT / "oos-platform-operation"
REPOSITORY_STATE_ROOT = STATE_ROOT / "oos-repository-custody"
REPOSITORY_PROVISIONING_RECEIPT = RECEIPT_ROOT / "repository-provisioning-deliver.json"
REPOSITORY_PROVISIONING_REVOKE_RECEIPT = RECEIPT_ROOT / "repository-provisioning-revoke.json"
REPO_PATH_OVERRIDES: dict[str, Path] = {}
OPERATING_PROOF_LOCK_PATH = STATE_ROOT / "verify-operating.lock"
RECORD_AUTHORITY_ROOT = STATE_ROOT / "record-authority"
INTAKE_OWNER_SOURCE_ROOT = STATE_ROOT / "intake-owner-sources"
INTAKE_OWNER_SOURCE_VOLUME = "intake-owner-source-snapshots"


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


def selected_repo_paths() -> dict[str, Path]:
    selected = {"platform-engineering": persistent_platform_source()}
    selected.update(REPO_PATH_OVERRIDES)
    return selected


def persistent_platform_source() -> Path:
    """Prefer surviving merged source only when it is the identical clean tree."""
    main = WORKSPACE_ROOT / "platform-engineering"
    if main.resolve() == REPO_ROOT.resolve() or not main.is_dir() or not REPO_ROOT.is_dir():
        return REPO_ROOT
    main_tree = run(["git", "-C", str(main), "rev-parse", "HEAD^{tree}"], check=False)
    candidate_tree = run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD^{tree}"], check=False)
    remote_tree = run(["git", "-C", str(main), "rev-parse", "origin/main^{tree}"], check=False)
    branch = run(["git", "-C", str(main), "symbolic-ref", "--short", "HEAD"], check=False)
    if (
        any(result.returncode for result in (main_tree, candidate_tree, remote_tree, branch))
        or not main_tree.stdout.strip()
        or main_tree.stdout.strip() != candidate_tree.stdout.strip()
        or main_tree.stdout.strip() != remote_tree.stdout.strip()
        or branch.stdout.strip() != "main"
        or run(["git", "-C", str(main), "status", "--porcelain"]).stdout.strip()
        or run(["git", "-C", str(REPO_ROOT), "status", "--porcelain"]).stdout.strip()
    ):
        return REPO_ROOT
    return main


def repo_path(name: str) -> Path:
    return selected_repo_paths().get(name, WORKSPACE_ROOT / name)


def git_head(name: str) -> str:
    return run(["git", "-C", str(repo_path(name)), "rev-parse", "HEAD"]).stdout.strip()


def git_tree(name: str) -> str:
    return run(["git", "-C", str(repo_path(name)), "rev-parse", "HEAD^{tree}"]).stdout.strip()


def require_clean_exact_source(name: str, revision: str) -> None:
    path = repo_path(name)
    if not re_full_commit(revision) or not path.is_dir():
        raise RuntimeError(f"{name} is not at the exact reviewed revision")
    if run(["git", "-C", str(path), "status", "--porcelain"]).stdout.strip():
        raise RuntimeError(f"{name} must be clean before complete runtime activation")
    current = git_head(name)
    if current != revision:
        if name not in record_authority.OWNERS:
            raise RuntimeError(f"{name} is not at the exact reviewed revision")
        # Only accepted record-only descendants may advance an owner's primary
        # checkout. All executable/schema/policy source remains exactly pinned.
        branch = run(["git", "-C", str(path), "symbolic-ref", "--short", "HEAD"]).stdout.strip()
        if branch != "main":
            raise RuntimeError(f"{name} data advancement is not on main")
        record_authority.git(path, "merge-base", "--is-ancestor", current, "refs/remotes/origin/main")
        record_authority.admit_record_delta(path, name, revision, current)


def re_full_commit(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


def validate_policy(policy_path: Path = POLICY_PATH) -> dict[str, Any]:
    policy = provider.load_policy(policy_path)
    workflow_credentials.validate_policy(policy)
    model_management.validate(policy)
    if policy.get("record_authority") != {"enabled": True,
        "owner_repos": ["workspace-governance", "workspace-prototype-studio"]}:
        raise RuntimeError("complete runtime canonical record boundary is invalid")
    if policy.get("source_realization") != {"enabled": True, "profile_id": "source-realization-v1",
        "security_review_ref": "docs/reviews/components/2026-10-15-bounded-source-realization-boundary.md"}:
        raise RuntimeError("complete runtime source realization boundary is invalid")
    delivery = policy.get("delivery", {})
    architecture = delivery.get("architecture", {})
    if delivery.get("delivery_id") != "delivery-1313" or delivery.get("work_item_ref") != "openproject://work_packages/1320":
        raise RuntimeError("complete runtime Delivery binding is invalid")
    digest = architecture.get("digest", "")
    if (
        architecture.get("artifact_id") != "architecture-packet:delivery-1313-v1"
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
        "operator_id": provider_policy.get("operator_id"),
        "profile_id": "accepted-idea-delivery",
        "composition_id": "refinement-catalog",
        "subject_ref": "profile:accepted-idea-delivery",
        "security_gate_id": "gate:ai-routing-composed-security",
    }:
        raise RuntimeError("complete runtime Platform-operation boundary is invalid")
    require_operator_policy(policy)
    repository = policy.get("repository_provisioning")
    if not isinstance(repository, dict) or repository.get("enabled") is not True:
        raise RuntimeError("complete runtime repository provisioning is not enabled")
    if (
        repository.get("security_gate_id") != "gate:repository-custody-runtime-activation"
        or repository.get("security_review_ref")
        != "docs/reviews/components/2026-10-15-repository-custody-controlled-activation.md"
    ):
        raise RuntimeError("complete runtime repository provisioning Security binding is invalid")
    for name in ("policy_profile_ref", "credential_binding_ref"):
        reference = repository.get(name)
        if (
            not isinstance(reference, dict)
            or set(reference) != {"uri", "digest"}
            or not isinstance(reference.get("uri"), str)
            or not reference["uri"]
            or not provider.DIGEST.fullmatch(str(reference.get("digest", "")))
        ):
            raise RuntimeError(f"complete runtime repository {name} is invalid")
    identity = repository.get("identity")
    if (
        not isinstance(identity, dict)
        or identity.get("contract") != "security/repository-provisioning-identity.yaml"
        or not isinstance(identity.get("app_id"), int)
        or identity["app_id"] <= 0
        or not isinstance(identity.get("installation_id"), int)
        or identity["installation_id"] <= 0
        or identity.get("organization") != "mfshaf7-workspace"
        or identity.get("runtime_secret_name")
        != "operator-orchestration-service-repository-provisioning-provider"
        or identity.get("runtime_secret_key")
        != "OOS_REPOSITORY_PROVISIONING_INSTALLATION_TOKEN"
    ):
        raise RuntimeError("complete runtime repository provisioning identity is invalid")
    vault = repository.get("vault")
    if (
        not isinstance(vault, dict)
        or vault.get("address") != "http://127.0.0.1:8200"
        or vault.get("namespace") != "vault"
        or vault.get("pod") != "vault-0"
        or vault.get("secret_path")
        != "kv/components/operator-orchestration-service/dev-integration/repository-provisioning-provider"
        or vault.get("secret_property") != "privateKey"
    ):
        raise RuntimeError("complete runtime repository provisioning Vault source is invalid")
    wgcf = repository.get("wgcf")
    if (
        not isinstance(wgcf, dict)
        or wgcf.get("namespace_pattern") != "devint-governance-control-fabric-{operator}"
        or wgcf.get("deployment") != "workspace-governance-control-fabric-api"
        or wgcf.get("service") != "workspace-governance-control-fabric-api"
        or wgcf.get("port") != 8080
        or wgcf.get("caller_id") != "operator-orchestration-service"
    ):
        raise RuntimeError("complete runtime repository WGCF binding is invalid")
    oos = repository.get("oos")
    if (
        not isinstance(oos, dict)
        or oos.get("state_mount_path") != "/var/lib/oos/repository-custody"
        or oos.get("state_volume_name") != "governance-console-repository-custody-state"
    ):
        raise RuntimeError("complete runtime repository OOS state binding is invalid")
    security = policy["security"]
    required_repos = {
        "context-governance-gateway",
        "governance-operations-console",
        "operator-orchestration-service",
        "platform-engineering",
        "workspace-governance",
        "workspace-governance-control-fabric",
        "workspace-prototype-studio",
    }
    if (
        security.get("owner_repo") != "security-architecture"
        or security.get("decision_ref") != "docs/reviews/components/2026-10-24-configurable-ai-routing.yaml"
        or security.get("review_ref") != "docs/reviews/components/2026-10-24-configurable-ai-routing.md"
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


def security_acceptance_anchor(repo: Path, current: str, paths: list[str]) -> str:
    """Bind current decision content, not unrelated generated-index commits.

    Callers still read and validate the decision at clean current origin/main;
    a changed/revoked decision or relevant review advances this exact anchor.
    """
    value = run(["git", "-C", str(repo), "log", "-1", "--format=%H", current,
        "--", *paths]).stdout.strip()
    if not re_full_commit(value):
        raise RuntimeError("Security acceptance source history is unavailable")
    return value


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
        or decision["decision_id"] != "delivery-1313-ai-routing"
        or decision["gate_id"] != security["gate_id"]
        or decision["status"] != "accepted"
        or decision["delivery_id"] != "delivery-1313"
        or decision["work_item_ref"] != "openproject://work_packages/1319"
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
    repository = policy["repository_provisioning"]
    try:
        repository_review = _git_file(
            security_repo,
            security_revision,
            repository["security_review_ref"],
        )
        oos_manifest = json.loads(
            _git_file(
                repo_path("operator-orchestration-service"),
                revisions["operator-orchestration-service"],
                "contracts/repository-custody/manifest.json",
            )
        )
    except (RuntimeError, json.JSONDecodeError):
        raise RuntimeError("the accepted repository-custody activation evidence is unavailable") from None
    authority = oos_manifest.get("authority", {})
    runtime_activation = oos_manifest.get("runtime_activation", {})
    expected_policy_ref = repository["policy_profile_ref"]
    if (
        authority.get("uri") != expected_policy_ref["uri"]
        or f"sha256:{authority.get('sha256', '')}" != expected_policy_ref["digest"]
        or runtime_activation.get("enabled") is not True
        or "provision-new" not in runtime_activation.get("active_capabilities", [])
        or runtime_activation.get("allowed_runtime_profile") != "dev-integration"
    ):
        raise RuntimeError("the repository-custody source activation is stale or incomplete")
    repository_review_tokens = (
        repository["security_gate_id"],
        "- decision: `approved-with-findings`",
    )
    if (
        runtime_activation.get("security_review", {}).get("path") != repository["security_review_ref"]
        or any(token not in repository_review for token in repository_review_tokens)
    ):
        raise RuntimeError("the Repository Custody Security review does not bind the active source")
    identity = repository["identity"]
    contract_path = REPO_ROOT / identity["contract"]
    contract_bytes = contract_path.read_bytes()
    contract = yaml.safe_load(contract_bytes)
    expected_binding = {
        "app_id": identity["app_id"],
        "identity_id": contract["identity"]["id"],
        "contract_digest": f"sha256:{hashlib.sha256(contract_bytes).hexdigest()}",
        "installation_id": identity["installation_id"],
        "organization": identity["organization"].casefold(),
        "permissions": contract["identity"]["required_permissions"],
        "provider_api_base_url": contract["identity"]["api_base_url"],
    }
    if provider.canonical_digest(expected_binding) != repository["credential_binding_ref"]["digest"]:
        raise RuntimeError("the repository provisioning credential binding is stale")
    decision_digest = provider.canonical_digest(decision)
    # The current authoritative content has already passed every gate above.
    # An unrelated owner-record index update must not invalidate that decision.
    acceptance_revision = security_acceptance_anchor(security_repo, security_revision, [
        security["decision_ref"], security["review_ref"], repository["security_review_ref"],
        policy["source_realization"]["security_review_ref"],
    ])
    resolved = json.loads(json.dumps(policy))
    resolved["security"].update({
        "status": "accepted",
        "decision_uri": f"security-architecture://git/{acceptance_revision}/{security['decision_ref']}",
        "decision_digest": decision_digest,
        # The reviewed candidate and a squash merge have distinct commit IDs.
        # The strict clean-tree check above accepts their identical content;
        # runtime readback must bind the actual selected execution revision.
        # Original review provenance remains in reviewed_revisions unchanged.
        "platform_revision": git_head("platform-engineering"),
        "platform_tree": trees["platform-engineering"],
        "reviewed_revisions": revisions,
        "security_revision": acceptance_revision,
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
            "delivery_id": policy["delivery"]["delivery_id"],
            "work_item_ref": policy["delivery"]["work_item_ref"],
            "security_gate_id": policy["security"]["gate_id"],
        },
        "proof_scope": {
            "includes": [
                "complete-console-runtime",
                "authenticated-platform-operation-provider",
                "automatic-session-and-runtime-credential-lifecycle",
                "repository-provisioning-runtime",
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
            "workspace_governance_binding": "reviewed-record-only",
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
        "repository_custody": {
            "policy_profile_ref": policy["repository_provisioning"]["policy_profile_ref"],
            "provisioning_credential_binding_ref": policy["repository_provisioning"]["credential_binding_ref"],
            "wgcf_readiness_enabled": True,
        },
        "prototype_preview": {
            "owner_repo_root": str(RECORD_AUTHORITY_ROOT / "workspace-prototype-studio"),
            "source_revision": revisions["workspace-prototype-studio"],
            "state_root": str(STATE_ROOT / "prototype-preview"),
            "record_authority_freshness_required": True,
        },
        "console_publication": publication_console_binding(policy),
        "receipts": {"directory": "governance-console-complete-runtime/receipts", "maximum_age_seconds": 120},
    }


def publication_console_binding(policy: dict[str, Any]) -> dict[str, str]:
    """Reuse the existing accepted Publication decision; this is not enablement."""
    publication_policy = yaml.safe_load((PRODUCT_ROOT / "product-publication-commissioning-policy.yaml").read_text(encoding="utf-8"))
    decision = publication_policy["product_publication"]["security_decision"]
    if decision.get("approved_target_postures") != ["unlisted", "internal", "archived"]:
        raise RuntimeError("the existing Publication target boundary is not the accepted scope")
    return {
        # The Console obtains current mutable Inventory from its native Registry
        # for each new command; this stable value retains reviewed source binding.
        "authority_revision": policy["security"]["reviewed_revisions"]["workspace-governance"],
        "security_decision_uri": decision["uri"],
        "security_decision_digest": decision["digest"],
        "security_decision_revision": decision["revision"],
    }


def require_publication_owner_bindings(policy: dict[str, Any]) -> dict[str, bool]:
    """Read existing gates and exact decision without modifying either owner."""
    binding = publication_console_binding(policy)
    source = json.loads(_git_file(repo_path("operator-orchestration-service"),
        policy["security"]["reviewed_revisions"]["operator-orchestration-service"], "contracts/product-publication/manifest.json"))
    authority = source.get("security_authority", {})
    if (source.get("runtime_activation") is not True
            or source.get("allowed_target_postures") != ["unlisted", "internal", "archived"]
            or any(authority.get(key) != binding[value] for key, value in (
                ("decision_uri", "security_decision_uri"), ("decision_digest", "security_decision_digest"),
                ("decision_revision", "security_decision_revision")))):
        raise RuntimeError("the exact reviewed OOS Publication source does not accept this decision")
    expected = {
        "OOS_PRODUCT_PUBLICATION_ENABLED": "true",
        "OOS_PRODUCT_PUBLICATION_SECURITY_DECISION_URI": binding["security_decision_uri"],
        "OOS_PRODUCT_PUBLICATION_SECURITY_DECISION_DIGEST": binding["security_decision_digest"],
        "OOS_PRODUCT_PUBLICATION_SECURITY_DECISION_REVISION": binding["security_decision_revision"],
    }
    script = "const expected=" + json.dumps(expected) + ";console.log(JSON.stringify({matched:Object.entries(expected).every(([k,v])=>process.env[k]===v)}));"
    actual = json.loads(run(["k3s", "kubectl", "-n", namespace(policy), "exec",
        f"deployment/{policy['runtime']['oos_deployment']}", "-c", policy["runtime"]["oos_deployment"],
        "--", "node", "-e", script]).stdout)
    wgcf = json.loads(run(["k3s", "kubectl", "-n", f"devint-governance-control-fabric-{operator()}",
        "exec", "deployment/workspace-governance-control-fabric-api", "-c", "api", "--", "python3", "-c",
        "import json,os; print(json.dumps({'enabled':os.environ.get('WGCF_PRODUCT_PUBLICATION_READINESS_ENABLED')=='true'}))"]).stdout)
    if actual != {"matched": True} or wgcf != {"enabled": True}:
        raise RuntimeError("existing Publication owner enablement or exact Security binding is unavailable")
    return {"oos_enabled_and_bound": True, "wgcf_enabled": True}


def require_console_publication_mode(policy: dict[str, Any]) -> dict[str, str]:
    try:
        with urlopen(f"http://127.0.0.1:{policy['runtime']['console_port']}/api/product-portfolio/publications", timeout=15) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, HTTPError, URLError) as exc:
        raise RuntimeError("the Console Publication owner route is unavailable") from exc
    if value != {"mode": "live", "reason_code": None}:
        raise RuntimeError("the Console Publication owner route is not selected; preview is not readiness")
    return {"console_mode": "live"}


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
    if policy["platform_operation_provider"]["operator_id"] != f"operator:{operator()}":
        raise RuntimeError("the selected dev-integration operator does not match the admitted Console principal")


def require_operator_policy(policy: dict[str, Any]) -> str:
    """Compare existing authorities; never alias a role to a source actor."""
    identity = policy["platform_operation_provider"].get("operator_id")
    principals = session_projection.load_policy(PRODUCT_ROOT / "session-projection-policy.yaml").principals
    matches = [value for value in principals.values() if value.reference == identity]
    if len(matches) != 1 or matches[0].kind != "human" or identity != f"operator:{matches[0].operator}":
        raise RuntimeError("Console principal and native source operator bindings disagree")
    for filename in ("product-publication-commissioning-policy.yaml",
                     "proposal-target-commissioning-policy.yaml",
                     "repository-catalog-commissioning-policy.yaml"):
        other = yaml.safe_load((PRODUCT_ROOT / filename).read_text(encoding="utf-8"))
        if other.get("session", {}).get("operator_id") != identity:
            raise RuntimeError(f"Console operator binding disagrees in {filename}")
    return identity


def require_console_operator_bindings(policy: dict[str, Any]) -> dict[str, Any]:
    identity = require_operator_policy(policy)
    # Inspect only the closed binding maps inside the existing process. Tokens,
    # environment dumps and unrelated values never leave the workload.
    script = "const names=" + json.dumps(CONSOLE_OPERATOR_FAMILIES) + ";const caller=" + json.dumps(CONSOLE_CALLER) + ";const expected=" + json.dumps(identity) + ";const checks=Object.fromEntries(names.map(n=>{try{return [n,JSON.parse(process.env[n]||'{}')[caller]===expected]}catch{return [n,false]}}));console.log(JSON.stringify(checks));"
    result = run(["k3s", "kubectl", "-n", namespace(policy), "exec",
                  f"deployment/{policy['runtime']['oos_deployment']}", "-c",
                  policy["runtime"]["oos_deployment"], "--", "node", "-e", script])
    try:
        checks = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        raise RuntimeError("Console operator binding readback is unavailable") from None
    if not isinstance(checks, dict) or set(checks) != set(CONSOLE_OPERATOR_FAMILIES) or any(value is not True for value in checks.values()):
        raise RuntimeError("the live Console workflow operator bindings disagree")
    return {"caller_id": CONSOLE_CALLER, "operator_id": identity, "families": checks, "consistent": True}


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
        str(repo_path("platform-engineering") / "scripts" / "dev_integration.py"),
        action,
        "--composition",
        policy["platform_operation_provider"]["composition_id"],
        "--workspace-root",
        str(WORKSPACE_ROOT),
    ]
    for name, path in sorted(selected_repo_paths().items()):
        command.extend(["--repo-path", f"{name}={path}"])
    return command


def composition_supervisor_unit(policy: dict[str, Any]) -> str:
    account = re.sub(r"[^a-z0-9]+", "-", operator().lower()).strip("-")
    return f"workspace-devint-{policy['runtime']['session_profile']}-{account}.service"


def inside_composition_supervisor(policy: dict[str, Any]) -> bool:
    if os.environ.get("DEVINT_AUTO_RESUME") != "1":
        return False
    try:
        groups = Path("/proc/self/cgroup").read_text().splitlines()
    except OSError:
        return False
    return any(composition_supervisor_unit(policy) in line.split(":")[-1].split("/") for line in groups)


def require_retained_supervision() -> str:
    try:
        groups = Path("/proc/self/cgroup").read_text().splitlines()
        units = [part for line in groups for part in line.split(":")[-1].split("/")
            if part.endswith(".service") and re.fullmatch(r"[A-Za-z0-9_.@-]+", part)]
        unit = units[-1]
        value = run(["systemctl", "--user", "show", unit, "-p", "Type", "-p", "RemainAfterExit"]).stdout
        fields = dict(line.split("=", 1) for line in value.splitlines() if "=" in line)
        if fields.get("Type") != "oneshot" or fields.get("RemainAfterExit") != "yes":
            raise ValueError()
        return unit
    except (OSError, IndexError, ValueError):
        raise RuntimeError("runtime proof requires a retained oneshot supervisor; detached owner helpers must survive controller exit") from None


def write_composition_supervisor(policy: dict[str, Any]) -> None:
    # Reuse the admitted profile unit. Its product-owned drop-in survives a
    # generic profile-unit refresh and adds no new service or startup authority.
    scripts = repo_path("platform-engineering") / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        from dev_integration_auto_resume import build_auto_resume_spec, enable_auto_resume, _systemd_quote, _systemd_path_value
    finally:
        sys.path.pop(0)
    profile_path = repo_path("operator-orchestration-service") / "dev-integration/profiles/accepted-idea-delivery/profile.yaml"
    profile = yaml.safe_load(profile_path.read_text())
    spec = build_auto_resume_spec(operator=operator(), platform_runner=scripts / "dev_integration.py",
        profile=profile, profile_id=policy["runtime"]["session_profile"],
        composition_id=policy["platform_operation_provider"]["composition_id"],
        repo_paths=selected_repo_paths(), workspace_root=WORKSPACE_ROOT)
    if spec.policy != "operator-login" or spec.unit_name != composition_supervisor_unit(policy):
        raise RuntimeError("the existing composition supervisor is not admitted")
    enable_auto_resume(spec)
    directory = spec.unit_path.parent / f"{spec.unit_name}.d"
    ensure_private(directory)
    command = [sys.executable, str(PRODUCT_ROOT / "scripts/console_complete_runtime.py"), "activate"]
    for name, path in sorted(selected_repo_paths().items()):
        command.extend(["--repo-path", f"{name}={path}"])
    content = "[Service]\nWorkingDirectory=" + _systemd_path_value(repo_path("platform-engineering")) + "\nExecStart=\nExecStart="
    content += " ".join(_systemd_quote(value) for value in command) + "\n"
    target = directory / "console-runtime.conf"
    if target.is_symlink():
        raise RuntimeError("the composition supervisor drop-in is unsafe")
    target.write_text(content)
    target.chmod(0o600)
    run(["systemctl", "--user", "daemon-reload"])


def cross_domain_command(action: str) -> list[str]:
    command = [
        sys.executable,
        str(PRODUCT_ROOT / "scripts" / "console_cross_domain_activation.py"),
        "--policy",
        str(RESOLVED_ACTIVATION_POLICY_PATH),
        action,
    ]
    for name, path in sorted(selected_repo_paths().items()):
        command.extend(["--repo-path", f"{name}={path}"])
    return command


def dev_integration_session_manifest(policy: dict[str, Any]) -> Path:
    return (
        WORKSPACE_ROOT
        / ".dev-integration"
        / policy["runtime"]["session_profile"]
        / operator()
        / "current-session.yaml"
    )


def vault_token() -> str:
    value = os.environ.get("VAULT_TOKEN", "").strip()
    if value:
        return value
    path = Path.home() / ".vault-token"
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_uid != os.geteuid()
        or stat.S_IMODE(path.stat().st_mode) & 0o077
    ):
        raise RuntimeError("the operator-private Vault token is unavailable or unsafe")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise RuntimeError("the operator-private Vault token is empty")
    return value


def repository_provisioning_private_key(policy: dict[str, Any]) -> Path:
    return vault_private_key(policy["repository_provisioning"]["vault"])


def vault_private_key(vault: dict[str, Any]) -> Path:
    ensure_private(STATE_ROOT)
    ensure_private(PRIVATE_ROOT)
    script = (
        'IFS= read -r VAULT_TOKEN; export VAULT_TOKEN; '
        'export VAULT_ADDR="$1"; vault kv get -field="$2" "$3"'
    )
    result = run(
        [
            "k3s", "kubectl", "-n", vault["namespace"], "exec", "-i",
            vault["pod"], "--", "sh", "-c", script, "vault-read",
            vault["address"], vault["secret_property"], vault["secret_path"],
        ],
        input_value=vault_token() + "\n",
    )
    private_key = result.stdout.strip()
    if "-----BEGIN" not in private_key or "PRIVATE KEY-----" not in private_key:
        raise RuntimeError("the repository provisioning private key is invalid")
    descriptor, raw_path = tempfile.mkstemp(
        prefix="repository-provisioning-",
        suffix=".pem",
        dir=PRIVATE_ROOT,
        text=True,
    )
    path = Path(raw_path)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(private_key + "\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def workflow_credential_manager(policy: dict[str, Any]) -> workflow_credentials.Credentials:
    return workflow_credentials.Credentials(
        repo_root=REPO_ROOT, workspace_root=WORKSPACE_ROOT,
        session_manifest=dev_integration_session_manifest(policy), run=run,
        private_key=vault_private_key,
        readiness_revision=policy["security"]["reviewed_revisions"].get("workspace-governance-control-fabric"),
    )


def repository_identity_command(
    policy: dict[str, Any],
    action: str,
    receipt_path: Path,
    *,
    private_key_path: Path | None = None,
) -> list[str]:
    identity = policy["repository_provisioning"]["identity"]
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "repository_provisioning_identity.py"),
        "--contract", str(REPO_ROOT / identity["contract"]),
        action,
        "--app-id", str(identity["app_id"]),
        "--installation-id", str(identity["installation_id"]),
        "--organization", identity["organization"],
        "--receipt", str(receipt_path),
    ]
    if private_key_path is not None:
        command.extend(["--private-key-file", str(private_key_path)])
    if action in {"deliver", "revoke"}:
        command.extend([
            "--session-manifest", str(dev_integration_session_manifest(policy)),
            "--workspace-root", str(WORKSPACE_ROOT),
        ])
    return command


def deliver_repository_provisioning_identity(policy: dict[str, Any]) -> dict[str, Any]:
    ensure_private(RECEIPT_ROOT)
    private_key = repository_provisioning_private_key(policy)
    try:
        run(repository_identity_command(
            policy,
            "deliver",
            REPOSITORY_PROVISIONING_RECEIPT,
            private_key_path=private_key,
        ))
    finally:
        private_key.unlink(missing_ok=True)
    try:
        value = json.loads(REPOSITORY_PROVISIONING_RECEIPT.read_text(encoding="utf-8"))
        expires_at = datetime.fromisoformat(value["token_expires_at"].replace("Z", "+00:00"))
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        raise RuntimeError("the repository provisioning delivery receipt is invalid") from None
    repository = policy["repository_provisioning"]
    identity = repository["identity"]
    if (
        value.get("action") != "deliver"
        or value.get("outcome") != "delivered"
        or value.get("app_id") != identity["app_id"]
        or value.get("installation_id") != identity["installation_id"]
        or value.get("organization") != identity["organization"]
        or value.get("credential_binding_digest")
        != repository["credential_binding_ref"]["digest"]
        or value.get("secret_values_embedded") is not False
        or (expires_at - datetime.now(UTC)).total_seconds() < 300
    ):
        raise RuntimeError("the repository provisioning delivery receipt is stale or mismatched")
    return value


def revoke_repository_provisioning_identity(policy: dict[str, Any]) -> None:
    identity = policy["repository_provisioning"]["identity"]
    ns = namespace(policy)
    if run(
        ["k3s", "kubectl", "-n", ns, "get", f"secret/{identity['runtime_secret_name']}"],
        check=False,
    ).returncode:
        return
    ensure_private(RECEIPT_ROOT)
    run(repository_identity_command(
        policy,
        "revoke",
        REPOSITORY_PROVISIONING_REVOKE_RECEIPT,
    ))


def write_repository_refresh_units() -> None:
    """Reuse the local runtime's systemd lifecycle for purpose-bound renewal."""
    UNIT_ROOT.mkdir(parents=True, exist_ok=True)
    runtime_repo = repo_path("platform-engineering")
    python = shutil.which("python3")
    if not python:
        raise RuntimeError("python3 is unavailable for repository credential renewal")
    service = f"""[Unit]
Description=Renew Governance Console admitted workflow credentials
After=network.target
ConditionPathExists={STATE_ROOT / 'active.json'}

[Service]
Type=oneshot
WorkingDirectory={runtime_repo}
ExecStart={python} {runtime_repo / 'products/governance-operations-console/scripts/console_complete_runtime.py'} refresh-credentials
TimeoutStartSec=900
NoNewPrivileges=true
PrivateTmp=true
"""
    timer = f"""[Unit]
Description=Maintain Governance Console admitted workflow credentials

[Timer]
OnActiveSec=60s
OnUnitActiveSec=60s
Unit={REPOSITORY_REFRESH_SERVICE}

[Install]
WantedBy=timers.target
"""
    (UNIT_ROOT / REPOSITORY_REFRESH_SERVICE).write_text(service, encoding="utf-8")
    (UNIT_ROOT / REPOSITORY_REFRESH_TIMER).write_text(timer, encoding="utf-8")
    run(["systemctl", "--user", "daemon-reload"])
    run(["systemctl", "--user", "enable", "--now", REPOSITORY_REFRESH_TIMER])


def refresh_repository_credentials(policy: dict[str, Any], *, force: bool = False) -> Path:
    policy, activation = resolve_security_decision(policy)
    require_materialized_policy(policy, activation)
    require_activation_allowed(policy)
    if model_management.enabled(policy):
        model_management.renew_account_lease(state_root=STATE_ROOT, run=run)
    try:
        marker = json.loads((STATE_ROOT / "active.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise RuntimeError("repository renewal requires the active reviewed runtime") from None
    if (
        not isinstance(marker, dict)
        or marker.get("security_decision_digest") != policy["security"]["decision_digest"]
        or marker.get("platform_tree") != policy["security"]["platform_tree"]
    ):
        raise RuntimeError("repository renewal runtime binding is stale")
    record_failure = False
    try:
        records = refresh_record_authorities(policy)
    except record_authority.RecordAuthorityError:
        # A data/provider failure withholds fresh record authority, but must not
        # silently prevent the existing purpose-bound credential renewal.
        records = {"status": "unavailable"}
        record_failure = True
    try:
        delivered = json.loads(REPOSITORY_PROVISIONING_RECEIPT.read_text(encoding="utf-8"))
        expires_at = datetime.fromisoformat(delivered["token_expires_at"].replace("Z", "+00:00"))
        fresh = (
            delivered.get("credential_binding_digest")
            == policy["repository_provisioning"]["credential_binding_ref"]["digest"]
            and (expires_at - datetime.now(UTC)).total_seconds() > 1200
        )
    except (OSError, KeyError, ValueError, TypeError):
        fresh = False
    # Delivery remains the existing exact-App, exact-installation Platform path.
    refreshed = force or not fresh
    if refreshed:
        delivered = deliver_repository_provisioning_identity(policy)
    # A stable, non-secret delivery version makes consumption retryable after
    # a crash between Secret replacement and rollout, without rolling on every tick.
    workflows = workflow_credential_manager(policy).renew(force=force, extra_annotations={
        "workspace-governance/repository-token-expires-at": delivered["token_expires_at"],
    })
    repository_provisioning_status(policy)
    result = receipt("refresh-credentials", policy, {
        "refreshed": refreshed, "credential_current": True, "workflow_credentials": workflows,
        "record_authority": records,
    })
    if record_failure:
        raise RuntimeError("canonical record refresh failed; owner writes are withheld; credentials remain maintained")
    return result


def refresh_record_authorities(policy: dict[str, Any]) -> dict[str, Any]:
    revisions = policy["security"]["reviewed_revisions"]
    invalidated = False
    def before_change():
        nonlocal invalidated
        if invalidated:
            return
        # Preserve group-wide denial before any actual source change, not on
        # every unchanged timer tick. A fresh checkpoint is not a stale cache.
        for owner in sorted(record_authority.OWNERS):
            record_authority.invalidate_snapshot(RECORD_AUTHORITY_ROOT, owner)
        invalidated = True
    try:
        values = {owner: record_authority.refresh_snapshot(RECORD_AUTHORITY_ROOT,
            repo_path(owner), owner, revisions[owner], before_change=before_change)
            for owner in sorted(record_authority.OWNERS)}
        # A later owner change may have invalidated an already refreshed,
        # unchanged peer. Re-observe that peer before returning group readiness.
        for owner in sorted(record_authority.OWNERS):
            if not (RECORD_AUTHORITY_ROOT / owner / ".git" / record_authority.CHECKPOINT).is_file():
                values[owner] = record_authority.refresh_snapshot(RECORD_AUTHORITY_ROOT,
                    repo_path(owner), owner, revisions[owner], before_change=before_change)
        owner_sources = record_authority.refresh_intake_owner_sources(
            RECORD_AUTHORITY_ROOT, WORKSPACE_ROOT, revisions["workspace-governance"])
    except Exception:
        for owner in sorted(record_authority.OWNERS):
            record_authority.invalidate_snapshot(RECORD_AUTHORITY_ROOT, owner)
        raise record_authority.RecordAuthorityError("canonical record refresh failed; restore the approved owner source") from None
    return {"status": "current", "owners": values, "physical_owner_sources": owner_sources}


def record_authority_status(policy: dict[str, Any]) -> dict[str, Any]:
    return {"status": "current", "owners": {owner: record_authority.snapshot_status(
        RECORD_AUTHORITY_ROOT, owner, policy["security"]["reviewed_revisions"][owner])
        for owner in sorted(record_authority.OWNERS)}}


def apply_record_authority_binding(policy: dict[str, Any], *, enabled: bool = True) -> None:
    """Compose private data mounts without changing owner execution-source roots."""
    studio = str(RECORD_AUTHORITY_ROOT / "workspace-prototype-studio" if enabled else repo_path("workspace-prototype-studio"))
    governance = str(RECORD_AUTHORITY_ROOT / "workspace-governance" if enabled else repo_path("workspace-governance"))
    flag = "true" if enabled else "false"
    oos_mounts = {
        "workspace-governance-source": (governance, "/sources/workspace-governance"),
        "proposal-target-application-authority": (studio, "/var/lib/oos/proposal-target-application/authority"),
        "prototype-landing-authority": (studio, "/var/lib/oos/prototype-landing/authority"),
        "prototype-maturity-authority": (studio, "/var/lib/oos/prototype-maturity/authority"),
        "prototype-closure-authority": (studio, "/var/lib/oos/prototype-closure/authority"),
    }
    wgcf = policy["repository_provisioning"]["wgcf"]
    for ns, deployment, container, mounts, environment in [
        (namespace(policy), policy["runtime"]["oos_deployment"], policy["runtime"]["oos_deployment"], oos_mounts,
         {"OOS_RECORD_AUTHORITY_FRESHNESS_REQUIRED": flag, "OOS_SOURCE_REALIZATION_ENABLED": flag,
          "OOS_SOURCE_REALIZATION_PROFILE_ID": policy["source_realization"]["profile_id"]}),
        (wgcf["namespace_pattern"].replace("{operator}", operator()), wgcf["deployment"], "api",
         {"workspace-governance-source": (governance, "/sources/workspace-governance"),
          "prototype-studio-source": (studio, "/sources/workspace-prototype-studio")},
         {"WGCF_RECORD_AUTHORITY_FRESHNESS_REQUIRED": flag}),
    ]:
        if not enabled and run(["k3s", "kubectl", "-n", ns, "get", f"deployment/{deployment}", "-o", "name"], check=False).returncode:
            continue
        patch = {"spec": {"template": {"spec": {
            "containers": [{"name": container,
                "volumeMounts": [{"name": name, "mountPath": value[1], "readOnly": True} for name, value in mounts.items()],
                "env": [{"name": name, "value": value} for name, value in environment.items()]}],
            "volumes": [{"name": name, "hostPath": {"path": value[0], "type": "Directory"}} for name, value in mounts.items()],
        }}}}
        if container == "api":
            # One fixed, read-only parent exposes only sanitized committed-source
            # clones. More-specific reviewed WG/Studio/Console mounts stay intact.
            spec = patch["spec"]["template"]["spec"]
            if enabled:
                spec["volumes"].append({"name": INTAKE_OWNER_SOURCE_VOLUME,
                    "hostPath": {"path": str(INTAKE_OWNER_SOURCE_ROOT), "type": "Directory"}})
                spec["containers"][0]["volumeMounts"].append({"name": INTAKE_OWNER_SOURCE_VOLUME,
                    "mountPath": "/sources", "readOnly": True})
            else:
                spec["volumes"].append({"name": INTAKE_OWNER_SOURCE_VOLUME, "$patch": "delete"})
                spec["containers"][0]["volumeMounts"].append({"name": INTAKE_OWNER_SOURCE_VOLUME,
                    "mountPath": "/sources", "$patch": "delete"})
        run(["k3s", "kubectl", "-n", ns, "patch", f"deployment/{deployment}",
            "--type=strategic", "--patch", json.dumps(patch, separators=(",", ":"))])
        run(["k3s", "kubectl", "-n", ns, "rollout", "status", f"deployment/{deployment}", "--timeout=300s"])


def record_binding_status(policy: dict[str, Any]) -> dict[str, Any]:
    """Observe actual consumed roots/flags, not only producer checkpoint files."""
    records = record_authority_status(policy)
    wgcf = policy["repository_provisioning"]["wgcf"]
    targets = [
        (namespace(policy), policy["runtime"]["oos_deployment"], "OOS_RECORD_AUTHORITY_FRESHNESS_REQUIRED", "OOS_SOURCE_REALIZATION_ENABLED"),
        (wgcf["namespace_pattern"].replace("{operator}", operator()), wgcf["deployment"], "WGCF_RECORD_AUTHORITY_FRESHNESS_REQUIRED", None),
    ]
    for ns, name, freshness, realization in targets:
        value = json.loads(run(["k3s", "kubectl", "-n", ns, "get", f"deployment/{name}", "-o", "json"]).stdout)
        pod = value["spec"]["template"]["spec"]
        expected_container = name if freshness.startswith("OOS_") else "api"
        container = next((item for item in pod["containers"] if item["name"] == expected_container), None)
        if not isinstance(container, dict):
            raise RuntimeError("canonical record owner container is unavailable")
        environment = {item["name"]: item.get("value") for item in container.get("env", [])}
        if environment.get(freshness) != "true" or realization and environment.get(realization) != "true":
            raise RuntimeError("canonical record or realization runtime guard is not active")
        expected = {"workspace-governance-source": ("workspace-governance", "/sources/workspace-governance")}
        if realization:
            expected.update({f"{family}-authority": ("workspace-prototype-studio", f"/var/lib/oos/{family}/authority")
                for family in ("proposal-target-application", "prototype-landing", "prototype-maturity", "prototype-closure")})
            if environment.get("OOS_SOURCE_REALIZATION_PROFILE_ID") != "source-realization-v1":
                raise RuntimeError("source realization is not bound to the commissioned profile")
        else:
            expected["prototype-studio-source"] = ("workspace-prototype-studio", "/sources/workspace-prototype-studio")
        mounts = {item["name"]: item for item in container.get("volumeMounts", [])}
        volumes = {item["name"]: item for item in pod.get("volumes", [])}
        for volume_name, (owner, mount_path) in expected.items():
            if (volumes.get(volume_name, {}).get("hostPath", {}).get("path") != str(RECORD_AUTHORITY_ROOT / owner)
                or volumes.get(volume_name, {}).get("hostPath", {}).get("type") != "Directory"
                or mounts.get(volume_name, {}).get("mountPath") != mount_path
                or mounts.get(volume_name, {}).get("readOnly") is not True
                or mounts.get(volume_name, {}).get("subPath")
                or mounts.get(volume_name, {}).get("subPathExpr")):
                raise RuntimeError("canonical record runtime mount is missing, swapped or not read-only")
        if not realization:
            volume = volumes.get(INTAKE_OWNER_SOURCE_VOLUME, {})
            mount = mounts.get(INTAKE_OWNER_SOURCE_VOLUME, {})
            if (volume.get("hostPath") != {"path": str(INTAKE_OWNER_SOURCE_ROOT), "type": "Directory"}
                or mount.get("mountPath") != "/sources" or mount.get("readOnly") is not True
                or mount.get("subPath") or mount.get("subPathExpr")):
                raise RuntimeError("physical owner source snapshots are missing, swapped or writable")
        replicas = value["spec"].get("replicas", 1)
        state = value.get("status", {})
        if (not replicas or state.get("observedGeneration") != value.get("metadata", {}).get("generation")
            or state.get("updatedReplicas") != replicas or state.get("availableReplicas") != replicas):
            raise RuntimeError("canonical record owner has not consumed the current deployment")
    return records


def require_source_realization_profile(policy: dict[str, Any]) -> dict[str, Any]:
    script = """const url=new URL('/readyz',process.env.GOVERNED_AI_GATEWAY_BASE_URL);
const response=await fetch(url,{signal:AbortSignal.timeout(15000)});
const body=await response.json();const p=body.profiles?.['source-realization-v1'];
if(!response.ok||p?.status!=='active'||p.activation_allowed!==true||p.activation_eligible!==true||p.ready!==true||JSON.stringify(p.task_kinds)!==JSON.stringify(['source_realization']))process.exit(1);
console.log(JSON.stringify({profile_id:'source-realization-v1',status:p.status,ready:p.ready,task_kinds:p.task_kinds}));"""
    value = json.loads(run(["k3s", "kubectl", "-n", namespace(policy), "exec",
        f"deployment/{policy['runtime']['oos_deployment']}", "--", "node", "--input-type=module", "-e", script]).stdout)
    if value != {"profile_id": "source-realization-v1", "status": "active", "ready": True, "task_kinds": ["source_realization"]}:
        raise RuntimeError("the actual governed source realization profile is unavailable")
    return value


def require_console_primary_records(policy: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for owner, route, key in (("prototype", "/api/prototypes/records", "readModel"), ("delivery", "/api/delivery/workspace", None)):
        try:
            with urlopen(f"http://127.0.0.1:{policy['runtime']['console_port']}{route}", timeout=90) as response:
                raw = response.read(5 * 1024 * 1024 + 1)
                if len(raw) > 5 * 1024 * 1024:
                    raise ValueError()
                value = json.loads(raw)
            projection = value["projection"]
            model = projection[key] if key else projection
            records = model["records" if key else "packages"]
            if value.get("mode") != "live" or not isinstance(records, list):
                raise ValueError()
            counts[owner] = len(records)
        except (OSError, ValueError, KeyError, TypeError, HTTPError, URLError):
            raise RuntimeError(f"the Console {owner} primary canonical read is unavailable; fixtures are not readiness") from None
    return counts


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


def provider_service_path() -> str:
    # User-installed issuer tools must resolve in the service as well as the
    # operator shell. Never inherit arbitrary shell/manager PATH entries.
    return ":".join((str(Path.home() / ".local/bin"), "/usr/local/sbin",
                     "/usr/local/bin", "/usr/sbin", "/usr/bin", "/sbin", "/bin"))


def require_provider_tools() -> None:
    path = provider_service_path()
    missing = [name for name in ("vault", "openssl", "git", "k3s", "docker")
               if not shutil.which(name, path=path)]
    if missing:
        raise RuntimeError("Platform provider required tools unavailable: " + ", ".join(missing))


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
    runtime_repo = repo_path("platform-engineering")
    unit = f"""[Unit]
Description=Governance Console Platform operation provider
After=network.target k3s.service

[Service]
WorkingDirectory={runtime_repo}
EnvironmentFile={env_path}
Environment=PATH={provider_service_path()}
Environment=VAULT_ADDR=http://127.0.0.1:32200
Environment=XDG_RUNTIME_DIR=%t
ExecStart={python} {runtime_repo / 'products' / 'governance-operations-console' / 'scripts' / 'platform_operation_provider.py'} --policy {RESOLVED_POLICY_PATH} --state-root {state} serve --listen-host {gateway} --listen-port {policy['runtime']['provider_port']}
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
    ensure_private(OOS_STATE_ROOT)
    ensure_private(REPOSITORY_STATE_ROOT)
    repository = policy["repository_provisioning"]
    repository_wgcf = repository["wgcf"]
    repository_oos = repository["oos"]
    repository_identity = repository["identity"]
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
        "OOS_PLATFORM_OPERATION_STATE_ROOT": OOS_STATE_MOUNT_PATH,
    }
    # Publication is already commissioned independently. Rebind its existing
    # Console actor without enabling a workflow or changing any other caller.
    current = run(["k3s", "kubectl", "-n", ns, "exec",
        f"deployment/{runtime['oos_deployment']}", "-c", runtime["oos_deployment"],
        "--", "node", "-e",
        "const k='OOS_PRODUCT_PUBLICATION_CALLER_OPERATOR_BINDINGS_JSON';const v=process.env[k];console.log(JSON.stringify({enabled:process.env.OOS_PRODUCT_PUBLICATION_ENABLED==='true',bindings:v?JSON.parse(v):null}));"])
    try:
        publication = json.loads(current.stdout)
    except (json.JSONDecodeError, TypeError):
        raise RuntimeError("existing Publication operator binding is unavailable") from None
    if publication.get("enabled") is True:
        bindings = publication.get("bindings")
        if not isinstance(bindings, dict) or CONSOLE_CALLER not in bindings:
            raise RuntimeError("the commissioned Publication Console caller binding is missing")
        bindings[CONSOLE_CALLER] = policy["platform_operation_provider"]["operator_id"]
        secret_values["OOS_PRODUCT_PUBLICATION_CALLER_OPERATOR_BINDINGS_JSON"] = json.dumps(bindings, separators=(",", ":"))
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
    state_patch = {
        "spec": {"template": {"spec": {
            "containers": [{
                "name": runtime["oos_deployment"],
                "volumeMounts": [{
                    "name": OOS_STATE_VOLUME_NAME,
                    "mountPath": OOS_STATE_MOUNT_PATH,
                }, {
                    "name": repository_oos["state_volume_name"],
                    "mountPath": repository_oos["state_mount_path"],
                }],
            }],
            "volumes": [{
                "name": OOS_STATE_VOLUME_NAME,
                "hostPath": {"path": str(OOS_STATE_ROOT), "type": "Directory"},
            }, {
                "name": repository_oos["state_volume_name"],
                "hostPath": {"path": str(REPOSITORY_STATE_ROOT), "type": "Directory"},
            }],
        }}},
    }
    run([
        "k3s", "kubectl", "-n", ns, "patch",
        f"deployment/{runtime['oos_deployment']}", "--type=strategic",
        "--patch", json.dumps(state_patch, separators=(",", ":")),
    ])
    run([
        "k3s", "kubectl", "-n", ns, "set", "env",
        f"deployment/{runtime['oos_deployment']}", f"--from=secret/{SECRET_NAME}",
    ])
    run([
        "k3s", "kubectl", "-n", ns, "set", "env",
        f"deployment/{runtime['oos_deployment']}",
        "OOS_REPOSITORY_CUSTODY_ENABLED=true",
        f"OOS_REPOSITORY_CUSTODY_STATE_ROOT={repository_oos['state_mount_path']}",
        (
            "WGCF_REPOSITORY_CUSTODY_BASE_URL="
            f"http://{repository_wgcf['service']}."
            f"{repository_wgcf['namespace_pattern'].replace('{operator}', operator())}:"
            f"{repository_wgcf['port']}"
        ),
        f"WGCF_REPOSITORY_CUSTODY_CALLER_ID={repository_wgcf['caller_id']}",
    ])
    run([
        "k3s", "kubectl", "-n", ns, "set", "env",
        f"deployment/{runtime['oos_deployment']}",
        f"--from=secret/{repository_identity['runtime_secret_name']}",
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


def require_current_provider(policy: dict[str, Any]) -> dict[str, Any]:
    catalog = provider_catalog(policy, credential())
    expected = policy["security"]["platform_revision"]
    subjects = catalog.get("subjects", [])
    if not isinstance(subjects, list):
        raise RuntimeError("Platform provider subjects are malformed")
    matching = [item for item in subjects if isinstance(item, dict)
                and item.get("ref") == policy["platform_operation_provider"]["subject_ref"]]
    capabilities = matching[0].get("capabilities", []) if len(matching) == 1 else []
    if not isinstance(capabilities, list):
        raise RuntimeError("Platform provider capabilities are malformed")
    if (catalog.get("source_version") != expected or len(matching) != 1
        or matching[0].get("source_version") != expected
        or len(capabilities) != len(provider.ALLOWED_ACTIONS)
        or any(not isinstance(item, dict) for item in capabilities)
        or any(not isinstance(item.get("action"), str) for item in capabilities)
        or {item.get("action") for item in capabilities} != provider.ALLOWED_ACTIONS
        or any(item.get("available") is not True for item in capabilities)):
        raise RuntimeError("Platform provider has not loaded the accepted source and active capabilities")
    return catalog


def refresh_stale_provider(policy: dict[str, Any]) -> None:
    try:
        require_current_provider(policy)
        return  # Same-source provider callbacks must not restart their owner.
    except RuntimeError:
        pass
    run(["systemctl", "--user", "restart", UNIT_NAME])
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            require_current_provider(policy)
            return
        except RuntimeError:
            time.sleep(0.25)
    raise RuntimeError("Platform provider did not load the accepted composition after bounded refresh")


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


def repository_provisioning_status(policy: dict[str, Any]) -> dict[str, Any]:
    repository = policy["repository_provisioning"]
    identity = repository["identity"]
    repository_oos = repository["oos"]
    repository_wgcf = repository["wgcf"]
    ns = namespace(policy)
    secret_result = run([
        "k3s", "kubectl", "-n", ns, "get",
        f"secret/{identity['runtime_secret_name']}", "-o", "json",
    ])
    try:
        secret = json.loads(secret_result.stdout)
        annotations = secret["metadata"]["annotations"]
        expires_at = datetime.fromisoformat(
            annotations["workspace-governance/token-expires-at"].replace("Z", "+00:00")
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise RuntimeError("the repository provisioning runtime credential is invalid") from None
    secret.pop("data", None)
    if (
        annotations.get("workspace-governance/credential-binding-digest")
        != repository["credential_binding_ref"]["digest"]
        or annotations.get("workspace-governance/provider-organization")
        != identity["organization"]
        or annotations.get("workspace-governance/dev-integration-profile")
        != policy["runtime"]["session_profile"]
        or (expires_at - datetime.now(UTC)).total_seconds() < 300
    ):
        raise RuntimeError("the repository provisioning runtime credential is stale or mismatched")

    deployment = json.loads(run([
        "k3s", "kubectl", "-n", ns, "get",
        f"deployment/{policy['runtime']['oos_deployment']}", "-o", "json",
    ]).stdout)
    pod = deployment.get("spec", {}).get("template", {}).get("spec", {})
    containers = pod.get("containers", [])
    container = next(
        (item for item in containers if item.get("name") == policy["runtime"]["oos_deployment"]),
        None,
    )
    if not isinstance(container, dict):
        raise RuntimeError("the OOS repository-custody container binding is unavailable")
    environment = {item.get("name"): item for item in container.get("env", [])}
    token_binding = environment.get(identity["runtime_secret_key"], {}).get("valueFrom", {}).get("secretKeyRef", {})
    expected_plain = {
        "OOS_REPOSITORY_CUSTODY_ENABLED": "true",
        "OOS_REPOSITORY_CUSTODY_STATE_ROOT": repository_oos["state_mount_path"],
        "WGCF_REPOSITORY_CUSTODY_CALLER_ID": repository_wgcf["caller_id"],
        "WGCF_REPOSITORY_CUSTODY_BASE_URL": (
            f"http://{repository_wgcf['service']}."
            f"{repository_wgcf['namespace_pattern'].replace('{operator}', operator())}:"
            f"{repository_wgcf['port']}"
        ),
    }
    if (
        any(environment.get(name, {}).get("value") != value for name, value in expected_plain.items())
        or token_binding.get("name") != identity["runtime_secret_name"]
        or token_binding.get("key") != identity["runtime_secret_key"]
    ):
        raise RuntimeError("the OOS repository-custody environment binding is incomplete")
    mounts = {item.get("name"): item for item in container.get("volumeMounts", [])}
    volumes = {item.get("name"): item for item in pod.get("volumes", [])}
    state_name = repository_oos["state_volume_name"]
    if (
        mounts.get(state_name, {}).get("mountPath") != repository_oos["state_mount_path"]
        or volumes.get(state_name, {}).get("hostPath", {}).get("path")
        != str(REPOSITORY_STATE_ROOT)
    ):
        raise RuntimeError("the OOS repository-custody state binding is incomplete")

    wgcf_namespace = repository_wgcf["namespace_pattern"].replace("{operator}", operator())
    wgcf_deployment = json.loads(run([
        "k3s", "kubectl", "-n", wgcf_namespace, "get",
        f"deployment/{repository_wgcf['deployment']}", "-o", "json",
    ]).stdout)
    wgcf_environment = {
        item.get("name"): item
        for container_item in wgcf_deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        for item in container_item.get("env", [])
    }
    if wgcf_environment.get("WGCF_REPOSITORY_CUSTODY_READINESS_ENABLED", {}).get("value") != "true":
        raise RuntimeError("WGCF repository-custody readiness is not active")

    try:
        with urlopen(
            Request(
                f"http://127.0.0.1:{policy['runtime']['console_port']}/api/console/capabilities",
                headers={"accept": "application/json"},
            ),
            timeout=15,
        ) as response:
            capabilities = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Console repository capability readback is unavailable: {type(exc).__name__}") from None
    projected = next(
        (
            item for item in capabilities.get("capabilities", [])
            if item.get("id") == "repository-provisioning"
        ),
        None,
    )
    if (
        capabilities.get("mode") != "live"
        or not isinstance(projected, dict)
        or projected.get("source", {}).get("state") != "available"
        or projected.get("mutation", {}).get("state") != "available"
    ):
        raise RuntimeError("Console repository provisioning is not executable")

    require_repository_projection_route(policy)

    return {
        "console_capability": "available",
        "credential_binding_digest": repository["credential_binding_ref"]["digest"],
        "credential_expires_at": expires_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "oos_runtime": "active",
        "wgcf_readiness": "active",
    }


def require_repository_projection_route(policy: dict[str, Any]) -> None:
    """Probe the Console contract, not OOS's internal error representation."""
    probe_url = (
        f"http://127.0.0.1:{policy['runtime']['console_port']}"
        "/api/repositories/provisioning/requests/repository-custody-request:runtime-status-probe"
    )
    deadline = time.monotonic() + 30
    while True:
        try:
            with urlopen(Request(probe_url, headers={"accept": "application/json"}), timeout=5):
                raise RuntimeError("the repository provisioning readiness probe returned unexpected state")
        except HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
            except (ValueError, UnicodeError):
                body = {}
            if (
                exc.code == 404 and isinstance(body, dict)
                and body.get("code") == "repository_custody_oos_rejected"
                and body.get("error") == "Repository custody request was not found."
                and body.get("mode") == "live" and body.get("status") == "offline"
            ):
                return
            if exc.code not in {502, 503}:
                raise RuntimeError("the Console-to-OOS repository provisioning route is not active") from None
        except (URLError, TimeoutError):
            pass
        if time.monotonic() < deadline:
            time.sleep(1)
            continue
        raise RuntimeError("the Console-to-OOS repository provisioning route is unavailable") from None


def write_active_marker(policy: dict[str, Any]) -> None:
    ensure_private(STATE_ROOT)
    marker = STATE_ROOT / "active.json"
    payload = {
        "schema_version": 1,
        "platform_revision": policy["security"]["platform_revision"],
        "platform_tree": policy["security"]["platform_tree"],
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


@contextmanager
def operating_proof_lock(*, blocking: bool = True):
    ensure_private(STATE_ROOT)
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(OPERATING_PROOF_LOCK_PATH, flags, 0o600)
    except OSError as exc:
        raise RuntimeError(f"operating-proof lock is unavailable: {type(exc).__name__}") from None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid():
            raise RuntimeError("operating-proof lock path is unsafe")
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            raise RuntimeError("complete runtime lifecycle is busy; credential renewal will retry") from None
        yield
    finally:
        os.close(descriptor)


def reusable_operating_receipt(policy: dict[str, Any]) -> Path | None:
    ensure_private(RECEIPT_ROOT)
    expected_security = {
        "gate_id": policy["security"]["gate_id"],
        "decision_uri": policy["security"]["decision_uri"],
        "decision_digest": policy["security"]["decision_digest"],
        "reviewed_revisions": policy["security"]["reviewed_revisions"],
    }
    expected_fields = {
        "schema_version", "artifact_type", "action", "delivery", "security",
        "credential_values_embedded", "recorded_at", "proof", "content_digest",
    }
    expected_proof_fields = {
        "activation_receipt", "invalid_credential_denied", "revoked_gate_denied",
        "stale_state_denied", "process_loss_recovered", "restart_receipt",
        "rollback_receipt", "teardown_receipt", "restored_activation_receipt",
        "normal_availability_restored", "repository_provisioning_restored",
        "repository_credentials_renewed", "workflow_credentials_renewed", "credential_refresh_receipt",
    }
    for path in sorted(RECEIPT_ROOT.glob("*-verify-operating.json"), reverse=True):
        try:
            metadata = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.geteuid()
                or stat.S_IMODE(metadata.st_mode) != 0o600
            ):
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict) or set(value) != expected_fields:
            continue
        content_digest = value.pop("content_digest", None)
        proof = value.get("proof")
        if (
            content_digest != provider.canonical_digest(value)
            or value.get("schema_version") != 1
            or value.get("artifact_type") != "governance-console-complete-runtime-receipt"
            or value.get("action") != "verify-operating"
            or value.get("delivery") != policy["delivery"]
            or value.get("security") != expected_security
            or value.get("credential_values_embedded") is not False
            or not isinstance(value.get("recorded_at"), str)
            or not isinstance(proof, dict)
            or set(proof) != expected_proof_fields
            or any(proof.get(name) is not True for name in (
                "invalid_credential_denied", "revoked_gate_denied",
                "stale_state_denied", "process_loss_recovered",
                "normal_availability_restored", "repository_provisioning_restored",
                "repository_credentials_renewed",
                "workflow_credentials_renewed",
            ))
            or any(not isinstance(proof.get(name), str) or not proof[name] for name in (
                "activation_receipt", "restart_receipt", "rollback_receipt",
                "teardown_receipt", "restored_activation_receipt",
                "credential_refresh_receipt",
            ))
        ):
            continue
        return path
    return None


def activate(policy: dict[str, Any]) -> Path:
    policy, activation = resolve_security_decision(policy)
    require_activation_allowed(policy)
    require_provider_tools()
    write_resolved_policies(policy, activation)
    write_composition_supervisor(policy)
    model_management.prepare(policy, repo_root=repo_path("platform-engineering"), state_root=STATE_ROOT,
        operator_id=policy["platform_operation_provider"]["operator_id"],
        gateway_namespace="devint-governed-ai-gateway-" + operator(), run=run, vault_token=vault_token)
    refresh_record_authorities(policy)
    run(composition_command(policy, "up"))
    # Full composition startup may take longer than the data freshness window.
    refresh_record_authorities(policy)
    delivered = deliver_repository_provisioning_identity(policy)
    workflow_credential_manager(policy).renew(extra_annotations={
        "workspace-governance/repository-token-expires-at": delivered["token_expires_at"],
    })
    secret = credential()
    gateway = cni_gateway()
    write_provider_unit(policy, gateway, secret)
    apply_kubernetes_binding(policy, gateway, secret)
    apply_record_authority_binding(policy)
    model_management.bind_oos(policy, state_root=STATE_ROOT,
        namespace=policy["runtime"]["namespace_pattern"].format(operator=operator()),
        operator_id=policy["platform_operation_provider"]["operator_id"], run=run)
    require_publication_owner_bindings(policy)
    run(cross_domain_command("activate"))
    write_active_marker(policy)
    refresh_stale_provider(policy)
    write_repository_refresh_units()
    return status(policy, action="activate")


def require_model_management_runtime(policy: dict[str, Any]) -> dict[str, Any] | None:
    if not model_management.enabled(policy):
        return None
    base = f"http://127.0.0.1:{policy['runtime']['console_port']}"
    try:
        with urlopen(Request(base + "/api/model-operations/runtime/registry", headers={"accept": "application/json", "origin": base}), timeout=30) as response:
            raw = response.read(1_048_577)
            if len(raw) > 1_048_576:
                raise ValueError()
            registry = json.loads(raw)
        configuration = registry["configuration"]
        if (registry["schema_version"] != 1 or set(row["backend_id"] for row in registry["backends"]) != {"local-ollama", "managed-codex"}
                or configuration["revision"] != configuration["current_revision"]
                or configuration["digest"] != provider.canonical_digest(configuration["configuration"])):
            raise ValueError()
        return {"management_api_current": True, "configuration_revision": configuration["revision"],
                "verified_registration_count": len(configuration["configuration"]["models"]), "provider_health": "not-probed"}
    except (OSError, ValueError, KeyError, TypeError):
        raise RuntimeError("The commissioned Console model-management owner projection is unavailable or invalid.") from None


def status(policy: dict[str, Any], *, action: str = "status") -> Path:
    policy, activation = resolve_security_decision(policy)
    require_materialized_policy(policy, activation)
    require_activation_allowed(policy)
    run(composition_command(policy, "status"))
    if run(["systemctl", "--user", "is-active", "--quiet", UNIT_NAME], check=False).returncode:
        raise RuntimeError("Platform operation provider service is not active")
    if run(["systemctl", "--user", "is-active", "--quiet", REPOSITORY_REFRESH_TIMER], check=False).returncode:
        raise RuntimeError("repository credential renewal timer is not active")
    run(cross_domain_command("status"))
    catalog = require_current_provider(policy)
    console = console_operations(policy)
    repository = repository_provisioning_status(policy)
    workflows = workflow_credential_manager(policy).status()
    records = record_binding_status(policy)
    realization = require_source_realization_profile(policy)
    primary_records = require_console_primary_records(policy)
    operator_bindings = require_console_operator_bindings(policy)
    publication = {**require_publication_owner_bindings(policy), **require_console_publication_mode(policy)}
    model_runtime = require_model_management_runtime(policy)
    return receipt(action, policy, {
        "composition": policy["platform_operation_provider"]["composition_id"],
        "composition_current": True,
        "console_mode": console["mode"],
        "console_status": console["status"],
        "platform_catalog_id": catalog["catalog_id"],
        "platform_catalog_source_version": catalog["source_version"],
        "platform_subject_count": len(catalog["subjects"]),
        "provider_active": True,
        "repository_provisioning": repository,
        "workflow_credentials": workflows,
        "record_authority": records,
        "source_realization": realization,
        "primary_records": primary_records,
        "operator_bindings": operator_bindings,
        "product_publication": publication,
        "model_management": model_runtime,
    })


def restart(policy: dict[str, Any]) -> Path:
    policy, activation = resolve_security_decision(policy)
    write_resolved_policies(policy, activation)
    require_activation_allowed(policy)
    refresh_record_authorities(policy)
    delivered = deliver_repository_provisioning_identity(policy)
    workflow_credential_manager(policy).renew(extra_annotations={
        "workspace-governance/repository-token-expires-at": delivered["token_expires_at"],
    })
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
    apply_record_authority_binding(policy)
    run(cross_domain_command("restart"))
    write_active_marker(policy)
    write_repository_refresh_units()
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
        "OOS_REPOSITORY_CUSTODY_ENABLED",
        "OOS_REPOSITORY_CUSTODY_STATE_ROOT",
        "OOS_REPOSITORY_PROVISIONING_INSTALLATION_TOKEN",
        "WGCF_REPOSITORY_CUSTODY_BASE_URL",
        "WGCF_REPOSITORY_CUSTODY_CALLER_ID",
    ]
    failures: list[str] = []
    if run(["k3s", "kubectl", "-n", ns, "set", "env", deployment, *(f"{name}-" for name in names)], check=False).returncode:
        failures.append("oos-environment-removal")
    state_patch = {
        "spec": {"template": {"spec": {
            "containers": [{
                "name": policy["runtime"]["oos_deployment"],
                "volumeMounts": [{
                    "name": OOS_STATE_VOLUME_NAME,
                    "mountPath": OOS_STATE_MOUNT_PATH,
                    "$patch": "delete",
                }, {
                    "name": policy["repository_provisioning"]["oos"]["state_volume_name"],
                    "mountPath": policy["repository_provisioning"]["oos"]["state_mount_path"],
                    "$patch": "delete",
                }],
            }],
            "volumes": [
                {"name": OOS_STATE_VOLUME_NAME, "$patch": "delete"},
                {
                    "name": policy["repository_provisioning"]["oos"]["state_volume_name"],
                    "$patch": "delete",
                },
            ],
        }}},
    }
    if run([
        "k3s", "kubectl", "-n", ns, "patch", deployment, "--type=strategic",
        "--patch", json.dumps(state_patch, separators=(",", ":")),
    ], check=False).returncode:
        failures.append("oos-state-binding-removal")
    if run([
        "k3s", "kubectl", "-n", ns, "delete",
        f"secret/{SECRET_NAME}", f"service/{SERVICE_NAME}", f"endpoints/{SERVICE_NAME}",
        "--ignore-not-found=true",
    ], check=False).returncode:
        failures.append("provider-kubernetes-binding-removal")
    return failures


def rollback(policy: dict[str, Any], *, cleanup: bool = False) -> Path:
    failures: list[str] = []
    # Stop renewal before revocation so a concurrent timer cannot restore it.
    for unit in (REPOSITORY_REFRESH_TIMER, REPOSITORY_REFRESH_SERVICE):
        if (UNIT_ROOT / unit).is_file():
            if run(["systemctl", "--user", "disable", "--now", unit], check=False).returncode:
                failures.append("repository-credential-renewal-disable")
    try:
        model_management.disable(policy, state_root=STATE_ROOT,
            namespace=policy["runtime"]["namespace_pattern"].format(operator=operator()), run=run)
    except (OSError, RuntimeError, model_management.ModelCompositionError):
        failures.append("model-management-authority-removal")
    try:
        apply_record_authority_binding(policy, enabled=False)
        dropin = UNIT_ROOT / f"{composition_supervisor_unit(policy)}.d" / "console-runtime.conf"
        if dropin.is_symlink():
            raise RuntimeError("the composition supervisor drop-in is unsafe")
        dropin.unlink(missing_ok=True)
        # Preserve the admitted generic profile unit and all owner data. Only
        # the Console-owned coordinator override is retired during rollback.
        run(["systemctl", "--user", "daemon-reload"])
    except (OSError, RuntimeError):
        failures.append("console-record-boundary-restoration")
    try:
        revoke_repository_provisioning_identity(policy)
    except RuntimeError:
        failures.append("repository-provisioning-credential-revocation")
    binding_failures = remove_kubernetes_binding(policy)
    failures.extend(binding_failures)
    if RESOLVED_ACTIVATION_POLICY_PATH.is_file() and not binding_failures:
        if run(cross_domain_command("cleanup" if cleanup else "rollback"), check=False).returncode:
            failures.append("console-cross-domain-cleanup")
    elif RESOLVED_ACTIVATION_POLICY_PATH.is_file():
        failures.append("console-cross-domain-cleanup-blocked-by-oos-binding-removal")
    if run(["systemctl", "--user", "disable", "--now", UNIT_NAME], check=False).returncode:
        failures.append("provider-service-disable")
    remove_active_marker()
    if cleanup:
        (UNIT_ROOT / UNIT_NAME).unlink(missing_ok=True)
        for unit in (REPOSITORY_REFRESH_TIMER, REPOSITORY_REFRESH_SERVICE):
            (UNIT_ROOT / unit).unlink(missing_ok=True)
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
        "repository_provisioning_credential_present": False,
        "preexisting_workflow_bindings_preserved": True,
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
    with operating_proof_lock():
        resolved, _ = resolve_security_decision(policy)
        cached = reusable_operating_receipt(resolved)
        if cached is not None:
            return cached
        require_retained_supervision()
        activate_receipt = activate(policy)
        credential_refresh_receipt = refresh_repository_credentials(policy, force=True)
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
        final_policy, _ = resolve_security_decision(policy)
        return receipt("verify-operating", final_policy, {
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
            "repository_provisioning_restored": True,
            "repository_credentials_renewed": True,
            "workflow_credentials_renewed": True,
            "credential_refresh_receipt": str(credential_refresh_receipt),
        })


def main() -> int:
    global REPO_PATH_OVERRIDES
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("validate", "activate", "status", "restart", "rollback", "cleanup", "teardown", "verify-operating", "refresh-credentials"),
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
            "refresh-credentials": refresh_repository_credentials,
        }
        if args.action == "activate" and not inside_composition_supervisor(policy):
            # Delegate before taking the lifecycle lock. The independently
            # retained unit takes it normally; holding it while waiting here
            # would deadlock its activation. No new flag or bypass is used.
            resolved, _ = resolve_security_decision(policy)
            require_activation_allowed(resolved)
            if args.policy.resolve() != POLICY_PATH.resolve():
                raise RuntimeError("normal activation requires the canonical complete-runtime policy")
            require_provider_tools()
            write_composition_supervisor(resolved)
            run(["systemctl", "--user", "restart", composition_supervisor_unit(resolved)])
            result = status(policy, action="activate")
        elif args.action in {"status", "verify-operating"}:
            result = actions[args.action](policy)
        else:
            if args.action == "activate":
                require_retained_supervision()
            with operating_proof_lock(blocking=args.action != "refresh-credentials"):
                result = actions[args.action](policy)
        print(f"complete Console runtime {args.action} succeeded: {result}")
        return 0
    except (RuntimeError, provider.ProviderError, workflow_credentials.CredentialError, workflow_credentials.IdentityError, record_authority.RecordAuthorityError, model_management.ModelCompositionError) as exc:
        print(f"complete Console runtime {args.action} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
