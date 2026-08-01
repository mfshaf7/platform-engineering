#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import subprocess
import tempfile
from typing import Any


MAX_DOCUMENT_BYTES = 64 * 1024
MAX_DRAIN_OBSERVATION_AGE_SECONDS = 300
MAX_RETIREMENT_LIFETIME_SECONDS = 900
MAX_REGISTRY_STARTS = 512
MAX_PUBLIC_KEY_BYTES = 16 * 1024
BUSINESS_WORKFLOW_QUEUE_PREFIX = "oos.validation-readiness-run.v1"
START_REGISTRY_QUEUE_PREFIX = "oos.generation-start-registry.v1"
START_REGISTRY_WORKFLOW_ID_PREFIX = "oos:generation-start-registry:v1"
START_REGISTRY_WORKFLOW_TYPE = "generationStartRegistryV1"
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{2,255}$")
URI_RE = re.compile(
    r"^[a-z][a-z0-9+.-]*://[A-Za-z0-9][A-Za-z0-9._~:/@+%-]{2,511}$"
)
ACTIVATION_EVIDENCE_GATES = {
    "activity-idempotency-tested",
    "contract-valid",
    "deterministic-replay-tested",
    "dev-integration-profile-active",
    "failure-and-control-tested",
    "implementation-reviewed",
    "platform-runtime-accepted",
    "rollback-and-suspension-proven",
    "security-review-accepted",
    "source-projection-verified",
}
ACTIVATION_FIELDS = {
    "decision",
    "decision_ref",
    "definition_id",
    "definition_version",
    "environment",
    "evidence",
    "expires_at",
    "issued_at",
    "issued_by",
    "manifest_id",
    "profile_id",
    "profile_lifecycle",
    "schema_version",
    "temporal_target",
}
RETIREMENT_FIELDS = {
    "activation_evidence_digest",
    "activation_manifest_ref",
    "definition_id",
    "definition_version",
    "environment",
    "expires_at",
    "issued_at",
    "issued_by",
    "profile_id",
    "receipt_verification",
    "reason_ref",
    "registry_seal_resume",
    "retirement_id",
    "schema_version",
    "start_ingress",
    "start_registry",
    "temporal_target",
    "workflow_poller",
    "workflow_task_queue",
}
RECEIPT_FIELDS = {
    "attestation",
    "activation_evidence_digest",
    "activation_manifest_ref",
    "cancel_signal_target_count",
    "definition_id",
    "definition_version",
    "environment",
    "ordinary_poller_stopped",
    "outcome",
    "poller_evidence_ref",
    "receipt_id",
    "recorded_at",
    "retirement_evidence_digest",
    "retirement_id",
    "retirement_started_at",
    "schema_version",
    "start_ingress_evidence_ref",
    "start_registry",
    "temporal_target",
    "terminal_projection_count",
    "workflow_task_queue",
}


class ContractError(ValueError):
    pass


