#!/usr/bin/env python3
"""Apply reviewed OOS model-profile requests to Platform-owned source contracts."""

from __future__ import annotations

import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
import yaml

from validate_ai_model_profiles import validate as validate_ai_model_profiles


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = Path("security/governed-ai-model-profiles.yaml")
ACCESS_PLANE = Path("security/governed-ai-access-plane.yaml")
RUNTIME_ASSIST = Path("security/governed-ai-runtime-assist-contract.yaml")
SOURCE_LOCK = Path("security/model-profile-request-source-lock.json")
DECISION_SCHEMA = Path("security/schemas/model-profile-lifecycle-decision.schema.json")
RECEIPT_SCHEMA = Path("security/schemas/model-profile-lifecycle-receipt.schema.json")
PROJECTION_SCHEMA = Path("security/schemas/model-profile-source-projection.schema.json")
OPERATING_SCHEMA = Path("security/schemas/model-profile-operating-proof.schema.json")
ACTOR_ID = "platform-engineering/model-profile-lifecycle"
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


class LifecycleError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest_value(value: Any, omitted_field: str | None = None) -> str:
    projection = copy.deepcopy(value)
    if omitted_field and isinstance(projection, dict):
        projection.pop(omitted_field, None)
    return "sha256:" + hashlib.sha256(canonical_json(projection)).hexdigest()


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"unable to read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LifecycleError(f"{path} must contain a JSON object")
    return value


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise LifecycleError(f"unable to read YAML {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LifecycleError(f"{path} must contain a YAML mapping")
    return value


def validate_schema(value: dict[str, Any], schema_path: Path, *, label: str) -> None:
    schema = read_json(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        detail = "; ".join(
            f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise LifecycleError(f"invalid {label}: {detail}")


def git_show(repo: Path, revision: str, relative_path: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), "show", f"{revision}:{relative_path}"],
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise LifecycleError(
            f"unable to resolve locked OOS source {revision}:{relative_path}"
        )
    return completed.stdout


def load_oos_schemas(repo_root: Path, oos_repo_root: Path) -> dict[str, dict[str, Any]]:
    lock = read_json(repo_root / SOURCE_LOCK)
    if lock.get("schema_version") != 1 or lock.get("owner_repo") != "operator-orchestration-service":
        raise LifecycleError("model-profile request source lock has invalid authority metadata")
    revision = str(lock.get("git_commit") or "")
    if not COMMIT.fullmatch(revision):
        raise LifecycleError("model-profile request source lock must pin a full OOS commit")
    root = str(lock.get("root") or "").strip("/")
    files = lock.get("files")
    if not isinstance(files, dict) or not files:
        raise LifecycleError("model-profile request source lock has no files")
    documents: dict[str, dict[str, Any]] = {}
    for name, expected in files.items():
        if not isinstance(name, str) or "/" in name or not isinstance(expected, str):
            raise LifecycleError("model-profile request source lock contains an invalid file entry")
        content = git_show(oos_repo_root, revision, f"{root}/{name}")
        if digest_bytes(content) != f"sha256:{expected}":
            raise LifecycleError(f"locked OOS model-profile contract digest is stale: {name}")
        try:
            document = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LifecycleError(f"locked OOS model-profile contract is invalid JSON: {name}") from exc
        if not isinstance(document, dict):
            raise LifecycleError(f"locked OOS model-profile contract must be an object: {name}")
        documents[name] = document
    manifest = documents.get("manifest.json") or {}
    if manifest.get("contract_id") != lock.get("contract_id") or manifest.get("files") != {
        name: digest for name, digest in files.items() if name != "manifest.json"
    }:
        raise LifecycleError("locked OOS manifest does not match the Platform source lock")
    return {name: value for name, value in documents.items() if name.endswith(".schema.json")}


def validate_oos_projection(projection: dict[str, Any], schemas: dict[str, dict[str, Any]]) -> None:
    schema = schemas.get("projection.schema.json")
    if not schema:
        raise LifecycleError("locked OOS projection schema is missing")
    registry = Registry().with_resources(
        (str(document["$id"]), Resource.from_contents(document))
        for document in schemas.values()
    )
    errors = sorted(
        Draft202012Validator(
            schema, registry=registry, format_checker=FormatChecker()
        ).iter_errors(projection),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        detail = "; ".join(
            f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise LifecycleError(f"invalid OOS model-profile projection: {detail}")
    receipt = projection["latest_receipt"]
    if digest_value(receipt, "digest") != receipt["digest"]:
        raise LifecycleError("OOS latest receipt digest is false")
    latest_event = projection["history"][-1]
    if latest_event["receipt_ref"]["digest"] != receipt["digest"]:
        raise LifecycleError("OOS history does not bind the latest receipt")


def source_state(repo_root: Path, *, source_version: str | None = None) -> dict[str, str]:
    values = {
        "registry_digest": digest_bytes((repo_root / REGISTRY).read_bytes()),
        "access_plane_digest": digest_bytes((repo_root / ACCESS_PLANE).read_bytes()),
        "runtime_assist_digest": digest_bytes((repo_root / RUNTIME_ASSIST).read_bytes()),
    }
    combined = digest_value(values)
    values["source_version"] = source_version or f"platform-source:{combined[7:31]}"
    return values


def clean_git_head(repo_root: Path) -> str:
    head = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    status = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        text=True,
        capture_output=True,
        check=False,
    )
    if head.returncode or status.returncode or not COMMIT.fullmatch(head.stdout.strip()):
        raise LifecycleError("operation requires a valid Platform git worktree")
    if status.stdout.strip():
        raise LifecycleError("operation requires a clean Platform git worktree")
    return head.stdout.strip()


def assert_time_order(earlier: str, later: str) -> None:
    try:
        first = datetime.fromisoformat(earlier.replace("Z", "+00:00"))
        second = datetime.fromisoformat(later.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LifecycleError("lifecycle timestamps must be RFC 3339 date-times") from exc
    if second < first:
        raise LifecycleError("Platform decision timestamp precedes the authoritative OOS receipt")


def recursive_secret_keys(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}/{key}"
            lowered = key.casefold()
            if any(marker in lowered for marker in ("password", "api_key", "token_value", "secret_value")):
                found.append(child_path)
            found.extend(recursive_secret_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(recursive_secret_keys(child, f"{path}/{index}"))
    return found


def validate_handoff(
    projection: dict[str, Any], decision: dict[str, Any], current_source: dict[str, str]
) -> tuple[str, dict[str, Any]]:
    request = projection["request"]
    receipt = projection["latest_receipt"]
    if projection["review_state"] != "approved":
        raise LifecycleError("OOS request must be approved before Platform fulfillment")
    if projection["fulfillment_state"] != "implementing":
        raise LifecycleError("OOS fulfillment must be implementing before Platform source mutation")
    if projection["profile_lifecycle_changed"] is not False:
        raise LifecycleError("OOS projection falsely claims a profile lifecycle mutation")
    bindings = {
        "request_id": projection["request_id"],
        "request_revision": projection["revision"],
        "request_receipt_digest": receipt["digest"],
        "intent": request["intent"],
    }
    for field, expected in bindings.items():
        if decision.get(field) != expected:
            raise LifecycleError(f"Platform decision has stale or mismatched {field}")
    if decision["expected_sources"] != current_source:
        raise LifecycleError("Platform decision source binding is stale")
    assert_time_order(receipt["recorded_at"], decision["recorded_at"])
    intent = request["intent"]
    profile_id = decision["profile_id"]
    requested_id = request["profile_intent"]["profile_id"]
    if intent == "create":
        if requested_id is not None:
            raise LifecycleError("create request must leave canonical profile_id assignment to Platform")
    elif requested_id != profile_id:
        raise LifecycleError("Platform profile_id does not match the approved request")
    request_source = request["profile_intent"]["source"]
    if intent == "create":
        if request_source is not None:
            raise LifecycleError("create request must not claim an existing Platform source")
    elif (
        request_source is None
        or request_source["source_version"] != current_source["source_version"]
        or request_source["registry_ref"]["digest"] != current_source["registry_digest"]
    ):
        raise LifecycleError("approved request is bound to stale Platform registry source")
    if intent in {"activate", "exception"} and decision["security_decision_ref"] is None:
        raise LifecycleError(f"{intent} requires an exact Security decision reference")
    if intent not in {"activate", "exception"} and decision["security_decision_ref"] is not None:
        raise LifecycleError("Security decision reference is only accepted for activate or exception")
    target = decision["target_profile"]
    if intent in {"create", "amend", "activate", "exception"} and not isinstance(target, dict):
        raise LifecycleError(f"{intent} requires a complete Platform target_profile")
    if intent in {"suspend", "retire"} and target is not None:
        raise LifecycleError(f"{intent} derives the lifecycle change and must not carry target_profile")
    if target:
        secret_paths = recursive_secret_keys(target)
        if secret_paths:
            raise LifecycleError(f"target_profile contains prohibited secret-shaped fields: {secret_paths}")
        if target.get("human_approval_required") is not True:
            raise LifecycleError("target_profile must require human approval")
        if target.get("direct_provider_access_allowed") is not False:
            raise LifecycleError("target_profile must prohibit direct provider access")
        requested_callers = sorted(
            item["caller_id"] for item in request["profile_intent"]["registered_callers"]
        )
        if sorted(target.get("allowed_callers") or []) != requested_callers:
            raise LifecycleError("target_profile callers do not match the approved request")
        selected = set((target.get("selected_binding_by_environment") or {}).keys())
        requested_environments = set(request["profile_intent"]["requested_environments"])
        if not requested_environments.issubset(selected):
            raise LifecycleError("target_profile does not cover every approved requested environment")
        output_ref = request["profile_intent"]["required_output_schema_ref"]
        profile_output = target.get("provider_output_schema_ref") or {}
        if (profile_output.get("repo"), profile_output.get("path")) != (
            output_ref["repo"], output_ref["path"]
        ):
            raise LifecycleError("target_profile output schema does not match the approved request")
    expected_status = {
        "create": "suspended",
        "amend": "suspended",
        "activate": "active",
        "exception": "exception",
    }.get(intent)
    if target and target.get("status") != expected_status:
        raise LifecycleError(f"{intent} target_profile status must be {expected_status}")
    if intent == "activate" and decision["activation_environment"] is None:
        raise LifecycleError("activate requires an activation_environment")
    if intent != "activate" and decision["activation_environment"] is not None:
        raise LifecycleError("activation_environment is only valid for activate")
    return profile_id, request


def caller_projection(profile_id: str, caller_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {
        "caller_id": caller_id,
        "purpose": profile["purpose"],
        "required_profile": profile_id,
        "allowed_task_kinds": sorted((profile.get("task_contracts") or {}).get("allowed") or {}),
    }
    for source, target in (
        ("provider_output_schema_ref", "required_provider_output_schema_ref"),
        ("accepted_record_schema_ref", "accepted_record_schema_ref"),
    ):
        if profile.get(source) is not None:
            item[target] = copy.deepcopy(profile[source])
    return item


def mutate_sources(
    registry: dict[str, Any],
    access: dict[str, Any],
    runtime: dict[str, Any],
    decision: dict[str, Any],
) -> tuple[str | None, str | None]:
    intent = decision["intent"]
    profile_id = decision["profile_id"]
    profiles = registry["model_profiles"]
    existing = profiles.get(profile_id)
    before = existing.get("status") if isinstance(existing, dict) else None
    if intent == "create" and existing is not None:
        raise LifecycleError("create cannot replace an existing profile")
    if intent != "create" and existing is None:
        raise LifecycleError("requested profile does not exist in the Platform registry")
    if intent in {"create", "amend", "activate", "exception"}:
        profiles[profile_id] = copy.deepcopy(decision["target_profile"])
    elif intent == "suspend":
        profiles[profile_id]["status"] = "suspended"
        for binding in profiles[profile_id]["bindings"].values():
            if binding.get("status") != "retired":
                binding["status"] = "selected-not-active"
    elif intent == "retire":
        profiles[profile_id]["status"] = "retired"
        for binding in profiles[profile_id]["bindings"].values():
            binding["status"] = "retired"

    profile = profiles[profile_id]
    plane = access["access_plane"]
    plane["allowed_callers"] = [
        item for item in plane["allowed_callers"] if item.get("required_profile") != profile_id
    ]
    for route in plane["provider_routes"]:
        route["allowed_profiles"] = [value for value in route["allowed_profiles"] if value != profile_id]
    plane["allowed_profiles"] = [value for value in plane["allowed_profiles"] if value != profile_id]
    active = profile["status"] == "active"
    retired = profile["status"] == "retired"
    if not retired:
        plane["allowed_profiles"].append(profile_id)
        for binding in profile["bindings"].values():
            route = next(
                (item for item in plane["provider_routes"] if item["route_id"] == binding["provider_route"]),
                None,
            )
            if route is None or binding["upstream_model"] not in route["allowed_models"]:
                raise LifecycleError("target_profile requires an unreviewed provider route or model")
            route["allowed_profiles"].append(profile_id)
        plane["allowed_callers"].extend(
            caller_projection(profile_id, caller, profile)
            for caller in profile["allowed_callers"]
        )
    for route in plane["provider_routes"]:
        route["allowed_profiles"] = sorted(set(route["allowed_profiles"]))
    plane["allowed_profiles"] = sorted(set(plane["allowed_profiles"]))
    plane["allowed_callers"].sort(key=lambda item: item["caller_id"])

    environment = decision["activation_environment"]
    if environment is None:
        environment = sorted(profile["selected_binding_by_environment"])[0]
    binding_id = profile["selected_binding_by_environment"][environment]
    plane["activation_state"]["profile_activations"][profile_id] = {
        "activation_allowed": active,
        "environment": environment,
        "binding": binding_id,
        "reason": (
            f"security-reviewed-lifecycle-decision:{decision['decision_id']}"
            if active
            else f"lifecycle-{profile['status']}:{decision['decision_id']}"
        ),
    }

    contract = runtime["contract"]
    contract["model_profiles"] = sorted(profiles)
    consumers = contract["consumers"]
    consumers["allowed_callers"] = sorted(
        caller
        for value in profiles.values()
        if value.get("status") == "active"
        for caller in value.get("allowed_callers") or []
    )
    consumers["registered_not_active_callers"] = sorted(
        caller
        for value in profiles.values()
        if value.get("status") == "selected-not-active"
        for caller in value.get("allowed_callers") or []
    )
    return before, profile["status"]


def render_yaml(value: dict[str, Any]) -> bytes:
    return yaml.safe_dump(value, sort_keys=False, width=100).encode("utf-8")


def validate_candidate(
    repo_root: Path, registry_bytes: bytes, access_bytes: bytes, runtime_bytes: bytes
) -> None:
    with tempfile.TemporaryDirectory(prefix="model-profile-lifecycle-validate-") as temp_dir:
        candidate = Path(temp_dir) / "platform-engineering"
        shutil.copytree(repo_root / "security", candidate / "security")
        for name in ("docs", "dev-integration"):
            os.symlink(repo_root / name, candidate / name, target_is_directory=True)
        (candidate / REGISTRY).write_bytes(registry_bytes)
        (candidate / ACCESS_PLANE).write_bytes(access_bytes)
        (candidate / RUNTIME_ASSIST).write_bytes(runtime_bytes)
        errors = validate_ai_model_profiles(candidate)
        if errors:
            raise LifecycleError("candidate Platform lifecycle source is invalid: " + "; ".join(errors))


def write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def artifact_ref(path: Path, digest: str) -> dict[str, str]:
    return {"uri": path.resolve().as_uri(), "digest": digest}


def command_apply(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    schemas = load_oos_schemas(repo_root, args.oos_repo_root.resolve())
    projection = read_json(args.request_projection)
    validate_oos_projection(projection, schemas)
    decision = read_json(args.decision)
    validate_schema(decision, repo_root / DECISION_SCHEMA, label="Platform lifecycle decision")
    current = source_state(
        repo_root, source_version=decision["expected_sources"]["source_version"]
    )
    decision_digest = digest_value(decision)
    if args.receipt.exists() or args.rollback_bundle.exists():
        if not args.receipt.exists() or not args.rollback_bundle.exists():
            raise LifecycleError("idempotency conflict: lifecycle outputs are incomplete")
        prior = load_valid_receipt(repo_root, args.receipt)
        rollback = read_json(args.rollback_bundle)
        if digest_value(rollback, "digest") != rollback.get("digest"):
            raise LifecycleError("idempotency conflict: existing rollback bundle digest is false")
        if (
            prior["decision_digest"] != decision_digest
            or prior["request_id"] != projection["request_id"]
            or prior["request_revision"] != projection["revision"]
            or prior["rollback_bundle_ref"] != artifact_ref(args.rollback_bundle, rollback["digest"])
        ):
            raise LifecycleError("idempotency conflict: output paths are bound to different input")
        if any(
            current[field] != prior["result_source"][field]
            for field in ("registry_digest", "access_plane_digest", "runtime_assist_digest")
        ):
            raise LifecycleError("idempotency conflict: prior result is no longer the current source")
        print(json.dumps(prior, sort_keys=True))
        return 0
    head = clean_git_head(repo_root)
    current = source_state(repo_root, source_version=head)
    profile_id, _request = validate_handoff(projection, decision, current)

    registry = read_yaml(repo_root / REGISTRY)
    access = read_yaml(repo_root / ACCESS_PLANE)
    runtime = read_yaml(repo_root / RUNTIME_ASSIST)
    before, after = mutate_sources(registry, access, runtime, decision)
    rendered = {
        REGISTRY: render_yaml(registry),
        ACCESS_PLANE: render_yaml(access),
        RUNTIME_ASSIST: render_yaml(runtime),
    }
    validate_candidate(repo_root, rendered[REGISTRY], rendered[ACCESS_PLANE], rendered[RUNTIME_ASSIST])
    result_values = {
        "registry_digest": digest_bytes(rendered[REGISTRY]),
        "access_plane_digest": digest_bytes(rendered[ACCESS_PLANE]),
        "runtime_assist_digest": digest_bytes(rendered[RUNTIME_ASSIST]),
    }
    result_values["source_version"] = f"platform-source:{digest_value(result_values)[7:31]}"
    rollback = {
        "schema_version": 1,
        "artifact_type": "platform-model-profile-rollback-bundle",
        "request_id": projection["request_id"],
        "decision_digest": decision_digest,
        "base_source": current,
        "result_source": result_values,
        "documents": {
            REGISTRY.as_posix(): base64.b64encode((repo_root / REGISTRY).read_bytes()).decode("ascii"),
            ACCESS_PLANE.as_posix(): base64.b64encode((repo_root / ACCESS_PLANE).read_bytes()).decode("ascii"),
            RUNTIME_ASSIST.as_posix(): base64.b64encode((repo_root / RUNTIME_ASSIST).read_bytes()).decode("ascii"),
        },
    }
    rollback["digest"] = digest_value(rollback, "digest")
    write_atomic(args.rollback_bundle, json.dumps(rollback, sort_keys=True, indent=2).encode() + b"\n")
    rollback_ref = artifact_ref(args.rollback_bundle, rollback["digest"])

    base_receipt = {
        "schema_version": 1,
        "artifact_type": "platform-model-profile-lifecycle-receipt",
        "receipt_id": "platform-model-profile-receipt:000000000000000000000000",
        "request_id": projection["request_id"],
        "request_revision": projection["revision"],
        "request_receipt_digest": projection["latest_receipt"]["digest"],
        "decision_id": decision["decision_id"],
        "decision_digest": decision_digest,
        "intent": decision["intent"],
        "profile_id": profile_id,
        "actor_id": ACTOR_ID,
        "recorded_at": decision["recorded_at"],
        "outcome": "applied",
        "lifecycle_before": before,
        "lifecycle_after": after,
        "base_source": current,
        "result_source": result_values,
        "rollback_bundle_ref": rollback_ref,
        "oos_fulfillment": {
            "state": "pending-source-review",
            "expected_revision": projection["revision"],
            "next_action": "merge reviewed Platform source, then run model-profile-lifecycle readback",
        },
        "digest": "sha256:" + "0" * 64,
    }
    identity = digest_value({**base_receipt, "receipt_id": None, "digest": None})
    base_receipt["receipt_id"] = f"platform-model-profile-receipt:{identity[7:31]}"
    base_receipt["digest"] = digest_value(base_receipt, "digest")
    validate_schema(base_receipt, repo_root / RECEIPT_SCHEMA, label="Platform lifecycle receipt")

    backups = {path: (repo_root / path).read_bytes() for path in rendered}
    try:
        for path, content in rendered.items():
            write_atomic(repo_root / path, content)
        write_atomic(args.receipt, json.dumps(base_receipt, sort_keys=True, indent=2).encode() + b"\n")
    except Exception:
        for path, content in backups.items():
            write_atomic(repo_root / path, content)
        raise
    print(json.dumps(base_receipt, sort_keys=True))
    return 0


def projection_for(repo_root: Path, source_version: str | None) -> dict[str, Any]:
    registry = read_yaml(repo_root / REGISTRY)
    access = read_yaml(repo_root / ACCESS_PLANE)["access_plane"]
    activations = access["activation_state"]["profile_activations"]
    profiles = []
    for profile_id, profile in sorted(registry["model_profiles"].items()):
        profiles.append(
            {
                "profile_id": profile_id,
                "lifecycle": profile["status"],
                "purpose": profile["purpose"],
                "allowed_callers": sorted(profile["allowed_callers"]),
                "selected_environments": sorted(profile["selected_binding_by_environment"]),
                "activation": copy.deepcopy(activations[profile_id]),
                "security_review_ref": copy.deepcopy(profile["security_review_ref"]),
            }
        )
    result = {
        "schema_version": 1,
        "artifact_type": "platform-model-profile-source-projection",
        "owner_repo": "platform-engineering",
        "source": source_state(repo_root, source_version=source_version),
        "profiles": profiles,
        "digest": "sha256:" + "0" * 64,
    }
    result["digest"] = digest_value(result, "digest")
    validate_schema(result, repo_root / PROJECTION_SCHEMA, label="Platform profile source projection")
    return result


def command_project(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    errors = validate_ai_model_profiles(repo_root)
    if errors:
        raise LifecycleError("Platform model-profile sources are invalid: " + "; ".join(errors))
    head = clean_git_head(repo_root)
    if args.source_version and args.source_version != head:
        raise LifecycleError("requested source_version does not match Platform HEAD")
    result = projection_for(repo_root, head)
    rendered = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        write_atomic(args.output, rendered.encode())
    else:
        print(rendered, end="")
    return 0


def load_valid_receipt(repo_root: Path, path: Path) -> dict[str, Any]:
    receipt = read_json(path)
    validate_schema(receipt, repo_root / RECEIPT_SCHEMA, label="Platform lifecycle receipt")
    if digest_value(receipt, "digest") != receipt["digest"]:
        raise LifecycleError("Platform lifecycle receipt digest is false")
    return receipt


def load_private_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise LifecycleError(f"{label} must be an absolute regular private file")
    stat = path.stat()
    if stat.st_uid != os.geteuid() or stat.st_mode & 0o077:
        raise LifecycleError(f"{label} must be owned by the operator with mode 0600")
    return read_json(path)


def parse_repo_paths(values: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        name, separator, raw_path = value.partition("=")
        path = Path(raw_path)
        if not separator or not name or not path.is_absolute() or name in parsed:
            raise LifecycleError("--repo-path requires unique REPO=/absolute/path values")
        parsed[name] = path.resolve()
    return parsed


def workspace_repo(repo_root: Path, name: str, overrides: dict[str, Path]) -> Path:
    if name in overrides:
        return overrides[name]
    if name == "platform-engineering":
        return repo_root
    for ancestor in repo_root.parents:
        candidate = ancestor / name
        if candidate.exists():
            return candidate
    raise LifecycleError(f"unable to locate required owner repo {name}")


def get_live_projection(spec: dict[str, Any]) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    caller_id = spec.get("caller_id")
    secret_file = spec.get("secret_file")
    if bool(caller_id) != bool(secret_file):
        raise LifecycleError("live projection caller_id and secret_file must be supplied together")
    if caller_id:
        secret_path = Path(secret_file)
        if not secret_path.is_absolute() or not secret_path.is_file() or secret_path.is_symlink():
            raise LifecycleError("live projection secret_file must be an absolute regular file")
        stat = secret_path.stat()
        if stat.st_uid != os.geteuid() or stat.st_mode & 0o077:
            raise LifecycleError("live projection secret_file must be operator-private")
        secret = secret_path.read_text(encoding="utf-8").strip()
        if not secret:
            raise LifecycleError("live projection secret_file is empty")
        headers.update({"x-oos-caller-id": caller_id, "x-oos-caller-secret": secret})
    try:
        with urlopen(Request(spec["url"], headers=headers), timeout=20) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"live projection read failed: {type(exc).__name__}") from None
    if not isinstance(value, dict) or digest_value(value) != spec["expected_digest"]:
        raise LifecycleError("live projection does not match its exact expected digest")
    return value


def command_verify_operating(args: argparse.Namespace) -> int:
    if (
        os.environ.get("OOS_DELIVERY_ART_EVIDENCE_EXECUTION") != "true"
        or os.environ.get("OOS_DELIVERY_ART_EVIDENCE_MODE") != "verification-only"
    ):
        raise LifecycleError("operating verification requires the OOS verification-only evidence boundary")
    repo_root = args.repo_root.resolve()
    if args.evidence is None:
        raise LifecycleError("MODEL_PROFILE_LIFECYCLE_OPERATING_EVIDENCE or --evidence is required")
    proof = load_private_json(args.evidence.resolve(), label="operating proof")
    validate_schema(proof, repo_root / OPERATING_SCHEMA, label="model-profile operating proof")
    try:
        recorded = datetime.fromisoformat(proof["recorded_at"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(proof["expires_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise LifecycleError("operating proof timestamps are invalid") from exc
    now = datetime.now(timezone.utc)
    if recorded > now or expires < now or expires <= recorded or (expires - recorded).total_seconds() > 1800:
        raise LifecycleError("operating proof is future-dated, expired, or exceeds 30 minutes")
    overrides = parse_repo_paths(args.repo_path)
    for name, expected in proof["source_revisions"].items():
        observed = clean_git_head(workspace_repo(repo_root, name, overrides))
        if observed != expected:
            raise LifecycleError(f"operating proof source revision is stale for {name}")

    artifact_paths = {
        name: Path(value)
        for name, value in proof["platform_artifacts"].items()
    }
    artifacts = {
        name: load_private_json(path, label=name.replace("_", " "))
        for name, path in artifact_paths.items()
    }
    receipt = artifacts["lifecycle_receipt"]
    validate_schema(receipt, repo_root / RECEIPT_SCHEMA, label="Platform lifecycle receipt")
    if digest_value(receipt, "digest") != receipt["digest"]:
        raise LifecycleError("operating lifecycle receipt digest is false")
    readback = artifacts["merged_readback"]
    restore = artifacts["restore_receipt"]
    if (
        digest_value(readback, "digest") != readback.get("digest")
        or digest_value(restore, "digest") != restore.get("digest")
        or readback.get("lifecycle_receipt_ref") != artifact_ref(
            artifact_paths["lifecycle_receipt"], receipt["digest"]
        )
        or restore.get("lifecycle_receipt_ref") != readback.get("lifecycle_receipt_ref")
        or restore.get("outcome") != "restored"
    ):
        raise LifecycleError("Platform readback or restore receipt is false or unbound")

    oos = get_live_projection(proof["oos"])
    console = get_live_projection(proof["console"])
    latest = oos.get("latest_receipt") if isinstance(oos, dict) else None
    if (
        oos.get("workflow_id") != "model-profile-request"
        or oos.get("review_state") != "approved"
        or oos.get("fulfillment_state") != "applied"
        or oos.get("profile_lifecycle_changed") is not False
        or not isinstance(latest, dict)
        or digest_value(latest, "digest") != latest.get("digest")
    ):
        raise LifecycleError("live OOS model-profile projection is incomplete or false")
    oos_ref = console.get("oos_request_ref") if isinstance(console, dict) else None
    platform_ref = console.get("platform_source_ref") if isinstance(console, dict) else None
    if (
        console.get("workflow_id") != "model-operations-live-projection"
        or console.get("projection_state") != "current"
        or console.get("next_action") != "complete"
        or console.get("console_mutation_authority") is not False
        or not isinstance(oos_ref, dict)
        or oos_ref.get("request_id") != oos.get("request_id")
        or oos_ref.get("revision") != oos.get("revision")
        or oos_ref.get("receipt_digest") != latest.get("digest")
        or not isinstance(platform_ref, dict)
        or platform_ref.get("lifecycle_receipt_digest") != receipt["digest"]
        or platform_ref.get("merged_readback_digest") != readback["digest"]
    ):
        raise LifecycleError("live Console projection is stale, incomplete, or claims mutation authority")
    summary = {
        "outcome": "verified",
        "request_id": oos["request_id"],
        "request_revision": oos["revision"],
        "platform_revision": proof["source_revisions"]["platform-engineering"],
        "negative_outcomes": proof["negative_outcomes"],
        "cleanup": proof["cleanup"],
        "secret_values_embedded": False,
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


def command_readback(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    if not COMMIT.fullmatch(args.source_version):
        raise LifecycleError("readback source_version must be the full merged Platform commit")
    head = clean_git_head(repo_root)
    if head != args.source_version:
        raise LifecycleError("readback source_version does not match Platform HEAD")
    receipt = load_valid_receipt(repo_root, args.receipt)
    assert_time_order(receipt["recorded_at"], args.recorded_at)
    observed = source_state(repo_root, source_version=receipt["result_source"]["source_version"])
    if observed != receipt["result_source"]:
        raise LifecycleError("merged Platform source does not match the lifecycle receipt")
    review_ref = {"uri": args.review_uri, "digest": args.review_digest}
    fulfillment = {
        "schema_version": 1,
        "fulfillment_id": f"platform-model-profile-fulfillment:{receipt['digest'][7:31]}",
        "request_id": receipt["request_id"],
        "expected_revision": receipt["request_revision"],
        "state": "applied",
        "actor_id": ACTOR_ID,
        "recorded_at": args.recorded_at,
        "source": {
            "owner_repo": "platform-engineering",
            "base_version": receipt["base_source"]["source_version"],
            "result_version": args.source_version,
            "review_ref": review_ref,
        },
        "receipt_ref": artifact_ref(args.receipt, receipt["digest"]),
        "failure": None,
        "idempotency_key": f"model-profile-readback:{receipt['digest'][7:31]}",
    }
    result = {
        "schema_version": 1,
        "artifact_type": "platform-model-profile-merged-readback",
        "source_version": args.source_version,
        "lifecycle_receipt_ref": artifact_ref(args.receipt, receipt["digest"]),
        "source_projection": projection_for(repo_root, args.source_version),
        "oos_fulfillment": fulfillment,
    }
    result["digest"] = digest_value(result)
    validate_oos_projection_contract("fulfillment.schema.json", fulfillment, args, repo_root)
    write_atomic(args.output, json.dumps(result, sort_keys=True, indent=2).encode() + b"\n")
    print(json.dumps(result, sort_keys=True))
    return 0


def validate_oos_projection_contract(
    name: str, value: dict[str, Any], args: argparse.Namespace, repo_root: Path
) -> None:
    schemas = load_oos_schemas(repo_root, args.oos_repo_root.resolve())
    schema = schemas[name]
    registry = Registry().with_resources(
        (str(document["$id"]), Resource.from_contents(document))
        for document in schemas.values()
    )
    errors = list(
        Draft202012Validator(
            schema,
            registry=registry,
            format_checker=FormatChecker(),
        ).iter_errors(value)
    )
    if errors:
        raise LifecycleError(f"generated OOS fulfillment is invalid: {errors[0].message}")


def command_restore(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    receipt = load_valid_receipt(repo_root, args.receipt)
    bundle = read_json(args.rollback_bundle)
    if digest_value(bundle, "digest") != bundle.get("digest"):
        raise LifecycleError("rollback bundle digest is false")
    if artifact_ref(args.rollback_bundle, bundle["digest"]) != receipt["rollback_bundle_ref"]:
        raise LifecycleError("rollback bundle does not match the lifecycle receipt")
    observed = source_state(repo_root, source_version=receipt["result_source"]["source_version"])
    if observed != receipt["result_source"]:
        raise LifecycleError("rollback denied because current source differs from the applied result")
    documents = bundle.get("documents") or {}
    expected_paths = {REGISTRY.as_posix(), ACCESS_PLANE.as_posix(), RUNTIME_ASSIST.as_posix()}
    if set(documents) != expected_paths:
        raise LifecycleError("rollback bundle has an invalid source set")
    try:
        rendered = {
            Path(path): base64.b64decode(value, validate=True)
            for path, value in documents.items()
        }
    except (TypeError, ValueError) as exc:
        raise LifecycleError("rollback bundle contains invalid source bytes") from exc
    validate_candidate(repo_root, rendered[REGISTRY], rendered[ACCESS_PLANE], rendered[RUNTIME_ASSIST])
    restored = {
        "registry_digest": digest_bytes(rendered[REGISTRY]),
        "access_plane_digest": digest_bytes(rendered[ACCESS_PLANE]),
        "runtime_assist_digest": digest_bytes(rendered[RUNTIME_ASSIST]),
        "source_version": receipt["base_source"]["source_version"],
    }
    if restored != receipt["base_source"]:
        raise LifecycleError("rollback bundle does not reproduce the exact baseline")
    for path, content in rendered.items():
        write_atomic(repo_root / path, content)
    result = {
        "schema_version": 1,
        "artifact_type": "platform-model-profile-restore-receipt",
        "lifecycle_receipt_ref": artifact_ref(args.receipt, receipt["digest"]),
        "restored_source": restored,
        "recorded_at": args.recorded_at,
        "outcome": "restored",
    }
    result["digest"] = digest_value(result)
    write_atomic(args.output, json.dumps(result, sort_keys=True, indent=2).encode() + b"\n")
    print(json.dumps(result, sort_keys=True))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    schemas = load_oos_schemas(repo_root, args.oos_repo_root.resolve())
    if set(schemas) != {
        "request.schema.json", "command.schema.json", "fulfillment.schema.json",
        "receipt.schema.json", "projection.schema.json",
    }:
        raise LifecycleError("locked OOS model-profile contract bundle is incomplete")
    for path, label in (
        (DECISION_SCHEMA, "decision"),
        (RECEIPT_SCHEMA, "receipt"),
        (PROJECTION_SCHEMA, "projection"),
        (OPERATING_SCHEMA, "operating proof"),
    ):
        schema = read_json(repo_root / path)
        Draft202012Validator.check_schema(schema)
        if not schema.get("$id"):
            raise LifecycleError(f"Platform lifecycle {label} schema has no canonical id")
    errors = validate_ai_model_profiles(repo_root)
    if errors:
        raise LifecycleError("Platform model-profile sources are invalid: " + "; ".join(errors))
    print("model-profile lifecycle contracts valid; runtime activation remains Security-gated")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--repo-root", type=Path, default=ROOT)
    default_oos = next(
        (
            ancestor / "operator-orchestration-service"
            for ancestor in ROOT.parents
            if (ancestor / "operator-orchestration-service").is_dir()
        ),
        ROOT.parent / "operator-orchestration-service",
    )
    result.add_argument(
        "--oos-repo-root",
        type=Path,
        default=default_oos,
        help="git checkout containing the exact locked OOS contract commit",
    )
    result.add_argument(
        "--repo-path",
        action="append",
        default=[],
        metavar="REPO=/ABSOLUTE/PATH",
        help="override an exact owner-repo checkout for operating verification",
    )
    commands = result.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.set_defaults(handler=command_validate)
    project = commands.add_parser("project")
    project.add_argument("--source-version")
    project.add_argument("--output", type=Path)
    project.set_defaults(handler=command_project)
    apply = commands.add_parser("apply")
    apply.add_argument("--request-projection", type=Path, required=True)
    apply.add_argument("--decision", type=Path, required=True)
    apply.add_argument("--receipt", type=Path, required=True)
    apply.add_argument("--rollback-bundle", type=Path, required=True)
    apply.set_defaults(handler=command_apply)
    readback = commands.add_parser("readback")
    readback.add_argument("--receipt", type=Path, required=True)
    readback.add_argument("--source-version", required=True)
    readback.add_argument("--review-uri", required=True)
    readback.add_argument("--review-digest", required=True)
    readback.add_argument("--recorded-at", required=True)
    readback.add_argument("--output", type=Path, required=True)
    readback.set_defaults(handler=command_readback)
    restore = commands.add_parser("restore")
    restore.add_argument("--receipt", type=Path, required=True)
    restore.add_argument("--rollback-bundle", type=Path, required=True)
    restore.add_argument("--recorded-at", required=True)
    restore.add_argument("--output", type=Path, required=True)
    restore.set_defaults(handler=command_restore)
    verify_operating = commands.add_parser("verify-operating")
    configured_evidence = os.environ.get("MODEL_PROFILE_LIFECYCLE_OPERATING_EVIDENCE")
    verify_operating.add_argument(
        "--evidence",
        type=Path,
        default=Path(configured_evidence) if configured_evidence else None,
    )
    verify_operating.set_defaults(handler=command_verify_operating)
    return result


def main() -> int:
    args = parser().parse_args()
    if hasattr(args, "review_digest") and not DIGEST.fullmatch(args.review_digest):
        raise LifecycleError("review digest must be sha256:<64 lowercase hex>")
    return args.handler(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LifecycleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
