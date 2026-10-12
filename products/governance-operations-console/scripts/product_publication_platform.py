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
        or activation.get("work_item_ref") != "openproject://work_packages/1264"
        or activation.get("security_gate_id")
        != "gate:product-publication-audience-activation"
    ):
        raise ProductPublicationError("Product Publication activation binding is not exact")
    if binding.get("target") != {
        "posture": "internal",
        "listing_scope": "workspace-portfolio",
        "audience": "workspace-operators",
        "access_class": "workspace-authenticated",
    }:
        raise ProductPublicationError("only the approved internal publication tuple is allowed")
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
    security = binding.get("security_decision") or {}
    if (
        security.get("revision") != policy["authority"]["security_revision"]
        or security.get("uri")
        != "security-architecture://product-publication/decisions/audience-internal-only-v1"
        or security.get("approved_target_postures") != ["internal"]
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
    reviewed_manifest_revision = binding.get("security_reviewed_manifest_revision")
    manifest_bytes = git_file(
        owner_repo, binding["manifest_revision"], binding["manifest_path"]
    )
    if (
        binding["manifest_revision"] != policy["console"]["revision"]
        or reviewed_manifest_revision
        not in policy["architecture"].get("security_review_revisions", [])
        or base.run(
            [
                "git", "-C", str(owner_repo), "merge-base", "--is-ancestor",
                reviewed_manifest_revision, binding["manifest_revision"],
            ],
            check=False,
        ).returncode
        or git_file(owner_repo, reviewed_manifest_revision, binding["manifest_path"])
        != manifest_bytes
    ):
        raise ProductPublicationError(
            "Product Publication runtime manifest does not preserve its Security-reviewed bytes"
        )
    manifest = json.loads(manifest_bytes)
    if canonical_digest(manifest) != binding.get("manifest_digest"):
        raise ProductPublicationError("Product Publication owner manifest digest changed")
    if (
        manifest.get("product_id") != binding.get("product_id")
        or manifest.get("owner_revision") != binding.get("owner_source_revision")
    ):
        raise ProductPublicationError("Product Publication owner manifest binding changed")
    if base.run(
        [
            "git", "-C", str(owner_repo), "merge-base", "--is-ancestor",
            binding["owner_source_revision"], binding["manifest_revision"],
        ],
        check=False,
    ).returncode:
        raise ProductPublicationError("owner manifest does not descend from its source snapshot")
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
            owner_manifest.get("allowed_target_postures") != ["internal"]
            or owner_manifest.get("security_authority") != {
                "decision_uri": security["uri"],
                "decision_digest": security["digest"],
                "decision_revision": security["revision"],
                "approved_target_postures": ["internal"],
            }
            or owner_manifest.get("activation_prerequisites") != {
                "security_work_item": "openproject://work_packages/1262",
                "platform_work_item": "openproject://work_packages/1264",
            }
        ):
            raise ProductPublicationError("OOS Product Publication audience activation is not exact")


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