def sha256_digest(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ContractError(f"cannot read {path}: {exc}") from exc
    if not raw or len(raw) > MAX_DOCUMENT_BYTES:
        raise ContractError(f"{path} must contain 1-{MAX_DOCUMENT_BYTES} bytes")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractError(f"{path} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{path} must contain a JSON object")
    return value, raw


def load_pinned_json(path: Path, expected_digest: str) -> tuple[dict[str, Any], bytes]:
    require_digest(expected_digest, "configured digest")
    value, raw = load_json(path)
    if sha256_digest(raw) != expected_digest:
        raise ContractError(f"{path} does not match its configured digest")
    return value, raw


def load_ed25519_public_key(path: Path) -> bytes:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ContractError(f"cannot read receipt public key {path}: {exc}") from exc
    if not raw or len(raw) > MAX_PUBLIC_KEY_BYTES:
        raise ContractError("receipt public key has an invalid size")
    result = subprocess.run(
        ["openssl", "pkey", "-pubin", "-in", str(path), "-text", "-noout"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or "ED25519" not in result.stdout.upper():
        raise ContractError("receipt public key must be a valid Ed25519 public key")
    return raw


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def require_exact_fields(value: dict[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise ContractError(f"{name} fields differ: missing={missing}, extra={extra}")


def require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be an object")
    return value


def require_equal(actual: Any, expected: Any, name: str) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise ContractError(f"{name} must be {expected!r}")


def require_digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or DIGEST_RE.fullmatch(value) is None:
        raise ContractError(f"{name} must be a sha256 digest")
    return value


def require_identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or IDENTIFIER_RE.fullmatch(value) is None:
        raise ContractError(f"{name} must be a bounded identifier")
    return value


def require_uri(value: Any, name: str) -> str:
    if not isinstance(value, str) or URI_RE.fullmatch(value) is None:
        raise ContractError(f"{name} must be a bounded URI")
    return value


def require_integer(value: Any, minimum: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContractError(f"{name} must be an integer >= {minimum}")
    return value


def generation_contract(activation_evidence_digest: str) -> dict[str, str]:
    digest = require_digest(
        activation_evidence_digest, "activation_evidence_digest"
    )
    digest_hex = digest.removeprefix("sha256:")
    return {
        "business_workflow_task_queue": (
            f"{BUSINESS_WORKFLOW_QUEUE_PREFIX}.{digest_hex}"
        ),
        "registry_task_queue": f"{START_REGISTRY_QUEUE_PREFIX}.{digest_hex}",
        "registry_workflow_id": (
            f"{START_REGISTRY_WORKFLOW_ID_PREFIX}:{digest_hex}"
        ),
        "registry_workflow_type": START_REGISTRY_WORKFLOW_TYPE,
    }


def parse_timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ContractError(f"{name} must be an RFC3339 UTC timestamp")
    try:
        timestamp = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError as exc:
        raise ContractError(f"{name} must be an RFC3339 UTC timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
        raise ContractError(f"{name} must be an RFC3339 UTC timestamp")
    return timestamp


def validate_activation_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    require_exact_fields(manifest, ACTIVATION_FIELDS, "activation manifest")
    require_equal(manifest["schema_version"], 1, "activation schema_version")
    require_uri(manifest["manifest_id"], "activation manifest_id")
    require_equal(manifest["definition_id"], "validation-readiness-run", "definition_id")
    require_equal(manifest["definition_version"], 1, "definition_version")
    require_equal(manifest["environment"], "dev-integration", "environment")
    require_equal(manifest["profile_id"], "temporal", "profile_id")
    require_equal(manifest["profile_lifecycle"], "active", "profile_lifecycle")
    require_equal(manifest["issued_by"], "platform-engineering", "issued_by")
    require_equal(manifest["decision"], "accepted", "decision")
    require_uri(manifest["decision_ref"], "decision_ref")
    issued_at = parse_timestamp(manifest["issued_at"], "activation issued_at")
    expires_at = parse_timestamp(manifest["expires_at"], "activation expires_at")
    if issued_at > datetime.now(timezone.utc) or expires_at <= issued_at:
        raise ContractError("activation evidence lifetime is invalid")
    evidence = require_object(manifest["evidence"], "activation evidence")
    require_exact_fields(evidence, ACTIVATION_EVIDENCE_GATES, "activation evidence")

    target = require_object(manifest["temporal_target"], "activation temporal_target")
    require_exact_fields(target, {"address", "namespace", "identities"}, "activation target")
    require_identifier(target["address"], "activation target address")
    require_identifier(target["namespace"], "activation target namespace")
    identities = require_object(target["identities"], "activation identities")
    require_exact_fields(identities, {"api", "workflow_worker"}, "activation identities")
    require_equal(identities["api"], "operator-orchestration-service-api", "API identity")
    require_equal(identities["workflow_worker"], "oos-workflow-worker", "worker identity")
    return target


def validate_retirement_manifest(manifest: dict[str, Any]) -> None:
    require_exact_fields(manifest, RETIREMENT_FIELDS, "retirement manifest")
    require_equal(manifest["schema_version"], 1, "retirement schema_version")
    require_uri(manifest["retirement_id"], "retirement_id")
    require_equal(manifest["definition_id"], "validation-readiness-run", "definition_id")
    require_equal(manifest["definition_version"], 1, "definition_version")
    require_equal(manifest["environment"], "dev-integration", "environment")
    require_equal(manifest["profile_id"], "temporal", "profile_id")
    require_equal(manifest["issued_by"], "platform-engineering", "issued_by")
    require_uri(manifest["reason_ref"], "reason_ref")
    require_uri(manifest["activation_manifest_ref"], "activation_manifest_ref")
    generation = generation_contract(manifest["activation_evidence_digest"])
    require_equal(
        manifest["workflow_task_queue"],
        generation["business_workflow_task_queue"],
        "workflow_task_queue",
    )
    require_identifier(manifest["workflow_task_queue"], "workflow_task_queue")
    issued_at = parse_timestamp(manifest["issued_at"], "retirement issued_at")
    expires_at = parse_timestamp(manifest["expires_at"], "retirement expires_at")
    if expires_at <= issued_at:
        raise ContractError("retirement expires_at must follow issued_at")
    if (expires_at - issued_at).total_seconds() > MAX_RETIREMENT_LIFETIME_SECONDS:
        raise ContractError("retirement evidence lifetime must not exceed 900 seconds")

    verification = require_object(
        manifest["receipt_verification"], "receipt_verification"
    )
    require_exact_fields(
        verification,
        {"algorithm", "issuer", "key_id", "public_key_digest"},
        "receipt_verification",
    )
    require_equal(verification["algorithm"], "Ed25519", "receipt algorithm")
    require_equal(
        verification["issuer"],
        "operator-orchestration-service",
        "receipt issuer",
    )
    require_identifier(verification["key_id"], "receipt key_id")
    require_digest(verification["public_key_digest"], "receipt public_key_digest")

    resume = manifest["registry_seal_resume"]
    if resume is not None:
        resume = require_object(resume, "registry_seal_resume")
        require_exact_fields(
            resume,
            {"expires_at", "issued_at", "retirement_evidence_digest"},
            "registry_seal_resume",
        )
        require_digest(
            resume["retirement_evidence_digest"],
            "registry_seal_resume.retirement_evidence_digest",
        )
        resume_issued_at = parse_timestamp(
            resume["issued_at"], "registry_seal_resume.issued_at"
        )
        resume_expires_at = parse_timestamp(
            resume["expires_at"], "registry_seal_resume.expires_at"
        )
        if (
            resume_expires_at <= resume_issued_at
            or (resume_expires_at - resume_issued_at).total_seconds()
            > MAX_RETIREMENT_LIFETIME_SECONDS
        ):
            raise ContractError("registry seal resume lifetime is invalid")

    target = require_object(manifest["temporal_target"], "retirement temporal_target")
    require_exact_fields(
        target,
        {"address", "namespace", "workflow_worker_identity"},
        "retirement target",
    )
    require_identifier(target["address"], "retirement target address")
    require_identifier(target["namespace"], "retirement target namespace")
    require_equal(
        target["workflow_worker_identity"], "oos-workflow-worker", "worker identity"
    )

    ingress = require_object(manifest["start_ingress"], "start_ingress")
    require_exact_fields(
        ingress,
        {"state", "active_replicas", "in_flight_starts", "observed_at", "evidence_ref"},
        "start_ingress",
    )
    require_equal(ingress["state"], "drained", "start_ingress.state")
    require_equal(ingress["active_replicas"], 0, "start_ingress.active_replicas")
    require_equal(ingress["in_flight_starts"], 0, "start_ingress.in_flight_starts")
    require_uri(ingress["evidence_ref"], "start_ingress.evidence_ref")
    require_fresh_observation(
        parse_timestamp(ingress["observed_at"], "start_ingress.observed_at"),
        issued_at,
        "start ingress",
        "issuance",
    )

    registry = require_object(manifest["start_registry"], "start_registry")
    require_exact_fields(
        registry,
        {"workflow_id", "workflow_type", "task_queue"},
        "start_registry",
    )
    require_equal(
        registry["workflow_id"],
        generation["registry_workflow_id"],
        "start_registry.workflow_id",
    )
    require_equal(
        registry["workflow_type"],
        generation["registry_workflow_type"],
        "start_registry.workflow_type",
    )
    require_equal(
        registry["task_queue"],
        generation["registry_task_queue"],
        "start_registry.task_queue",
    )
    require_identifier(registry["workflow_id"], "start_registry.workflow_id")
    require_identifier(registry["task_queue"], "start_registry.task_queue")

    poller = require_object(manifest["workflow_poller"], "workflow_poller")
    require_exact_fields(
        poller,
        {"state", "active_replicas", "observed_at", "evidence_ref"},
        "workflow_poller",
    )
    require_equal(poller["state"], "drained", "workflow_poller.state")
    require_equal(poller["active_replicas"], 0, "workflow_poller.active_replicas")
    require_uri(poller["evidence_ref"], "workflow_poller.evidence_ref")
    require_fresh_observation(
        parse_timestamp(poller["observed_at"], "workflow_poller.observed_at"),
        issued_at,
        "workflow poller",
        "issuance",
    )


def require_fresh_observation(
    observed_at: datetime,
    reference_at: datetime,
    name: str,
    reference_name: str,
) -> None:
    age = (reference_at - observed_at).total_seconds()
    if age < 0:
        raise ContractError(
            f"{name} observation must not follow {reference_name}"
        )
    if age > MAX_DRAIN_OBSERVATION_AGE_SECONDS:
        raise ContractError(
            f"{name} observation must be no more than 300 seconds old at "
            f"{reference_name}"
        )


def atomic_write_json(path: Path, value: dict[str, Any]) -> bytes:
    raw = f"{json.dumps(value, indent=2, sort_keys=True)}\n".encode()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary_name = handle.name
            os.fchmod(handle.fileno(), 0o600)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
        os.chmod(path, 0o600)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
    return raw


def resolve_registry_seal_resume(
    args: argparse.Namespace,
    activation_evidence_digest: str,
) -> dict[str, Any] | None:
    manifest_path = args.resume_seal_manifest
    manifest_digest = args.resume_seal_digest
    if (manifest_path is None) != (manifest_digest is None):
        raise ContractError(
            "resume seal manifest and digest must be supplied together"
        )
    if manifest_path is None:
        return None

    prior, _ = load_pinned_json(manifest_path.resolve(), manifest_digest)
    validate_retirement_manifest(prior)
    require_equal(prior["retirement_id"], args.retirement_id, "resume retirement_id")
    require_equal(
        prior["activation_evidence_digest"],
        activation_evidence_digest,
        "resume activation_evidence_digest",
    )
    prior_resume = prior["registry_seal_resume"]
    if prior_resume is not None:
        return dict(prior_resume)
    return {
        "retirement_evidence_digest": manifest_digest,
        "issued_at": prior["issued_at"],
        "expires_at": prior["expires_at"],
    }


def issue_manifest(args: argparse.Namespace) -> dict[str, Any]:
    activation_path = args.activation_manifest.resolve()
    output_path = args.output.resolve()
    if output_path == activation_path:
        raise ContractError("retirement output must not overwrite activation evidence")
    activation_manifest, _ = load_pinned_json(
        activation_path, args.activation_digest
    )
    target = validate_activation_manifest(activation_manifest)
    require_uri(args.retirement_id, "retirement_id")
    require_uri(args.reason_ref, "reason_ref")
    require_uri(args.start_ingress_evidence_ref, "start_ingress_evidence_ref")
    require_uri(args.workflow_poller_evidence_ref, "workflow_poller_evidence_ref")
    require_identifier(args.receipt_key_id, "receipt_key_id")
    receipt_public_key = load_ed25519_public_key(args.receipt_public_key.resolve())
    if args.start_ingress_active_replicas != 0:
        raise ContractError("start ingress active replicas must be zero")
    if args.in_flight_starts != 0:
        raise ContractError("in-flight starts must be zero")
    if args.workflow_poller_active_replicas != 0:
        raise ContractError("ordinary workflow poller active replicas must be zero")

    issued_at = parse_timestamp(args.issued_at, "issued_at")
    expires_at = parse_timestamp(args.expires_at, "expires_at")
    now = datetime.now(timezone.utc)
    if issued_at > now:
        raise ContractError("issued_at must not be in the future")
    if expires_at <= issued_at or expires_at <= now:
        raise ContractError("expires_at must follow issued_at and remain current")
    start_observed_at = parse_timestamp(
        args.start_ingress_observed_at, "start ingress observed_at"
    )
    poller_observed_at = parse_timestamp(
        args.workflow_poller_observed_at, "workflow poller observed_at"
    )
    if start_observed_at > issued_at or poller_observed_at > issued_at:
        raise ContractError("drain observations must not follow manifest issuance")
    generation = generation_contract(args.activation_digest)
    registry_seal_resume = resolve_registry_seal_resume(
        args,
        args.activation_digest,
    )

    manifest = {
        "schema_version": 1,
        "retirement_id": args.retirement_id,
        "definition_id": "validation-readiness-run",
        "definition_version": 1,
        "environment": "dev-integration",
        "profile_id": "temporal",
        "issued_at": args.issued_at,
        "expires_at": args.expires_at,
        "issued_by": "platform-engineering",
        "receipt_verification": {
            "algorithm": "Ed25519",
            "issuer": "operator-orchestration-service",
            "key_id": args.receipt_key_id,
            "public_key_digest": sha256_digest(receipt_public_key),
        },
        "reason_ref": args.reason_ref,
        "registry_seal_resume": registry_seal_resume,
        "activation_manifest_ref": activation_manifest["manifest_id"],
        "activation_evidence_digest": args.activation_digest,
        "workflow_task_queue": generation["business_workflow_task_queue"],
        "temporal_target": {
            "address": target["address"],
            "namespace": target["namespace"],
            "workflow_worker_identity": target["identities"]["workflow_worker"],
        },
        "start_ingress": {
            "state": "drained",
            "active_replicas": 0,
            "in_flight_starts": 0,
            "observed_at": args.start_ingress_observed_at,
            "evidence_ref": args.start_ingress_evidence_ref,
        },
        "start_registry": {
            "workflow_id": generation["registry_workflow_id"],
            "workflow_type": generation["registry_workflow_type"],
            "task_queue": generation["registry_task_queue"],
        },
        "workflow_poller": {
            "state": "drained",
            "active_replicas": 0,
            "observed_at": args.workflow_poller_observed_at,
            "evidence_ref": args.workflow_poller_evidence_ref,
        },
    }
    validate_retirement_manifest(manifest)
    raw = atomic_write_json(output_path, manifest)
    return {
        "manifest_path": str(output_path),
        "retirement_evidence_digest": sha256_digest(raw),
        "retirement_id": manifest["retirement_id"],
        "start_registry": manifest["start_registry"],
        "workflow_task_queue": manifest["workflow_task_queue"],
    }


def verify_receipt_attestation(
    receipt: dict[str, Any],
    manifest: dict[str, Any],
    public_key_path: Path,
) -> None:
    verification = manifest["receipt_verification"]
    public_key_raw = load_ed25519_public_key(public_key_path)
    require_equal(
        sha256_digest(public_key_raw),
        verification["public_key_digest"],
        "receipt public-key digest",
    )
    attestation = require_object(receipt["attestation"], "receipt attestation")
    require_exact_fields(
        attestation,
        {"algorithm", "issuer", "key_id", "payload_digest", "signature"},
        "receipt attestation",
    )
    for field in ("algorithm", "issuer", "key_id"):
        require_equal(
            attestation[field],
            verification[field],
            f"receipt attestation {field}",
        )
    payload = dict(receipt)
    del payload["attestation"]
    payload_raw = canonical_json(payload)
    require_equal(
        attestation["payload_digest"],
        sha256_digest(payload_raw),
        "receipt attestation payload_digest",
    )
    try:
        signature = base64.b64decode(attestation["signature"], validate=True)
    except (binascii.Error, TypeError) as exc:
        raise ContractError("receipt attestation signature is not valid base64") from exc
    if len(signature) != 64:
        raise ContractError("receipt attestation signature is not Ed25519-sized")

    with tempfile.TemporaryDirectory() as temporary:
        payload_path = Path(temporary) / "payload.json"
        signature_path = Path(temporary) / "signature.bin"
        payload_path.write_bytes(payload_raw)
        signature_path.write_bytes(signature)
        result = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-pubin",
                "-inkey",
                str(public_key_path),
                "-rawin",
                "-in",
                str(payload_path),
                "-sigfile",
                str(signature_path),
            ],
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        raise ContractError("receipt attestation signature verification failed")


def verify_receipt(args: argparse.Namespace) -> dict[str, Any]:
    manifest, _ = load_pinned_json(
        args.retirement_manifest.resolve(), args.retirement_digest
    )
    validate_retirement_manifest(manifest)
    receipt, receipt_raw = load_json(args.receipt.resolve())
    require_exact_fields(receipt, RECEIPT_FIELDS, "retirement receipt")
    verify_receipt_attestation(
        receipt,
        manifest,
        args.receipt_public_key.resolve(),
    )
    require_equal(receipt["schema_version"], 1, "receipt schema_version")
    require_identifier(receipt["receipt_id"], "receipt_id")
    require_equal(receipt["retirement_id"], manifest["retirement_id"], "retirement_id")
    require_equal(
        receipt["retirement_evidence_digest"],
        args.retirement_digest,
        "retirement_evidence_digest",
    )
    for field in (
        "activation_evidence_digest",
        "activation_manifest_ref",
        "definition_id",
        "definition_version",
        "environment",
        "workflow_task_queue",
    ):
        require_equal(receipt[field], manifest[field], field)
    require_equal(receipt["outcome"], "retired", "outcome")
    require_equal(receipt["ordinary_poller_stopped"], True, "ordinary_poller_stopped")
    require_equal(
        receipt["start_ingress_evidence_ref"],
        manifest["start_ingress"]["evidence_ref"],
        "start_ingress_evidence_ref",
    )
    require_equal(
        receipt["poller_evidence_ref"],
        manifest["workflow_poller"]["evidence_ref"],
        "poller_evidence_ref",
    )
    target = require_object(receipt["temporal_target"], "receipt temporal_target")
    require_exact_fields(target, {"address", "namespace"}, "receipt temporal_target")
    require_equal(
        target["address"], manifest["temporal_target"]["address"], "target address"
    )
    require_equal(
        target["namespace"],
        manifest["temporal_target"]["namespace"],
        "target namespace",
    )
    issued_at = parse_timestamp(manifest["issued_at"], "retirement issued_at")
    expires_at = parse_timestamp(manifest["expires_at"], "retirement expires_at")
    started_at = parse_timestamp(
        receipt["retirement_started_at"], "retirement_started_at"
    )
    if started_at < issued_at or started_at >= expires_at:
        raise ContractError(
            "retirement_started_at must fall within the manifest lifetime"
        )

    registry = require_object(receipt["start_registry"], "receipt start_registry")
    require_exact_fields(
        registry,
        {
            "workflow_id",
            "workflow_type",
            "task_queue",
            "seal_ref",
            "sealed_at",
            "result_digest",
            "registered_workflow_count",
            "matched_execution_count",
            "uncommitted_registration_count",
            "seal_authorization_digest",
        },
        "receipt start_registry",
    )
    for field in ("workflow_id", "workflow_type", "task_queue"):
        require_equal(
            registry[field],
            manifest["start_registry"][field],
            f"start_registry.{field}",
        )
    require_equal(
        registry["seal_ref"], manifest["retirement_id"], "start_registry.seal_ref"
    )
    require_digest(
        registry["seal_authorization_digest"],
        "start_registry.seal_authorization_digest",
    )
    require_digest(registry["result_digest"], "start_registry.result_digest")
    sealed_at = parse_timestamp(registry["sealed_at"], "start_registry.sealed_at")
    seal_issued_at = issued_at
    seal_expires_at = expires_at
    if registry["seal_authorization_digest"] != args.retirement_digest:
        resume = manifest["registry_seal_resume"]
        if resume is None:
            raise ContractError(
                "start registry seal is not authorized by this manifest"
            )
        require_equal(
            registry["seal_authorization_digest"],
            resume["retirement_evidence_digest"],
            "start_registry.seal_authorization_digest",
        )
        seal_issued_at = parse_timestamp(
            resume["issued_at"], "registry_seal_resume.issued_at"
        )
        seal_expires_at = parse_timestamp(
            resume["expires_at"], "registry_seal_resume.expires_at"
        )
    if (
        sealed_at < seal_issued_at
        or sealed_at >= seal_expires_at
        or sealed_at > started_at
    ):
        raise ContractError(
            "start_registry.sealed_at must fall inside its seal authorization before retirement start"
        )
    registered_count = require_integer(
        registry["registered_workflow_count"],
        0,
        "start_registry.registered_workflow_count",
    )
    if registered_count > MAX_REGISTRY_STARTS:
        raise ContractError(
            f"start registry cannot exceed {MAX_REGISTRY_STARTS} registrations"
        )
    matched_count = require_integer(
        registry["matched_execution_count"],
        0,
        "start_registry.matched_execution_count",
    )
    uncommitted_count = require_integer(
        registry["uncommitted_registration_count"],
        0,
        "start_registry.uncommitted_registration_count",
    )
    if matched_count + uncommitted_count != registered_count:
        raise ContractError(
            "start registry reconciliation counts do not cover every registration"
        )
    cancel_count = require_integer(
        receipt["cancel_signal_target_count"], 0, "cancel_signal_target_count"
    )
    terminal_count = require_integer(
        receipt["terminal_projection_count"], 0, "terminal_projection_count"
    )
    if cancel_count > matched_count:
        raise ContractError("cancellation targets exceed matched registry executions")
    if terminal_count != matched_count:
        raise ContractError(
            "every matched registry execution must have a terminal projection"
        )
    require_fresh_observation(
        parse_timestamp(
            manifest["start_ingress"]["observed_at"],
            "start_ingress.observed_at",
        ),
        started_at,
        "start ingress",
        "retirement start",
    )
    require_fresh_observation(
        parse_timestamp(
            manifest["workflow_poller"]["observed_at"],
            "workflow_poller.observed_at",
        ),
        started_at,
        "workflow poller",
        "retirement start",
    )
    recorded_at = parse_timestamp(receipt["recorded_at"], "recorded_at")
    if recorded_at < started_at:
        raise ContractError("receipt recorded_at must not precede retirement start")
    if recorded_at > datetime.now(timezone.utc):
        raise ContractError("receipt recorded_at must not be in the future")
    return {
        "decision": "accepted",
        "receipt_digest": sha256_digest(receipt_raw),
        "receipt_id": receipt["receipt_id"],
        "retirement_id": receipt["retirement_id"],
        "start_registry": {
            "workflow_id": registry["workflow_id"],
            "result_digest": registry["result_digest"],
            "registered_workflow_count": registered_count,
            "matched_execution_count": matched_count,
            "uncommitted_registration_count": uncommitted_count,
        },
        "workflow_task_queue": receipt["workflow_task_queue"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Issue and verify Platform-owned Temporal generation retirement evidence."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    issue = subparsers.add_parser(
        "issue", help="Issue one digest-pinned retirement manifest."
    )
    issue.add_argument("--activation-manifest", type=Path, required=True)
    issue.add_argument("--activation-digest", required=True)
    issue.add_argument("--retirement-id", required=True)
    issue.add_argument("--reason-ref", required=True)
    issue.add_argument("--receipt-key-id", required=True)
    issue.add_argument("--receipt-public-key", type=Path, required=True)
    issue.add_argument("--resume-seal-manifest", type=Path)
    issue.add_argument("--resume-seal-digest")
    issue.add_argument("--issued-at", required=True)
    issue.add_argument("--expires-at", required=True)
    issue.add_argument("--start-ingress-active-replicas", type=int, required=True)
    issue.add_argument("--in-flight-starts", type=int, required=True)
    issue.add_argument("--start-ingress-observed-at", required=True)
    issue.add_argument("--start-ingress-evidence-ref", required=True)
    issue.add_argument("--workflow-poller-active-replicas", type=int, required=True)
    issue.add_argument("--workflow-poller-observed-at", required=True)
    issue.add_argument("--workflow-poller-evidence-ref", required=True)
    issue.add_argument("--output", type=Path, required=True)
    issue.set_defaults(handler=issue_manifest)

    verify = subparsers.add_parser(
        "verify-receipt",
        help="Verify an OOS retirement receipt against its exact manifest.",
    )
    verify.add_argument("--retirement-manifest", type=Path, required=True)
    verify.add_argument("--retirement-digest", required=True)
    verify.add_argument("--receipt", type=Path, required=True)
    verify.add_argument("--receipt-public-key", type=Path, required=True)
    verify.set_defaults(handler=verify_receipt)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        result = args.handler(args)
    except ContractError as exc:
        print(f"generation-retirement: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
