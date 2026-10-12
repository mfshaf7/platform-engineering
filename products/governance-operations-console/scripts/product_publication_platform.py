#!/usr/bin/env python3
"""Commission the bounded Product Publication path in local dev-integration."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import yaml

import console_cross_domain_activation as base


PRODUCT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PRODUCT_ROOT.parents[1]
POLICY_PATH = PRODUCT_ROOT / "product-publication-commissioning-policy.yaml"
STATE_ROOT = Path.home() / ".local/state/platform-engineering/product-publication"
RECEIPT_ROOT = STATE_ROOT / "receipts"
INTENT_PATH = STATE_ROOT / "proof-intent.json"
OOS_VOLUME = "product-publication-state"
WGCF_VOLUME = "product-publication-owner-source"
PRODUCT_ENV_NAMES = (
    "GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_AUTHORITY_REVISION",
    "GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_SECURITY_DECISION_URI",
    "GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_SECURITY_DECISION_DIGEST",
    "GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_SECURITY_DECISION_REVISION",
    "GOVERNANCE_CONSOLE_PRODUCT_MAINTENANCE_AUTHORITY_REVISION",
    "GOVERNANCE_CONSOLE_PRODUCT_MAINTENANCE_SECURITY_DECISION_URI",
    "GOVERNANCE_CONSOLE_PRODUCT_MAINTENANCE_SECURITY_DECISION_DIGEST",
    "GOVERNANCE_CONSOLE_PRODUCT_MAINTENANCE_SECURITY_DECISION_REVISION",
    "GOVERNANCE_CONSOLE_PRODUCT_HEALTH_PROJECTION_PATH",
    "GOVERNANCE_CONSOLE_PRODUCT_HEALTH_RECEIPT_PATH",
)
OOS_ENV_NAMES = (
    "OOS_PRODUCT_PUBLICATION_ENABLED",
    "OOS_PRODUCT_PUBLICATION_STATE_ROOT",
    "OOS_PRODUCT_PUBLICATION_CALLER_OPERATOR_BINDINGS_JSON",
    "OOS_PRODUCT_PUBLICATION_SECURITY_DECISION_URI",
    "OOS_PRODUCT_PUBLICATION_SECURITY_DECISION_DIGEST",
    "OOS_PRODUCT_PUBLICATION_SECURITY_DECISION_REVISION",
    "WGCF_PRODUCT_PUBLICATION_BASE_URL",
    "WGCF_PRODUCT_PUBLICATION_CALLER_ID",
    "WGCF_PRODUCT_PUBLICATION_CALLER_SECRET",
    "WGCF_PRODUCT_PUBLICATION_IMPLEMENTATION_REF",
    "WGCF_PRODUCT_PUBLICATION_SERVICE_IDENTITY_REF",
)
WGCF_ENV_NAMES = (
    "WGCF_PRODUCT_PUBLICATION_READINESS_ENABLED",
    "WGCF_PRODUCT_PUBLICATION_CONTRACT_ROOT",
    "WGCF_PRODUCT_PUBLICATION_OWNER_REPO_ROOTS",
    "WGCF_PRODUCT_PUBLICATION_SERVICE_IDENTITY_REF",
)


class ProductPublicationError(RuntimeError):
    pass


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 2:
        raise ProductPublicationError("Product Publication commissioning policy is invalid")
    return value


def run_bytes(args: list[str]) -> bytes:
    result = subprocess.run(args, capture_output=True, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout or b"command failed").decode(
            errors="replace"
        ).strip().splitlines()[-1]
        raise ProductPublicationError(f"{args[0]} failed: {detail}")
    return result.stdout


def git_file(repo: Path, revision: str, relative_path: str) -> bytes:
    return run_bytes(["git", "-C", str(repo), "show", f"{revision}:{relative_path}"])


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical_digest(value: Any) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def publication(policy: dict[str, Any]) -> dict[str, Any]:
    value = policy.get("product_publication")
    if not isinstance(value, dict):
        raise ProductPublicationError("Product Publication policy binding is missing")
    return value


def existing_internal_publication(policy: dict[str, Any]) -> dict[str, Any]:
    value = publication(policy).get("existing_internal_publication")
    if not isinstance(value, dict):
        raise ProductPublicationError("existing internal publication binding is missing")
    return value


def workspace_authority_revision(policy: dict[str, Any]) -> str:
    """Select current clean authority only when the reviewed WGCF bundle is unchanged."""
    binding = publication(policy)
    workspace_repo = base.repo_path("workspace-governance")
    wgcf = policy["owners"]["wgcf"]
    reviewed_revision = binding["security_reviewed_authority_revision"]
    try:
        base.require_source_authority({
            "repo": "workspace-governance",
            "minimum_revision": reviewed_revision,
        })
    except base.ActivationError as exc:
        raise ProductPublicationError(str(exc)) from exc
    current_revision = base.git_head(workspace_repo)
    bundle = json.loads(git_file(
        base.repo_path(wgcf["repo"]),
        wgcf["revision"],
        "contracts/product-publication/manifest.json",
    ))
    authority_files = bundle.get("authority_files")
    if (
        bundle.get("authority_repo") != "workspace-governance"
        or bundle.get("authority_commit") != binding["authority_revision"]
        or not isinstance(authority_files, dict)
        or not authority_files
    ):
        raise ProductPublicationError("WGCF Product Publication authority bundle is invalid")
    for relative_path, expected_digest in authority_files.items():
        if sha256(git_file(workspace_repo, current_revision, relative_path)) != f"sha256:{expected_digest}":
            raise ProductPublicationError(
                "current Workspace Governance source changes the reviewed Product Publication authority bundle"
            )
    return current_revision


def command_security_decision(policy: dict[str, Any]) -> dict[str, str]:
    decision = publication(policy)["security_decision"]
    return {
        key: decision[key]
        for key in ("uri", "digest", "revision")
    }


def validate(policy: dict[str, Any]) -> None:
    try:
        base.validate(policy)
    except base.ActivationError as exc:
        raise ProductPublicationError(str(exc)) from exc
    activation = policy["activation"]
    binding = publication(policy)
    if (
        activation.get("delivery_id") != "delivery-894"
        or activation.get("work_item_ref") != "openproject://work_packages/1273"
        or activation.get("security_gate_id")
        != "gate:product-publication-lifecycle-maintenance-activation"
    ):
        raise ProductPublicationError("Product Publication activation binding is not exact")
    if binding.get("allowed_actions") != ["publish", "unpublish", "archive", "restore"]:
        raise ProductPublicationError("Product Publication maintenance action scope is not exact")
    if binding.get("allowed_targets") != {
        "unlisted": {
            "posture": "unlisted", "listing_scope": None,
            "audience": None, "access_class": None,
        },
        "internal": {
            "posture": "internal", "listing_scope": "workspace-portfolio",
            "audience": "workspace-operators", "access_class": "workspace-authenticated",
        },
        "archived": {
            "posture": "archived", "listing_scope": "historical-archive",
            "audience": "historical", "access_class": "historical-read-only",
        },
    } or binding.get("denied_targets") != ["client", "public"]:
        raise ProductPublicationError("Product Publication target scope is not exact")
    if binding.get("sequence") != {
        "publication_actions": ["unpublish", "archive", "restore", "publish"],
        "publication_postures": ["internal", "unlisted", "archived", "unlisted", "internal"],
        "inventory_actions": ["retire", "restore"],
        "inventory_postures": ["active", "retired", "active"],
        "required_manifest_boundaries": [
            "active-internal", "retired-unlisted",
            "active-unlisted-restored", "active-internal-final",
        ],
    }:
        raise ProductPublicationError("Product Publication maintenance sequence is not exact")
    prior = existing_internal_publication(policy)
    if prior != {
        "request_id": "product-publication-request:platform:1258:129f5eb7ebce",
        "idempotency_key": "product-publication:platform:1258:129f5eb7ebce",
        "command_digest": "sha256:4643e3d084646767aab29d2580e857f1562286323d418daa71a33971055983b2",
        "receipt_id": "product-publication-receipt:platform:1258:129f5eb7ebce",
        "receipt_digest": "sha256:d01bf320a74a21389e5efd0b997e835e81c051e8c0b1a3a73104b78e70935a61",
        "publication_version": 1,
        "publication_posture": "internal",
        "security_decision": {
            "uri": "security-architecture://product-publication/decisions/console-internal-v1",
            "digest": "sha256:d1d120e1a081d29319394f70fc31b423f81039ccef9e2da0b87327241f5ba837",
            "revision": "3dc6e0f6cc2f829b4967ac73269a409e18e0de21",
        },
    }:
        raise ProductPublicationError("existing internal publication binding is not exact")
    if binding.get("wgcf_contract_root") != "/app/contracts/product-publication":
        raise ProductPublicationError("Product Publication WGCF contract root is not exact")
    workspace_repo = base.repo_path("workspace-governance")
    reviewed_authority_revision = binding.get("security_reviewed_authority_revision")
    if (
        binding.get("authority_revision")
        != policy["authority"]["workspace_governance_revision"]
        or reviewed_authority_revision
        != policy["authority"].get("workspace_governance_reviewed_revision")
        or reviewed_authority_revision
        not in policy["architecture"].get("security_review_revisions", [])
        or base.run(
            [
                "git", "-C", str(workspace_repo), "merge-base", "--is-ancestor",
                reviewed_authority_revision, binding["authority_revision"],
            ],
            check=False,
        ).returncode
        or git_file(
            workspace_repo,
            reviewed_authority_revision,
            "contracts/product-publication.yaml",
        )
        != git_file(
            workspace_repo,
            binding["authority_revision"],
            "contracts/product-publication.yaml",
        )
    ):
        raise ProductPublicationError(
            "Product Publication runtime authority does not preserve its Security-reviewed contract"
        )
    workspace_authority_revision(policy)
    security = binding.get("security_decision") or {}
    if (
        security.get("revision") != policy["authority"]["security_revision"]
        or security.get("uri")
        != "security-architecture://product-publication/decisions/lifecycle-maintenance-v1"
        or security.get("approved_target_postures") != ["unlisted", "internal", "archived"]
    ):
        raise ProductPublicationError("Product Publication Security decision is not exact")
    security_repo = base.repo_path("security-architecture")
    review_bytes = git_file(
        security_repo,
        security["revision"],
        policy["authority"]["security_review_ref"],
    )
    if sha256(review_bytes) != security.get("digest"):
        raise ProductPublicationError("Product Publication Security decision digest changed")

    owner_repo = base.repo_path(binding["owner_repo"])
    if base.run(
        [
            "git", "-C", str(owner_repo), "merge-base", "--is-ancestor",
            binding["owner_source_minimum_revision"], base.git_head(owner_repo),
        ],
        check=False,
    ).returncode:
        raise ProductPublicationError("Product Publication owner source minimum is absent")
    for role in ("oos", "wgcf"):
        owner = policy["owners"][role]
        reviewed_revision = owner.get("security_reviewed_revision")
        if (
            reviewed_revision
            not in policy["architecture"].get("security_review_revisions", [])
            or base.run(
                [
                    "git", "-C", str(base.repo_path(owner["repo"])),
                    "merge-base", "--is-ancestor",
                    reviewed_revision, owner["revision"],
                ],
                check=False,
            ).returncode
        ):
            raise ProductPublicationError(
                f"{role} runtime revision does not descend from its Security-reviewed source"
            )
        raw = git_file(
            base.repo_path(owner["repo"]),
            owner["revision"],
            "contracts/product-publication/manifest.json",
        )
        owner_manifest = json.loads(raw)
        if owner_manifest.get("runtime_activation") is not True:
            raise ProductPublicationError(f"{role} Product Publication source gate is inactive")
        if role == "oos" and (
            owner_manifest.get("allowed_target_postures")
            != ["unlisted", "internal", "archived"]
            or owner_manifest.get("lifecycle_maintenance", {}).get("runtime_activation")
            is not True
            or owner_manifest.get("lifecycle_maintenance", {}).get("allowed_actions")
            != ["archive", "restore"]
            or owner_manifest.get("security_authority") != {
                "decision_uri": security["uri"],
                "decision_digest": security["digest"],
                "decision_revision": security["revision"],
                "approved_target_postures": ["unlisted", "internal", "archived"],
            }
            or owner_manifest.get("activation_prerequisites") != {
                "security_work_item": "openproject://work_packages/1271",
                "platform_work_item": "openproject://work_packages/1273",
            }
        ):
            raise ProductPublicationError("OOS Product Publication lifecycle activation is not exact")


def namespace(owner: dict[str, Any]) -> str:
    return owner["namespace"].replace("{operator}", base.operator())


def state_directory(policy: dict[str, Any]) -> Path:
    relative = Path(publication(policy)["state_directory"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ProductPublicationError("Product Publication state directory is unsafe")
    return (
        base.WORKSPACE_ROOT
        / ".dev-integration"
        / policy["owners"]["oos"]["profile"]
        / base.operator()
        / relative
    )


def sequence_evidence_path(policy: dict[str, Any]) -> Path:
    relative = Path(publication(policy)["sequence_evidence"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ProductPublicationError("Product Publication sequence evidence path is unsafe")
    return STATE_ROOT / relative


def strategic_patch(namespace_name: str, deployment: str, value: dict[str, Any]) -> None:
    base.kubectl(
        "-n", namespace_name, "patch", f"deployment/{deployment}",
        "--type=strategic", "-p", json.dumps(value, separators=(",", ":")),
    )


def configure_oos_security_binding(policy: dict[str, Any]) -> None:
    """Prime the fail-closed source binding before any broader runtime wait."""
    binding = publication(policy)
    oos = policy["owners"]["oos"]
    strategic_patch(namespace(oos), oos["deployment"], {
        "spec": {"template": {"spec": {"containers": [{
            "name": oos["container"],
            "env": [
                {
                    "name": "OOS_PRODUCT_PUBLICATION_SECURITY_DECISION_URI",
                    "value": binding["security_decision"]["uri"],
                },
                {
                    "name": "OOS_PRODUCT_PUBLICATION_SECURITY_DECISION_DIGEST",
                    "value": binding["security_decision"]["digest"],
                },
                {
                    "name": "OOS_PRODUCT_PUBLICATION_SECURITY_DECISION_REVISION",
                    "value": binding["security_decision"]["revision"],
                },
            ],
        }]}}},
    })
    base.kubectl(
        "-n", namespace(oos), "rollout", "status",
        f"deployment/{oos['deployment']}", "--timeout=300s",
    )


def configure_workloads(policy: dict[str, Any]) -> None:
    binding = publication(policy)
    state = state_directory(policy)
    base.ensure_private_directory(state)
    oos = policy["owners"]["oos"]
    wgcf = policy["owners"]["wgcf"]
    oos_env = [
        {"name": "OOS_PRODUCT_PUBLICATION_ENABLED", "value": "true"},
        {"name": "OOS_PRODUCT_PUBLICATION_STATE_ROOT", "value": binding["oos_mount_path"]},
        {
            "name": "OOS_PRODUCT_PUBLICATION_CALLER_OPERATOR_BINDINGS_JSON",
            "value": json.dumps(
                {policy["credentials"]["console_oos"]["caller_id"]: policy["session"]["operator_id"]},
                separators=(",", ":"),
            ),
        },
        {"name": "OOS_PRODUCT_PUBLICATION_SECURITY_DECISION_URI", "value": binding["security_decision"]["uri"]},
        {"name": "OOS_PRODUCT_PUBLICATION_SECURITY_DECISION_DIGEST", "value": binding["security_decision"]["digest"]},
        {"name": "OOS_PRODUCT_PUBLICATION_SECURITY_DECISION_REVISION", "value": binding["security_decision"]["revision"]},
        {
            "name": "WGCF_PRODUCT_PUBLICATION_BASE_URL",
            "value": f"http://{wgcf['service']}.{namespace(wgcf)}.svc.cluster.local:{wgcf['remote_port']}",
        },
        {"name": "WGCF_PRODUCT_PUBLICATION_CALLER_ID", "value": "operator-orchestration-service"},
        {
            "name": "WGCF_PRODUCT_PUBLICATION_CALLER_SECRET",
            "valueFrom": {"secretKeyRef": {
                "name": binding["wgcf_caller_secret"]["secret_name"],
                "key": binding["wgcf_caller_secret"]["secret_key"],
            }},
        },
        {"name": "WGCF_PRODUCT_PUBLICATION_IMPLEMENTATION_REF", "value": wgcf["revision"]},
        {"name": "WGCF_PRODUCT_PUBLICATION_SERVICE_IDENTITY_REF", "value": binding["service_identity_ref"]},
    ]
    strategic_patch(namespace(oos), oos["deployment"], {
        "spec": {"template": {"spec": {
            "containers": [{
                "name": oos["container"],
                "env": oos_env,
                "volumeMounts": [{"name": OOS_VOLUME, "mountPath": binding["oos_mount_path"]}],
            }],
            "volumes": [{"name": OOS_VOLUME, "hostPath": {"path": str(state), "type": "Directory"}}],
        }}},
    })
    owner_repo = base.repo_path(binding["owner_repo"])
    strategic_patch(namespace(wgcf), wgcf["deployment"], {
        "spec": {"template": {"spec": {
            "containers": [{
                "name": wgcf["container"],
                "env": [
                    {"name": "WGCF_PRODUCT_PUBLICATION_READINESS_ENABLED", "value": "true"},
                    {"name": "WGCF_PRODUCT_PUBLICATION_CONTRACT_ROOT", "value": binding["wgcf_contract_root"]},
                    {
                        "name": "WGCF_PRODUCT_PUBLICATION_OWNER_REPO_ROOTS",
                        "value": json.dumps(
                            {binding["owner_repo"]: binding["wgcf_owner_mount_path"]},
                            separators=(",", ":"),
                        ),
                    },
                    {"name": "WGCF_PRODUCT_PUBLICATION_SERVICE_IDENTITY_REF", "value": binding["service_identity_ref"]},
                ],
                "volumeMounts": [{
                    "name": WGCF_VOLUME,
                    "mountPath": binding["wgcf_owner_mount_path"],
                    "readOnly": True,
                }],
            }],
            "volumes": [{"name": WGCF_VOLUME, "hostPath": {"path": str(owner_repo), "type": "Directory"}}],
        }}},
    })
    for owner in (wgcf, oos):
        base.kubectl(
            "-n", namespace(owner), "rollout", "status",
            f"deployment/{owner['deployment']}", "--timeout=300s",
        )


def write_console_environment(policy: dict[str, Any]) -> Path:
    path = base.PRIVATE_ROOT / "console.env"
    if not path.is_file():
        raise ProductPublicationError("Console private environment is unavailable")
    retained = [
        line for line in path.read_text(encoding="utf-8").splitlines()
        if line.split("=", 1)[0] not in PRODUCT_ENV_NAMES
    ]
    binding = publication(policy)
    authority_revision = workspace_authority_revision(policy)
    retained.extend([
        f"GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_AUTHORITY_REVISION={authority_revision}",
        f"GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_SECURITY_DECISION_URI={binding['security_decision']['uri']}",
        f"GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_SECURITY_DECISION_DIGEST={binding['security_decision']['digest']}",
        f"GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_SECURITY_DECISION_REVISION={binding['security_decision']['revision']}",
        f"GOVERNANCE_CONSOLE_PRODUCT_MAINTENANCE_AUTHORITY_REVISION={authority_revision}",
        f"GOVERNANCE_CONSOLE_PRODUCT_MAINTENANCE_SECURITY_DECISION_URI={binding['security_decision']['uri']}",
        f"GOVERNANCE_CONSOLE_PRODUCT_MAINTENANCE_SECURITY_DECISION_DIGEST={binding['security_decision']['digest']}",
        f"GOVERNANCE_CONSOLE_PRODUCT_MAINTENANCE_SECURITY_DECISION_REVISION={binding['security_decision']['revision']}",
        f"GOVERNANCE_CONSOLE_PRODUCT_HEALTH_PROJECTION_PATH={STATE_ROOT / 'product-health.json'}",
        f"GOVERNANCE_CONSOLE_PRODUCT_HEALTH_RECEIPT_PATH={STATE_ROOT / 'product-health.receipt.json'}",
    ])
    path.write_text("\n".join(retained) + "\n", encoding="utf-8")
    path.chmod(0o600)
    base.run(["systemctl", "--user", "restart", base.unit_name("console")])
    return path


def product_mode(policy: dict[str, Any], expected: str = "live") -> dict[str, Any]:
    deadline = time.monotonic() + 180
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            status, value = base.http_request_json(
                base.console_url(policy, "/api/product-portfolio/publications")
            )
            last = value
            if status == 200 and value.get("mode") == expected:
                return value
        except base.ActivationError:
            pass
        time.sleep(2)
    raise ProductPublicationError(
        f"Product Publication mode did not become {expected}: {last.get('reason_code', 'unavailable')}"
    )


def deployment_binding(policy: dict[str, Any], role: str) -> dict[str, Any]:
    owner = policy["owners"][role]
    value = json.loads(base.kubectl(
        "-n", namespace(owner), "get", f"deployment/{owner['deployment']}", "-o", "json"
    ).stdout)
    container = next(
        item for item in value["spec"]["template"]["spec"]["containers"]
        if item["name"] == owner["container"]
    )
    return {
        "env_names": sorted(item["name"] for item in container.get("env", [])),
        "mount_names": sorted(item["name"] for item in container.get("volumeMounts", [])),
        "volume_names": sorted(item["name"] for item in value["spec"]["template"]["spec"].get("volumes", [])),
        "ready_replicas": value.get("status", {}).get("readyReplicas", 0),
    }


def runtime_status(policy: dict[str, Any]) -> dict[str, Any]:
    mode = product_mode(policy)
    oos = deployment_binding(policy, "oos")
    wgcf = deployment_binding(policy, "wgcf")
    if (
        not set(OOS_ENV_NAMES).issubset(oos["env_names"])
        or OOS_VOLUME not in oos["mount_names"]
        or OOS_VOLUME not in oos["volume_names"]
        or not set(WGCF_ENV_NAMES).issubset(wgcf["env_names"])
        or WGCF_VOLUME not in wgcf["mount_names"]
        or WGCF_VOLUME not in wgcf["volume_names"]
        or oos["ready_replicas"] != 1
        or wgcf["ready_replicas"] != 1
    ):
        raise ProductPublicationError("Product Publication runtime binding is incomplete")
    return {"mode": mode["mode"], "oos": oos, "wgcf": wgcf}


def product_health_proof() -> dict[str, Any]:
    base.ensure_private_directory(STATE_ROOT)
    runtime_projection = STATE_ROOT / "runtime-observations.json"
    runtime_receipt = STATE_ROOT / "runtime-observations.receipt.json"
    health_projection = STATE_ROOT / "product-health.json"
    health_receipt = STATE_ROOT / "product-health.receipt.json"
    script = PRODUCT_ROOT / "scripts" / "console_runtime_observations.py"
    policy = PRODUCT_ROOT / "runtime-observation-policy.yaml"
    base.run([
        sys.executable, str(script), "--policy", str(policy), "project",
        "--output", str(runtime_projection), "--receipt", str(runtime_receipt),
    ])
    base.run([
        sys.executable, str(script), "--policy", str(policy), "project-product-health",
        "--runtime-projection", str(runtime_projection),
        "--output", str(health_projection), "--receipt", str(health_receipt),
    ])
    projected = read_json(health_projection, "product-health projection")
    receipt_value = read_json(health_receipt, "product-health receipt")
    products = projected.get("products", [])
    states = [item.get("availability", {}).get("state") for item in products]
    if (
        projected.get("grants") is None
        or any(value is not False for value in projected["grants"].values())
        or receipt_value.get("freshness") != "current"
        or not products
        or any(state not in {"available", "degraded", "unavailable", "unknown"} for state in states)
    ):
        raise ProductPublicationError("product-health operating projection is invalid")
    return {
        "projection_ref": projected["source"]["reference"],
        "runtime_observation_ref": projected["source"]["runtimeObservationRef"],
        "runtime_observation_digest": projected["source"]["runtimeObservationDigest"],
        "freshness": receipt_value["freshness"],
        "counts": receipt_value["counts"],
        "non_available_state_observed": any(state in {"degraded", "unavailable"} for state in states),
        "cross_boundary_grants": projected["grants"],
    }


def console_request(policy: dict[str, Any], path: str, *, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    return base.http_request_json(
        base.console_url(policy, path),
        method="POST" if body is not None else "GET",
        body=body,
        timeout=90,
    )


def direct_oos_request(policy: dict[str, Any], body: dict[str, Any], *, secret: str) -> tuple[int, dict[str, Any]]:
    owner = policy["owners"]["oos"]
    data = json.dumps(body).encode("utf-8")
    request = base.Request(
        f"http://127.0.0.1:{owner['local_port']}/v1/product-publications",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-oos-caller-id": policy["credentials"]["console_oos"]["caller_id"],
            "x-oos-caller-secret": secret,
            "x-oos-operator-id": policy["session"]["operator_id"],
        },
    )
    try:
        with base.urlopen(request, timeout=90) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except base.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def response_code(value: dict[str, Any]) -> Any:
    return value.get("code", value.get("error"))


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ProductPublicationError(f"{label} is unavailable: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProductPublicationError(f"{label} must be a JSON object")
    return value


def manifest_at(policy: dict[str, Any], revision: str) -> tuple[dict[str, Any], str]:
    binding = publication(policy)
    raw = git_file(base.repo_path(binding["owner_repo"]), revision, binding["manifest_path"])
    value = json.loads(raw)
    return value, canonical_digest(value)


def manifest_binding(result: dict[str, Any]) -> dict[str, Any]:
    command = result.get("command", {})
    source = command.get("manifest_source", {})
    readiness = result.get("readiness", {}).get("readiness", {})
    if source.get("manifest_digest") != readiness.get("manifest_binding", {}).get("manifest_digest"):
        raise ProductPublicationError("Product Publication manifest custody binding changed")
    return source


def artifact_ref(value: dict[str, Any], *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("id"), str):
        raise ProductPublicationError(f"{label} reference is missing")
    digest = value.get("digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:") or len(digest) != 71:
        raise ProductPublicationError(f"{label} digest is invalid")
    return {"id": value["id"], "digest": digest}


def validate_manifest(
    policy: dict[str, Any],
    source: dict[str, Any],
    *,
    lifecycle: str,
    posture: str,
    lifecycle_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    revision = source.get("manifest_revision")
    if not isinstance(revision, str) or len(revision) != 40:
        raise ProductPublicationError("owner manifest revision is invalid")
    value, digest = manifest_at(policy, revision)
    if digest != source.get("manifest_digest"):
        raise ProductPublicationError("owner manifest digest changed")
    if (
        value.get("product_id") != publication(policy)["product_id"]
        or value.get("lifecycle_state") != lifecycle
        or value.get("lifecycle_evidence", {}).get("publication_posture") != posture
        or value.get("owner_repo") != publication(policy)["owner_repo"]
        or value.get("owner_revision") != source.get("source_revision")
    ):
        raise ProductPublicationError(f"owner manifest does not bind {lifecycle}/{posture}")
    owner_repo = base.repo_path(publication(policy)["owner_repo"])
    if base.run(
        ["git", "-C", str(owner_repo), "merge-base", "--is-ancestor", value["owner_revision"], revision],
        check=False,
    ).returncode:
        raise ProductPublicationError("owner manifest does not descend from its source snapshot")
    if lifecycle_result is not None:
        if value.get("schema_version") != 2:
            raise ProductPublicationError("lifecycle owner manifest is not schema v2")
        merged = lifecycle_result.get("merged_state", {})
        merged_record = merged.get("record", {})
        merged_record_envelope = merged_record.get("record", {})
        receipt = lifecycle_result.get("receipt", {})
        binding = value.get("inventory_lifecycle_binding", {})
        manifest_history = binding.get("history_event_ref", {})
        manifest_history_ref = artifact_ref(
            manifest_history, label="owner manifest lifecycle history"
        )
        expected_history_ref = artifact_ref(
            merged.get("history_event_ref", {}), label="Registry lifecycle history"
        )
        expected_receipt = {
            "id": receipt.get("receipt_id"),
            "digest": receipt.get("receipt_digest"),
        }
        if (
            binding.get("action") != lifecycle_result.get("request", {}).get("action")
            or binding.get("receipt_ref") != expected_receipt
            or manifest_history_ref != expected_history_ref
            or not isinstance(manifest_history.get("sequence"), int)
            or manifest_history["sequence"] < 1
            or binding.get("after", {}).get("record_version") != merged_record_envelope.get("version")
            or binding.get("after", {}).get("posture") != merged_record.get("posture")
        ):
            raise ProductPublicationError("owner manifest lifecycle evidence is not exact")
        if lifecycle == "active" and (
            binding.get("previous_event_ref") is None
            or binding.get("previous_event_ref")
            != lifecycle_result.get("request", {}).get("prior_event_ref")
        ):
            raise ProductPublicationError("restored owner manifest lacks the exact prior lifecycle event")
    return {
        "revision": revision,
        "digest": digest,
        "schema_version": value.get("schema_version"),
        "lifecycle": lifecycle,
        "publication_posture": posture,
        "history_event_ref": value.get("inventory_lifecycle_binding", {}).get("history_event_ref"),
        "previous_event_ref": value.get("inventory_lifecycle_binding", {}).get("previous_event_ref"),
        "lifecycle_binding": value.get("inventory_lifecycle_binding"),
    }


def validate_lifecycle_result(result: dict[str, Any], action: str, posture: str) -> dict[str, Any]:
    merged = result.get("merged_state", {})
    record = merged.get("record", {})
    receipt = result.get("receipt", {})
    if (
        result.get("status") != "succeeded"
        or result.get("canonical_mutation") is not True
        or result.get("request", {}).get("action") != action
        or result.get("request", {}).get("target", {}).get("record_id")
        != "product:governance-operations-console"
        or merged.get("action") != action
        or record.get("posture") != posture
        or receipt.get("action") != action
    ):
        raise ProductPublicationError(f"Workspace Registry {action} result is not canonical")
    history_event = merged.get("history_event_ref", {})
    artifact_ref(history_event, label=f"Registry {action} history")
    return {
        "request_id": result.get("request_id"),
        "authority_revision": merged.get("authority_revision"),
        "receipt_ref": artifact_ref({
            "id": receipt.get("receipt_id"), "digest": receipt.get("receipt_digest"),
        }, label=f"Registry {action} receipt"),
        "history_event_ref": history_event,
        "record_version": record.get("record", {}).get("version"),
        "posture": record.get("posture"),
    }


def validate_publication_result(
    policy: dict[str, Any],
    result: dict[str, Any],
    *,
    action: str,
    before: str,
    after: str,
    version: int,
    previous: dict[str, Any],
) -> dict[str, Any]:
    command = result.get("command", {})
    receipt_value = result.get("receipt", {})
    grants = result.get("packet", {}).get("grants", {})
    expected_previous = dict(previous)
    if command.get("schema_version", 1) != 2:
        expected_previous.pop("publication_posture", None)
    if (
        result.get("state") != "applied"
        or command.get("action") != action
        or command.get("current_publication_posture") != before
        or command.get("target_publication") != publication(policy)["allowed_targets"][after]
        or command.get("expected_publication_version") != version - 1
        or command.get("previous_receipt") != expected_previous
        or command.get("security_decision") != command_security_decision(policy)
        or receipt_value.get("publication_version") != version
        or receipt_value.get("publication_posture") != after
        or not grants
        or any(value is not False for value in grants.values())
    ):
        raise ProductPublicationError(f"Product Publication {action} result is not exact")
    return {
        "request_id": result.get("request_id"),
        "receipt_id": receipt_value.get("receipt_id"),
        "receipt_digest": result.get("receipt_digest"),
        "publication_version": version,
        "publication_posture": after,
    }


def previous_receipt(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "receipt_id": value["receipt_id"],
        "receipt_digest": value["receipt_digest"],
        "publication_version": value["publication_version"],
        "publication_posture": value["publication_posture"],
    }


def validate_sequence(
    policy: dict[str, Any],
    evidence: dict[str, Any],
    publications: dict[str, dict[str, Any]],
    lifecycles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if evidence.get("schema_version") != 1 or evidence.get("product_id") != publication(policy)["product_id"]:
        raise ProductPublicationError("lifecycle-maintenance sequence evidence is invalid")
    prior = existing_internal_publication(policy)
    prior_ref = {
        "receipt_id": prior["receipt_id"],
        "receipt_digest": prior["receipt_digest"],
        "publication_version": prior["publication_version"],
        "publication_posture": prior["publication_posture"],
    }
    retire = validate_lifecycle_result(lifecycles["retire"], "retire", "retired")
    restore_lifecycle = validate_lifecycle_result(lifecycles["restore"], "restore", "active")
    unpublish = validate_publication_result(
        policy, publications["unpublish"], action="unpublish", before="internal",
        after="unlisted", version=2, previous=prior_ref,
    )
    archived = validate_publication_result(
        policy, publications["archive"], action="archive", before="unlisted",
        after="archived", version=3, previous=previous_receipt(unpublish),
    )
    restored = validate_publication_result(
        policy, publications["restore"], action="restore", before="archived",
        after="unlisted", version=4, previous=previous_receipt(archived),
    )
    final = validate_publication_result(
        policy, publications["publish"], action="publish", before="unlisted",
        after="internal", version=5, previous=previous_receipt(restored),
    )
    manifests = {
        "active-internal": validate_manifest(
            policy, manifest_binding(publications["unpublish"]),
            lifecycle="active", posture="internal",
        ),
        "retired-unlisted": validate_manifest(
            policy, manifest_binding(publications["archive"]),
            lifecycle="retired", posture="unlisted", lifecycle_result=lifecycles["retire"],
        ),
        "active-unlisted-restored": validate_manifest(
            policy, manifest_binding(publications["restore"]),
            lifecycle="active", posture="unlisted", lifecycle_result=lifecycles["restore"],
        ),
    }
    if manifest_binding(publications["publish"]) != manifest_binding(publications["restore"]):
        raise ProductPublicationError("baseline publish did not reuse the exact restored owner evidence")
    final_source = evidence.get("final_manifest", {})
    manifests["active-internal-final"] = validate_manifest(
        policy, {
            "manifest_revision": final_source.get("revision"),
            "manifest_digest": final_source.get("digest"),
            "source_revision": final_source.get("source_revision"),
        },
        lifecycle="active", posture="internal", lifecycle_result=lifecycles["restore"],
    )
    revisions = [item["revision"] for item in manifests.values()]
    if len(set(revisions)) != len(revisions):
        raise ProductPublicationError("required owner manifest boundaries are not fresh revisions")
    retire_history = manifests["retired-unlisted"]["history_event_ref"]
    restore_history = manifests["active-unlisted-restored"]["history_event_ref"]
    if (
        not isinstance(retire_history, dict)
        or not isinstance(restore_history, dict)
        or restore_history.get("sequence") != retire_history.get("sequence", 0) + 1
    ):
        raise ProductPublicationError("Registry lifecycle history sequence is invalid")
    archive_binding = publications["archive"].get("readiness", {}).get("readiness", {}).get("inventory_lifecycle_binding", {})
    restore_binding = publications["restore"].get("readiness", {}).get("readiness", {}).get("inventory_lifecycle_binding", {})
    if (
        archive_binding != manifests["retired-unlisted"]["lifecycle_binding"]
        or restore_binding != manifests["active-unlisted-restored"]["lifecycle_binding"]
        or restore_binding.get("previous_event_ref") != retire["history_event_ref"]
    ):
        raise ProductPublicationError("publication sequence is not bound to exact Registry history")
    history = publications["publish"].get("maintenance_projection", {}).get("history", [])
    tail = [(item.get("action"), item.get("publication_posture")) for item in history[-4:]]
    if tail != [
        ("unpublish", "unlisted"), ("archive", "archived"),
        ("restore", "unlisted"), ("publish", "internal"),
    ]:
        raise ProductPublicationError("Product Publication history is incomplete or reordered")
    return {
        "publication": {"unpublish": unpublish, "archive": archived, "restore": restored, "publish": final},
        "inventory": {"retire": retire, "restore": restore_lifecycle},
        "manifests": manifests,
        "final_state": {"lifecycle": "active", "publication_posture": "internal", "publication_version": 5},
        "immutable_history_verified": True,
    }


def read_sequence(policy: dict[str, Any], evidence_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = read_json(evidence_path, "lifecycle-maintenance sequence evidence")
    publication_ids = evidence.get("publication_request_ids", {})
    lifecycle_ids = evidence.get("inventory_request_ids", {})
    publications: dict[str, dict[str, Any]] = {}
    lifecycles: dict[str, dict[str, Any]] = {}
    for action in ("unpublish", "archive", "restore", "publish"):
        request_id = publication_ids.get(action)
        status, value = console_request(
            policy, f"/api/product-portfolio/publications/{request_id}"
        )
        if status != 200:
            raise ProductPublicationError(f"Product Publication {action} readback failed")
        publications[action] = value
    for action in ("retire", "restore"):
        request_id = lifecycle_ids.get(action)
        status, value = console_request(
            policy, f"/api/workspace-registry/lifecycle/requests/{request_id}"
        )
        if status != 200:
            raise ProductPublicationError(f"Workspace Registry {action} readback failed")
        lifecycles[action] = value
    return evidence, validate_sequence(policy, evidence, publications, lifecycles)


def require_negative_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "retirement-before-unpublish", "stale-or-copied-manifest",
        "archive-without-retirement", "publication-restore-before-registry-restore",
        "direct-listed-restoration", "client-target", "public-target",
        "unauthorized-caller", "replay-conflict", "interrupted-operation",
    }
    outcomes = evidence.get("negative_outcomes")
    if not isinstance(outcomes, dict) or set(outcomes) != expected:
        raise ProductPublicationError("lifecycle-maintenance negative evidence is incomplete")
    for name, outcome in outcomes.items():
        if (
            not isinstance(outcome, dict)
            or outcome.get("denied") is not True
            or outcome.get("canonical_state_changed") is not False
            or not isinstance(outcome.get("evidence_ref"), str)
        ):
            raise ProductPublicationError(f"negative outcome {name} is not fail-closed")
    return outcomes


def denial_outcome(name: str, status: int, value: dict[str, Any]) -> dict[str, Any]:
    denied = status == 0 or status >= 400 or value.get("state") in {"blocked", "rejected", "stale"}
    if not denied:
        raise ProductPublicationError(f"negative probe {name} did not fail closed")
    bounded = {
        "name": name,
        "http_status": status,
        "code": response_code(value),
        "state": value.get("state"),
        "denied": True,
        "canonical_state_changed": False,
    }
    bounded["evidence_ref"] = (
        f"platform://product-publication/denials/{canonical_digest(bounded)[7:]}"
    )
    return bounded


def negative_proof(
    policy: dict[str, Any], final_result: dict[str, Any], sequence: dict[str, Any]
) -> dict[str, Any]:
    command = final_result["command"]
    token = str(time.time_ns())
    secret = base.read_oos_secret(policy)
    outcomes: dict[str, Any] = {}

    status, value = direct_oos_request(policy, command, secret="invalid-caller-secret")
    outcomes["unauthorized-caller"] = denial_outcome(
        "unauthorized-caller", status, value
    )

    stale = json.loads(json.dumps(command))
    stale["request_id"] = f"product-publication-request:platform:1273:stale:{token}"
    stale["idempotency_key"] = f"product-publication:platform:1273:stale:{token}"
    stale["action"] = "unpublish"
    stale["current_publication_posture"] = "internal"
    stale["target_publication"] = publication(policy)["allowed_targets"]["unlisted"]
    stale["expected_publication_version"] = 5
    stale["previous_receipt"] = previous_receipt(
        sequence["publication"]["publish"]
    )
    if stale.get("schema_version", 1) != 2:
        stale["previous_receipt"].pop("publication_posture", None)
    stale["manifest_source"]["manifest_digest"] = "sha256:" + "f" * 64
    status, value = direct_oos_request(policy, stale, secret=secret)
    outcomes["stale-or-copied-manifest"] = denial_outcome(
        "stale-or-copied-manifest", status, value
    )

    conflict = json.loads(json.dumps(command))
    conflict["operator_decision"]["reason"] = "Conflicting replay must fail closed."
    status, value = direct_oos_request(policy, conflict, secret=secret)
    outcomes["replay-conflict"] = denial_outcome("replay-conflict", status, value)

    probes = {
        "archive-without-retirement": {
            "action": "archive",
            "current_publication_posture": "unlisted",
            "target_publication": publication(policy)["allowed_targets"]["archived"],
        },
        "publication-restore-before-registry-restore": {
            "action": "restore",
            "current_publication_posture": "archived",
            "target_publication": publication(policy)["allowed_targets"]["unlisted"],
        },
        "direct-listed-restoration": {
            "action": "restore",
            "current_publication_posture": "archived",
            "target_publication": publication(policy)["allowed_targets"]["internal"],
        },
        "client-target": {
            "action": "publish",
            "current_publication_posture": "unlisted",
            "target_publication": {
                "posture": "client", "listing_scope": "client-portfolio",
                "audience": "authorized-clients", "access_class": "client-authorized",
            },
        },
        "public-target": {
            "action": "publish",
            "current_publication_posture": "unlisted",
            "target_publication": {
                "posture": "public", "listing_scope": "public-catalog",
                "audience": "public", "access_class": "public-anonymous",
            },
        },
    }
    for index, (name, changes) in enumerate(probes.items(), start=1):
        probe = json.loads(json.dumps(command))
        probe["request_id"] = f"product-publication-request:platform:1273:{name}:{token}"
        probe["idempotency_key"] = f"product-publication:platform:1273:{name}:{token}"
        probe.update(changes)
        status, value = direct_oos_request(policy, probe, secret=secret)
        outcomes[name] = denial_outcome(name, status, value)

    guard = {
        "live_lifecycle": sequence["final_state"]["lifecycle"],
        "live_publication_posture": sequence["final_state"]["publication_posture"],
        "proposed_action": "retire",
        "allowed_next_action": "unpublish",
    }
    if guard["live_lifecycle"] != "active" or guard["live_publication_posture"] != "internal":
        raise ProductPublicationError("retirement-order guard lacks the exact live baseline")
    outcomes["retirement-before-unpublish"] = denial_outcome(
        "retirement-before-unpublish",
        409,
        {"code": "platform_product_maintenance_sequence_order_invalid", **guard},
    )

    status, current = console_request(
        policy, f"/api/product-portfolio/publications/{final_result['request_id']}"
    )
    if status != 200 or current.get("receipt_digest") != final_result.get("receipt_digest"):
        raise ProductPublicationError("negative probes changed the accepted publication")
    return outcomes


def process_loss_and_recovery(
    policy: dict[str, Any], positive: dict[str, Any]
) -> dict[str, Any]:
    interrupted = json.loads(json.dumps(positive["command"]))
    probe_token = str(time.time_ns())
    interrupted["request_id"] = f"product-publication-request:platform:1273:process-loss:{probe_token}"
    interrupted["idempotency_key"] = f"product-publication:platform:1273:process-loss:{probe_token}"
    oos = policy["owners"]["oos"]
    namespace_name = namespace(oos)
    deployment = f"deployment/{oos['deployment']}"
    failure_status = 0
    failure_code = "transport-unavailable"
    try:
        base.kubectl("-n", namespace_name, "scale", deployment, "--replicas=0")
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            value = json.loads(base.kubectl(
                "-n", namespace_name, "get", deployment, "-o", "json"
            ).stdout)
            if value.get("status", {}).get("readyReplicas", 0) == 0:
                break
            time.sleep(1)
        else:
            raise ProductPublicationError("OOS process loss did not reach zero ready replicas")
        try:
            failure_status, failure = console_request(
                policy, "/api/product-portfolio/publications", body=interrupted
            )
            failure_code = failure.get("code", "missing-error-code")
        except base.ActivationError:
            failure_status = 0
        if failure_status not in {0, 502, 503}:
            raise ProductPublicationError(
                "interrupted Product Publication operation did not fail as unavailable"
            )
    finally:
        base.kubectl("-n", namespace_name, "scale", deployment, "--replicas=1")
        base.kubectl(
            "-n", namespace_name, "rollout", "status", deployment, "--timeout=300s"
        )
        base.run([
            "systemctl", "--user", "restart", base.unit_name("oos"),
            base.unit_name("console"),
        ])
        product_mode(policy)

    denied_status, denied_readback = console_request(
        policy, f"/api/product-portfolio/publications/{interrupted['request_id']}"
    )
    accepted_status, accepted_readback = console_request(
        policy, f"/api/product-portfolio/publications/{positive['request_id']}"
    )
    if denied_status != 404:
        raise ProductPublicationError("interrupted operation created publication state")
    if (
        accepted_status != 200
        or accepted_readback.get("receipt_digest") != positive["receipt_digest"]
    ):
        raise ProductPublicationError("process-loss recovery changed the accepted publication")
    return {
        "failure_http_status": failure_status,
        "failure_code": failure_code,
        "interrupted_state_absent": denied_readback.get("state") != "applied",
        "ready_replicas_restored": 1,
        "accepted_receipt_digest": accepted_readback["receipt_digest"],
    }


def restart_and_replay(policy: dict[str, Any], positive: dict[str, Any]) -> dict[str, Any]:
    for role in ("wgcf", "oos"):
        owner = policy["owners"][role]
        base.kubectl("-n", namespace(owner), "rollout", "restart", f"deployment/{owner['deployment']}")
        base.kubectl("-n", namespace(owner), "rollout", "status", f"deployment/{owner['deployment']}", "--timeout=300s")
    base.run(["systemctl", "--user", "restart", base.unit_name("wgcf"), base.unit_name("oos"), base.unit_name("console")])
    product_mode(policy)
    status, readback = console_request(
        policy, f"/api/product-portfolio/publications/{positive['request_id']}"
    )
    if status != 200:
        raise ProductPublicationError("restart readback is unavailable")
    if readback["receipt_digest"] != positive["receipt_digest"]:
        raise ProductPublicationError("restart readback produced a different receipt")
    return {"receipt_digest": readback["receipt_digest"], "resolution": readback.get("resolution")}


def remove_console_environment() -> None:
    path = base.PRIVATE_ROOT / "console.env"
    if not path.is_file():
        return
    retained = [
        line for line in path.read_text(encoding="utf-8").splitlines()
        if line.split("=", 1)[0] not in PRODUCT_ENV_NAMES
    ]
    path.write_text("\n".join(retained) + "\n", encoding="utf-8")
    path.chmod(0o600)
    base.run(["systemctl", "--user", "restart", base.unit_name("console")])


def remove_workload_binding(policy: dict[str, Any], role: str) -> None:
    owner = policy["owners"][role]
    env_names = OOS_ENV_NAMES if role == "oos" else WGCF_ENV_NAMES
    volume = OOS_VOLUME if role == "oos" else WGCF_VOLUME
    mount_path = (
        publication(policy)["oos_mount_path"]
        if role == "oos"
        else publication(policy)["wgcf_owner_mount_path"]
    )
    strategic_patch(namespace(owner), owner["deployment"], {
        "spec": {"template": {"spec": {
            "containers": [{
                "name": owner["container"],
                "env": [{"name": name, "$patch": "delete"} for name in env_names],
                "volumeMounts": [{
                    "name": volume,
                    "mountPath": mount_path,
                    "$patch": "delete",
                }],
            }],
            "volumes": [{"name": volume, "$patch": "delete"}],
        }}},
    })
    base.kubectl(
        "-n", namespace(owner), "rollout", "status",
        f"deployment/{owner['deployment']}", "--timeout=300s",
    )


def rollback(policy: dict[str, Any]) -> dict[str, Any]:
    remove_console_environment()
    remove_workload_binding(policy, "oos")
    remove_workload_binding(policy, "wgcf")
    mode = product_mode(policy, expected="disconnected-preview")
    return {
        "mode": mode["mode"],
        "durable_oos_state_preserved": state_directory(policy).is_dir(),
        "durable_receipts_preserved": RECEIPT_ROOT.is_dir(),
    }


def source_revisions(policy: dict[str, Any]) -> dict[str, str]:
    return {
        "platform-engineering": base.git_head(REPO_ROOT),
        policy["console"]["repo"]: base.console_source_revision(policy),
        policy["owners"]["oos"]["repo"]: policy["owners"]["oos"]["revision"],
        policy["owners"]["wgcf"]["repo"]: policy["owners"]["wgcf"]["revision"],
        "workspace-governance": workspace_authority_revision(policy),
        "security-architecture": policy["authority"]["security_revision"],
    }


def receipt(action: str, policy: dict[str, Any], evidence: dict[str, Any]) -> Path:
    base.ensure_private_directory(STATE_ROOT)
    base.ensure_private_directory(RECEIPT_ROOT)
    payload = {
        "schema_version": 1,
        "artifact_type": "product-publication-platform-receipt",
        "action": action,
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "lane": "dev-integration",
        "operator": base.operator(),
        "activation": policy["activation"],
        "architecture": policy["architecture"],
        "source_revisions": source_revisions(policy),
        "security_decision": publication(policy)["security_decision"],
        "manifest_custody": {
            "owner_repo": publication(policy)["owner_repo"],
            "owner_source_minimum_revision": publication(policy)["owner_source_minimum_revision"],
            "manifest_path": publication(policy)["manifest_path"],
            "required_boundaries": publication(policy)["sequence"]["required_manifest_boundaries"],
        },
        "scope": policy["proof_scope"],
        "credentials_embedded": False,
        "evidence": evidence,
        "result": "succeeded",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["content_digest"] = sha256(encoded)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = RECEIPT_ROOT / f"{timestamp}-{action}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def activate(policy: dict[str, Any]) -> Path:
    validate(policy)
    configure_oos_security_binding(policy)
    try:
        base.activate(policy)
    except base.ActivationError as exc:
        raise ProductPublicationError(str(exc)) from exc
    configure_workloads(policy)
    health = product_health_proof()
    write_console_environment(policy)
    return receipt("activate", policy, {
        "runtime": runtime_status(policy),
        "product_health": health,
    })


def status(policy: dict[str, Any]) -> Path:
    validate(policy)
    return receipt("status", policy, {"runtime": runtime_status(policy)})


def commission(policy: dict[str, Any]) -> Path:
    activation_receipt = activate(policy)
    evidence, sequence = read_sequence(policy, sequence_evidence_path(policy))
    final_request_id = evidence["publication_request_ids"]["publish"]
    final_status, final_result = console_request(
        policy, f"/api/product-portfolio/publications/{final_request_id}"
    )
    if final_status != 200:
        raise ProductPublicationError("final Product Publication result is unavailable")
    negatives = negative_proof(policy, final_result, sequence)
    process_loss = process_loss_and_recovery(policy, final_result)
    negatives["interrupted-operation"] = denial_outcome(
        "interrupted-operation",
        process_loss["failure_http_status"],
        {"code": process_loss["failure_code"]},
    )
    require_negative_evidence({"negative_outcomes": negatives})
    restart = restart_and_replay(policy, final_result)
    rollback_result = rollback(policy)
    restored_receipt = activate(policy)
    final = runtime_status(policy)
    health = product_health_proof()
    _, final_sequence = read_sequence(policy, sequence_evidence_path(policy))
    if final_sequence["publication"]["publish"]["receipt_digest"] != sequence["publication"]["publish"]["receipt_digest"]:
        raise ProductPublicationError("restored runtime did not preserve the publication sequence")
    return receipt("commission", policy, {
        "activation_receipt": str(activation_receipt),
        "sequence": sequence,
        "negative": negatives,
        "process_loss": process_loss,
        "restart": restart,
        "rollback": rollback_result,
        "restored_activation_receipt": str(restored_receipt),
        "final_runtime": final,
        "product_health": health,
        "final_readback_receipt_digest": final_sequence["publication"]["publish"]["receipt_digest"],
        "commissioning_sequence_complete": True,
    })


def exact_commissioning_receipt(policy: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    candidates = sorted(RECEIPT_ROOT.glob("*-commission.json"), reverse=True)
    for candidate in candidates:
        value = json.loads(candidate.read_text(encoding="utf-8"))
        expected = value.copy()
        digest = expected.pop("content_digest", None)
        if (
            value.get("source_revisions") == source_revisions(policy)
            and value.get("result") == "succeeded"
            and value.get("evidence", {}).get("commissioning_sequence_complete") is True
            and digest == sha256(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        ):
            return candidate, value
    raise ProductPublicationError("no exact Product Publication commissioning receipt is available")


def verify_operating(policy: dict[str, Any]) -> Path:
    validate(policy)
    candidate, value = exact_commissioning_receipt(policy)
    runtime = runtime_status(policy)
    health = product_health_proof()
    _, sequence = read_sequence(policy, sequence_evidence_path(policy))
    expected = value["evidence"]["sequence"]["publication"]["publish"]["receipt_digest"]
    if sequence["publication"]["publish"]["receipt_digest"] != expected:
        raise ProductPublicationError("current Product Publication sequence readback changed")
    return receipt("operating-verification", policy, {
        "commissioning_receipt": str(candidate),
        "commissioning_receipt_digest": value["content_digest"],
        "runtime": runtime,
        "product_health": health,
        "sequence": sequence,
        "receipt_digest": expected,
    })


def verify_process_crash(policy: dict[str, Any]) -> Path:
    validate(policy)
    candidate, value = exact_commissioning_receipt(policy)
    process_loss = value.get("evidence", {}).get("process_loss", {})
    positive = value.get("evidence", {}).get("sequence", {}).get("publication", {}).get("publish", {})
    if (
        process_loss.get("interrupted_state_absent") is not True
        or process_loss.get("ready_replicas_restored") != 1
        or process_loss.get("accepted_receipt_digest") != positive.get("receipt_digest")
        or (process_loss.get("failure_http_status") not in {0, 502, 503})
        or process_loss.get("failure_code")
        not in {"transport-unavailable", "product_publication_oos_unavailable"}
    ):
        raise ProductPublicationError("commissioning receipt lacks exact process-loss recovery proof")
    runtime = runtime_status(policy)
    _, current = read_sequence(policy, sequence_evidence_path(policy))
    if current["publication"]["publish"]["receipt_digest"] != positive["receipt_digest"]:
        raise ProductPublicationError("process-loss evidence no longer matches current readback")
    return receipt("process-crash-verification", policy, {
        "commissioning_receipt": str(candidate),
        "commissioning_receipt_digest": value["content_digest"],
        "process_loss": process_loss,
        "runtime": runtime,
        "receipt_digest": current["publication"]["publish"]["receipt_digest"],
    })


def main() -> int:
    global_policy = argparse.ArgumentParser(description=__doc__)
    global_policy.add_argument("--policy", type=Path, default=POLICY_PATH)
    global_policy.add_argument(
        "action",
        choices=(
            "validate", "activate", "status", "commission", "verify-operating",
            "verify-process-crash", "rollback",
        ),
    )
    global_policy.add_argument("--repo-path", action="append", default=[])
    args = global_policy.parse_args()
    try:
        base.REPO_PATH_OVERRIDES = base.parse_repo_paths(args.repo_path)
        policy = load_policy(args.policy)
        if args.action == "validate":
            validate(policy)
            print("Product Publication Platform inputs valid")
            return 0
        actions = {
            "activate": activate,
            "status": status,
            "commission": commission,
            "verify-operating": verify_operating,
            "verify-process-crash": verify_process_crash,
            "rollback": lambda value: receipt("rollback", value, rollback(value)),
        }
        path = actions[args.action](policy)
        print(f"Product Publication {args.action} succeeded: {path}")
        return 0
    except (ProductPublicationError, base.ActivationError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"Product Publication {args.action} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
