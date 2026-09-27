#!/usr/bin/env python3
"""Publish secret-free Console runtime observations from admitted workloads."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import tempfile
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker
import yaml


PRODUCT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PRODUCT_ROOT.parents[1]
DEFAULT_POLICY = PRODUCT_ROOT / "runtime-observation-policy.yaml"
DEFAULT_POLICY_SCHEMA = PRODUCT_ROOT / "schemas/runtime-observation-policy.schema.json"
DEFAULT_PROJECTION_SCHEMA = PRODUCT_ROOT / "schemas/runtime-observation-projection.schema.json"
MAX_FILE_BYTES = 131072
OPERATOR_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ObservationError(ValueError):
    pass


@dataclass(frozen=True)
class Component:
    id: str
    label: str
    category: str
    kind: str
    namespace_template: str
    name: str
    capabilities: tuple[str, ...]
    recovery_owner: str
    recovery_runbook_ref: str


@dataclass(frozen=True)
class Policy:
    digest: str
    schema_version: str
    source_authority: str
    source_mode: str
    maximum_age_seconds: int
    lane: str
    profile: str
    components: tuple[Component, ...]


CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def render_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ObservationError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ObservationError(f"{label} must be an ISO-8601 timestamp") from None
    if parsed.tzinfo is None:
        raise ObservationError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def load_yaml(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink():
            raise ObservationError(f"{label} must not be a symlink")
        info = path.stat()
    except OSError:
        raise ObservationError(f"{label} is unavailable") from None
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
        raise ObservationError(f"{label} must be a bounded regular file")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        raise ObservationError(f"{label} is invalid") from None
    if not isinstance(value, dict):
        raise ObservationError(f"{label} must contain an object")
    return value


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink():
            raise ObservationError(f"{label} must not be a symlink")
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
            raise ObservationError(f"{label} must be a bounded regular file")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ObservationError(f"{label} is invalid") from None
    if not isinstance(value, dict):
        raise ObservationError(f"{label} must contain an object")
    return value


def validate_schema(value: dict[str, Any], schema_path: Path, label: str) -> None:
    schema = load_json(schema_path, f"{label} schema")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    findings = sorted(validator.iter_errors(value), key=lambda finding: list(finding.absolute_path))
    if findings:
        finding = findings[0]
        location = ".".join(str(part) for part in finding.absolute_path) or "<root>"
        raise ObservationError(f"{label} is invalid at {location}: {finding.message}")


def load_policy(
    path: Path = DEFAULT_POLICY,
    schema_path: Path = DEFAULT_POLICY_SCHEMA,
) -> Policy:
    value = load_yaml(path, "runtime observation policy")
    validate_schema(value, schema_path, "runtime observation policy")
    components = tuple(
        Component(
            id=item["id"],
            label=item["label"],
            category=item["category"],
            kind=item["workload"]["kind"],
            namespace_template=item["workload"]["namespace"],
            name=item["workload"]["name"],
            capabilities=tuple(item["capabilities"]),
            recovery_owner=item["recovery"]["owner"],
            recovery_runbook_ref=item["recovery"]["runbook_ref"],
        )
        for item in value["components"]
    )
    ids = [component.id for component in components]
    if len(set(ids)) != len(ids):
        raise ObservationError("runtime observation component ids must be unique")
    for component in components:
        if component.namespace_template.count("{operator}") > 1:
            raise ObservationError("runtime observation namespace has repeated operator placeholders")
        runbook = REPO_ROOT / component.recovery_runbook_ref
        if not runbook.is_file():
            raise ObservationError(
                f"runtime observation recovery runbook is unavailable: {component.recovery_runbook_ref}"
            )
    projection = value["projection"]
    environment = value["environment"]
    return Policy(
        digest=digest(value),
        schema_version=projection["schema_version"],
        source_authority=projection["source_authority"],
        source_mode=projection["source_mode"],
        maximum_age_seconds=projection["maximum_age_seconds"],
        lane=environment["lane"],
        profile=environment["profile"],
        components=components,
    )


def default_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def workload_observation(
    component: Component,
    *,
    operator: str,
    observed_at: str,
    runner: CommandRunner,
) -> dict[str, Any]:
    namespace = component.namespace_template.replace("{operator}", operator)
    command = [
        "k3s",
        "kubectl",
        "-n",
        namespace,
        "get",
        component.kind,
        component.name,
        "-o",
        "json",
    ]
    result = runner(command)
    if result.returncode != 0:
        error_text = (result.stderr or "").casefold()
        if "notfound" not in error_text and "not found" not in error_text:
            raise ObservationError(f"platform observation command failed for {component.id}")
        desired = 0
        ready = 0
        state = "unavailable"
        reason = "runtime_not_found"
    else:
        try:
            value = json.loads(result.stdout)
            desired = int((value.get("spec") or {}).get("replicas") or 0)
            ready = int((value.get("status") or {}).get("readyReplicas") or 0)
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
            raise ObservationError(f"platform observation response is invalid for {component.id}") from None
        if desired <= 0:
            state = "unavailable"
            reason = "runtime_scaled_down"
        elif ready >= desired:
            state = "available"
            reason = None
        elif ready > 0:
            state = "degraded"
            reason = "runtime_partially_ready"
        else:
            state = "unavailable"
            reason = "runtime_not_ready"
    posture = {
        "available": "runtime-ready",
        "degraded": "degraded",
        "unavailable": "unavailable",
    }[state]
    return {
        "id": component.id,
        "label": component.label,
        "category": component.category,
        "runtime": {
            "state": state,
            "desiredReplicas": desired,
            "readyReplicas": ready,
            "reasonCode": reason,
        },
        "freshness": "current",
        "observedAt": observed_at,
        "sourceRef": f"kubernetes://{namespace}/{component.kind}/{component.name}",
        "capabilities": [
            {"id": capability, "posture": posture}
            for capability in component.capabilities
        ],
        "recovery": {
            "owner": component.recovery_owner,
            "runbookRef": component.recovery_runbook_ref,
        },
    }


def build_projection(
    policy: Policy,
    *,
    operator: str,
    now: datetime | None = None,
    runner: CommandRunner = default_runner,
) -> dict[str, Any]:
    if not OPERATOR_PATTERN.fullmatch(operator):
        raise ObservationError("operator must be a lowercase workspace identifier")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    observed_at = render_timestamp(current)
    components = [
        workload_observation(
            component,
            operator=operator,
            observed_at=observed_at,
            runner=runner,
        )
        for component in policy.components
    ]
    binding = hashlib.sha256(
        canonical_bytes(
            {
                "policy_digest": policy.digest,
                "operator": operator,
                "observed_at": observed_at,
                "components": components,
            }
        )
    ).hexdigest()
    return {
        "schemaVersion": policy.schema_version,
        "environment": {"lane": policy.lane, "profile": policy.profile},
        "source": {
            "authority": policy.source_authority,
            "mode": policy.source_mode,
            "observedAt": observed_at,
            "validUntil": render_timestamp(
                current + timedelta(seconds=policy.maximum_age_seconds)
            ),
            "reference": f"platform-runtime-observation://{binding}",
        },
        "components": components,
    }


def validate_projection(
    value: dict[str, Any],
    schema_path: Path = DEFAULT_PROJECTION_SCHEMA,
) -> None:
    validate_schema(value, schema_path, "runtime observation projection")
    observed_at = parse_timestamp(value["source"]["observedAt"], "source observation time")
    valid_until = parse_timestamp(value["source"]["validUntil"], "source validity time")
    if valid_until <= observed_at:
        raise ObservationError("runtime observation validity must follow its observation time")
    for component in value["components"]:
        if parse_timestamp(component["observedAt"], "component observation time") != observed_at:
            raise ObservationError("component observation time must match the source observation time")


def write_private_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink():
        raise ObservationError("runtime observation output directory must not be a symlink")
    os.chmod(path.parent, 0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def projection_summary(
    projection: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    validate_projection(projection)
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    valid_until = parse_timestamp(projection["source"]["validUntil"], "source validity time")
    counts = {"available": 0, "degraded": 0, "unavailable": 0}
    for component in projection["components"]:
        counts[component["runtime"]["state"]] += 1
    return {
        "schema_version": 1,
        "projection_reference": projection["source"]["reference"],
        "freshness": "current" if current <= valid_until else "stale",
        "observed_at": projection["source"]["observedAt"],
        "valid_until": projection["source"]["validUntil"],
        "component_count": len(projection["components"]),
        "counts": counts,
        "secret_values_embedded": False,
    }


def project(
    policy: Policy,
    output: Path,
    receipt: Path,
    *,
    operator: str,
    now: datetime | None = None,
    runner: CommandRunner = default_runner,
) -> dict[str, Any]:
    value = build_projection(policy, operator=operator, now=now, runner=runner)
    validate_projection(value)
    write_private_json(output, value)
    summary = projection_summary(value, now=now)
    receipt_value = {
        **summary,
        "action": "project",
        "policy_digest": policy.digest,
        "projection_digest": digest(value),
        "projection_path": str(output),
    }
    write_private_json(receipt, receipt_value)
    return receipt_value


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    actions = root.add_subparsers(dest="action", required=True)
    actions.add_parser("validate")
    project_action = actions.add_parser("project")
    project_action.add_argument("--output", type=Path, required=True)
    project_action.add_argument("--receipt", type=Path, required=True)
    project_action.add_argument("--operator", default=pwd.getpwuid(os.geteuid()).pw_name)
    inspect_action = actions.add_parser("inspect")
    inspect_action.add_argument("--projection", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        policy = load_policy(args.policy)
        if args.action == "validate":
            print(
                "Console runtime observation policy valid: "
                f"components={len(policy.components)} schema={policy.schema_version}"
            )
            return 0
        if args.action == "project":
            result = project(
                policy,
                args.output,
                args.receipt,
                operator=args.operator,
            )
        else:
            result = projection_summary(
                load_json(args.projection, "runtime observation projection")
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except ObservationError as error:
        print(f"Console runtime observation failed: {error}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