def strategic_patch(namespace_name: str, deployment: str, value: dict[str, Any]) -> None:
    base.kubectl(
        "-n", namespace_name, "patch", f"deployment/{deployment}",
        "--type=strategic", "-p", json.dumps(value, separators=(",", ":")),
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
    retained.extend([
        f"GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_AUTHORITY_REVISION={binding['authority_revision']}",
        f"GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_SECURITY_DECISION_URI={binding['security_decision']['uri']}",
        f"GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_SECURITY_DECISION_DIGEST={binding['security_decision']['digest']}",
        f"GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_SECURITY_DECISION_REVISION={binding['security_decision']['revision']}",
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


def proof_intent(policy: dict[str, Any]) -> dict[str, Any]:
    base.ensure_private_directory(STATE_ROOT)
    binding = publication(policy)
    proof_identity = hashlib.sha256(
        f"{binding['authority_revision']}:{binding['manifest_digest']}".encode("utf-8")
    ).hexdigest()[:12]
    request_id = f"product-publication-request:platform:1264:{proof_identity}"
    idempotency_key = f"product-publication:platform:1264:{proof_identity}"
    if INTENT_PATH.is_file():
        value = json.loads(INTENT_PATH.read_text(encoding="utf-8"))
        if (
            isinstance(value, dict)
            and value.get("request_id") == request_id
            and value.get("idempotency_key") == idempotency_key
            and value.get("manifest_source", {}).get("manifest_digest")
            == binding["manifest_digest"]
        ):
            return value
        superseded = STATE_ROOT / f"proof-intent-superseded-{canonical_digest(value)[7:19]}.json"
        INTENT_PATH.replace(superseded)
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    value = {
        "action": "publish",
        "current_publication_posture": "unlisted",
        "decided_at": now,
        "expected_publication_version": 0,
        "idempotency_key": idempotency_key,
        "manifest_source": {
            "manifest_digest": binding["manifest_digest"],
            "manifest_revision": binding["manifest_revision"],
            "path": binding["manifest_path"],
            "repo": binding["owner_repo"],
            "source_revision": binding["owner_source_revision"],
        },
        "operator_reason": "Exercise bounded Product Publication evidence for Platform work item 1264 without changing the accepted publication.",
        "previous_receipt": None,
        "request_id": request_id,
        "requested_at": now,
        "target_publication": binding["target"],
    }
    INTENT_PATH.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    INTENT_PATH.chmod(0o600)
    return value


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


def positive_proof(policy: dict[str, Any]) -> dict[str, Any]:
    prior = existing_internal_publication(policy)
    deadline = time.monotonic() + 60
    while True:
        status, created = console_request(
            policy, f"/api/product-portfolio/publications/{prior['request_id']}"
        )
        if (
            status not in {502, 503}
            or created.get("retryable") is not True
            or time.monotonic() >= deadline
        ):
            break
        time.sleep(2)
    if (
        status != 200
        or created.get("state") != "applied"
        or created.get("command_digest") != prior["command_digest"]
        or created.get("receipt_digest") != prior["receipt_digest"]
        or created.get("receipt", {}).get("receipt_id") != prior["receipt_id"]
        or created.get("receipt", {}).get("publication_posture")
        != prior["publication_posture"]
        or created.get("receipt", {}).get("publication_version")
        != prior["publication_version"]
        or created.get("command", {}).get("security_decision")
        != prior["security_decision"]
    ):
        raise ProductPublicationError(
            f"existing internal Product Publication readback failed: {status} "
            f"{created.get('code', created.get('state'))}"
        )
    grants = created.get("packet", {}).get("grants", {})
    if not grants or any(value is not False for value in grants.values()):
        raise ProductPublicationError("Product Publication result grants cross-boundary authority")
    request_id = prior["request_id"]
    read_status, readback = console_request(
        policy, f"/api/product-portfolio/publications/{request_id}"
    )
    if (
        read_status != 200
        or readback.get("receipt_digest") != created.get("receipt_digest")
        or readback.get("receipt", {}).get("publication_posture") != "internal"
        or readback.get("receipt", {}).get("publication_version") != 1
    ):
        raise ProductPublicationError("Product Publication durable readback is inconsistent")
    return {
        "request_id": request_id,
        "receipt_id": created["receipt"]["receipt_id"],
        "receipt_digest": created["receipt_digest"],
        "owner_receipt_ref": created["receipt"]["owner_receipt_ref"],
        "readiness_receipt_ref": created["packet"]["authority_refs"]["readiness_receipt_ref"],
        "publication_version": 1,
        "publication_posture": "internal",
        "publication_security_decision": prior["security_decision"],
        "runtime_security_decision": publication(policy)["security_decision"],
        "cross_boundary_grants": grants,
        "resolution": created.get("resolution"),
        "command": created["command"],
    }


def negative_proof(policy: dict[str, Any], positive: dict[str, Any]) -> dict[str, Any]:
    intent = proof_intent(policy)
    probe_token = str(time.time_ns())
    outcomes: dict[str, Any] = {}
    status, value = direct_oos_request(policy, positive["command"], secret="invalid-caller-secret")
    outcomes["unauthorized-caller"] = {"http_status": status, "code": response_code(value)}

    contradictory = json.loads(json.dumps(positive["command"]))
    contradictory["request_id"] = f"{intent['request_id']}:security-mismatch:{probe_token}"
    contradictory["idempotency_key"] = f"{intent['idempotency_key']}:security-mismatch:{probe_token}"
    contradictory["security_decision"]["digest"] = "sha256:" + "0" * 64
    status, value = direct_oos_request(policy, contradictory, secret=base.read_oos_secret(policy))
    outcomes["security-mismatch"] = {"http_status": status, "code": response_code(value)}

    stale = json.loads(json.dumps(intent))
    stale["request_id"] = f"{intent['request_id']}:stale-manifest:{probe_token}"
    stale["idempotency_key"] = f"{intent['idempotency_key']}:stale-manifest:{probe_token}"
    stale["manifest_source"]["manifest_digest"] = "sha256:" + "f" * 64
    status, value = console_request(policy, "/api/product-portfolio/publications", body=stale)
    outcomes["stale-manifest"] = {
        "http_status": status,
        "code": response_code(value),
        "provider_error": value.get("error"),
        "state": value.get("state"),
    }

    conflict = json.loads(json.dumps(positive["command"]))
    conflict["security_decision"] = command_security_decision(policy)
    conflict["operator_decision"]["reason"] = "Conflicting replay must fail."
    status, value = direct_oos_request(
        policy, conflict, secret=base.read_oos_secret(policy)
    )
    outcomes["replay-conflict"] = {"http_status": status, "code": response_code(value)}

    denied_targets = {
        "unlisted": {
            "action": "unpublish",
            "current_publication_posture": "internal",
            "target_publication": {
                "posture": "unlisted",
                "listing_scope": None,
                "audience": None,
                "access_class": None,
            },
        },
        "client": {
            "action": "publish",
            "current_publication_posture": "unlisted",
            "target_publication": {
                "posture": "client",
                "listing_scope": "client-portfolio",
                "audience": "authorized-clients",
                "access_class": "client-authorized",
            },
        },
        "public": {
            "action": "publish",
            "current_publication_posture": "unlisted",
            "target_publication": {
                "posture": "public",
                "listing_scope": "public-catalog",
                "audience": "public",
                "access_class": "public-anonymous",
            },
        },
        "archived": {
            "action": "archive",
            "current_publication_posture": "unlisted",
            "target_publication": {
                "posture": "archived",
                "listing_scope": "historical-archive",
                "audience": "historical",
                "access_class": "historical-read-only",
            },
        },
    }
    for posture, changes in denied_targets.items():
        denied = json.loads(json.dumps(positive["command"]))
        denied["request_id"] = f"{intent['request_id']}:{posture}-denied:{probe_token}"
        denied["idempotency_key"] = f"{intent['idempotency_key']}:{posture}-denied:{probe_token}"
        denied["security_decision"] = command_security_decision(policy)
        denied.update(changes)
        status, value = direct_oos_request(
            policy, denied, secret=base.read_oos_secret(policy)
        )
        outcomes[f"target-{posture}"] = {
            "http_status": status,
            "code": response_code(value),
        }

    if (
        outcomes["unauthorized-caller"]["http_status"] != 401
        or outcomes["unauthorized-caller"]["code"] != "caller_auth_invalid"
    ):
        raise ProductPublicationError("unauthorized Product Publication caller did not fail closed")
    if (
        outcomes["security-mismatch"]["http_status"] != 403
        or outcomes["security-mismatch"]["code"]
        != "product_publication_security_decision_mismatch"
    ):
        raise ProductPublicationError("contradictory Security decision did not fail closed")
    if (
        outcomes["stale-manifest"]["http_status"] != 502
        or outcomes["stale-manifest"]["provider_error"]
        != "product_publication_readiness_mismatch"
    ):
        raise ProductPublicationError("stale owner manifest did not fail closed")
    if (
        outcomes["replay-conflict"]["http_status"] != 409
        or outcomes["replay-conflict"]["code"]
        != "product_publication_idempotency_conflict"
    ):
        raise ProductPublicationError("conflicting Product Publication replay did not fail closed")
    for posture in denied_targets:
        outcome = outcomes[f"target-{posture}"]
        if (
            outcome["http_status"] < 400
            or outcome["code"] != "product_publication_target_posture_not_approved"
        ):
            raise ProductPublicationError(
                f"unapproved Product Publication target {posture} did not fail closed"
            )
    status, readback = console_request(
        policy, f"/api/product-portfolio/publications/{positive['request_id']}"
    )
    if status != 200 or readback.get("receipt_digest") != positive["receipt_digest"]:
        raise ProductPublicationError("negative cases changed the accepted publication")
    return outcomes


def process_loss_and_recovery(
    policy: dict[str, Any], positive: dict[str, Any]
) -> dict[str, Any]:
    intent = proof_intent(policy)
    interrupted = json.loads(json.dumps(intent))
    probe_token = str(time.time_ns())
    interrupted["request_id"] = f"{intent['request_id']}:process-loss:{probe_token}"
    interrupted["idempotency_key"] = f"{intent['idempotency_key']}:process-loss:{probe_token}"
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
    readback = positive_proof(policy)
    if readback["receipt_digest"] != positive["receipt_digest"]:
        raise ProductPublicationError("restart readback produced a different receipt")
    return {"receipt_digest": readback["receipt_digest"], "resolution": "read"}


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
        policy["console"]["repo"]: policy["console"]["revision"],
        policy["owners"]["oos"]["repo"]: policy["owners"]["oos"]["revision"],
        policy["owners"]["wgcf"]["repo"]: policy["owners"]["wgcf"]["revision"],
        "workspace-governance": publication(policy)["authority_revision"],
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
        "manifest_binding": {
            key: publication(policy)[key]
            for key in ("owner_repo", "owner_source_revision", "manifest_revision", "manifest_path", "manifest_digest")
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
    try:
        base.activate(policy)
    except base.ActivationError as exc:
        raise ProductPublicationError(str(exc)) from exc
    configure_workloads(policy)
    write_console_environment(policy)
    return receipt("activate", policy, {"runtime": runtime_status(policy)})


def status(policy: dict[str, Any]) -> Path:
    validate(policy)
    return receipt("status", policy, {"runtime": runtime_status(policy)})


def commission(policy: dict[str, Any]) -> Path:
    activation_receipt = activate(policy)
    positive = positive_proof(policy)
    negatives = negative_proof(policy, positive)
    process_loss = process_loss_and_recovery(policy, positive)
    restart = restart_and_replay(policy, positive)
    rollback_result = rollback(policy)
    restored_receipt = activate(policy)
    final = runtime_status(policy)
    final_read = positive_proof(policy)
    if final_read["receipt_digest"] != positive["receipt_digest"]:
        raise ProductPublicationError("restored runtime did not preserve the publication receipt")
    return receipt("commission", policy, {
        "activation_receipt": str(activation_receipt),
        "positive": {key: value for key, value in positive.items() if key != "command"},
        "negative": negatives,
        "process_loss": process_loss,
        "restart": restart,
        "rollback": rollback_result,
        "restored_activation_receipt": str(restored_receipt),
        "final_runtime": final,
        "final_readback_receipt_digest": final_read["receipt_digest"],
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
    positive = positive_proof(policy)
    if positive["receipt_digest"] != value["evidence"]["positive"]["receipt_digest"]:
        raise ProductPublicationError("current Product Publication readback changed")
    return receipt("operating-verification", policy, {
        "commissioning_receipt": str(candidate),
        "commissioning_receipt_digest": value["content_digest"],
        "runtime": runtime,
        "receipt_digest": positive["receipt_digest"],
    })


def verify_process_crash(policy: dict[str, Any]) -> Path:
    validate(policy)
    candidate, value = exact_commissioning_receipt(policy)
    process_loss = value.get("evidence", {}).get("process_loss", {})
    positive = value.get("evidence", {}).get("positive", {})
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
    current = positive_proof(policy)
    if current["receipt_digest"] != positive["receipt_digest"]:
        raise ProductPublicationError("process-loss evidence no longer matches current readback")
    return receipt("process-crash-verification", policy, {
        "commissioning_receipt": str(candidate),
        "commissioning_receipt_digest": value["content_digest"],
        "process_loss": process_loss,
        "runtime": runtime,
        "receipt_digest": current["receipt_digest"],
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
