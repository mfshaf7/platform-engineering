#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from collections.abc import Mapping


SCOPED_WORKFLOW_ID = "delivery-initiative-review-pack"
UNSCOPED_WORKFLOW_ID = "delivery-session-workflow-health"


def run_json(
    command: list[str], *, env: dict[str, str], input_text: str | None = None
) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=env,
            check=True,
            input=input_text,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or f"exit status {exc.returncode}"
        raise RuntimeError(f"command failed: {' '.join(command)}: {detail}") from exc

    lines = completed.stdout.splitlines()
    cleaned = "\n".join(
        line
        for line in lines
        if not line.startswith("Showing delivery ")
        and not line.startswith("Defaulted container ")
        and not line.startswith("DEPRECATION WARNING:")
        and not line.startswith("You can emulate the previous behavior")
        and not line.startswith(" (called from ")
        and not line.startswith("I, [")
        and not line.startswith("W, [")
    ).strip()
    json_start = cleaned.find("{")
    payload = cleaned[json_start:] if json_start >= 0 else ""
    if not payload:
        raise RuntimeError(f"command returned no JSON payload: {' '.join(command)}")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"command returned a non-object JSON payload: {' '.join(command)}")
    return parsed


def env_value(env: Mapping[str, str], key: str, default: str) -> str:
    value = (env.get(key) or "").strip()
    return value or default


def resolve_openproject_namespace(env: Mapping[str, str]) -> str:
    return env_value(env, "OPENPROJECT_NAMESPACE", "openproject")


def resolve_broker_namespace(env: Mapping[str, str]) -> str:
    broker_namespace = (env.get("BROKER_NAMESPACE") or "").strip()
    if broker_namespace:
        return broker_namespace
    openproject_namespace = resolve_openproject_namespace(env)
    if openproject_namespace == "openproject":
        return "operator-orchestration-service"
    return openproject_namespace


def normalize_delivery_id(raw_id: str) -> str:
    value = raw_id.strip()
    if not value:
        raise RuntimeError("delivery id is required")
    if value.startswith("delivery-"):
        suffix = value.removeprefix("delivery-")
    else:
        suffix = value
    if not suffix.isdigit():
        raise RuntimeError("delivery id must look like `698` or `delivery-698`")
    return f"delivery-{suffix}"


def run_broker_json(path: str, *, env: dict[str, str]) -> dict[str, object]:
    kubectl = shlex.split(env.get("KUBECTL", "k3s kubectl"))
    broker_namespace = resolve_broker_namespace(env)
    broker_deployment = env_value(
        env, "BROKER_DEPLOYMENT", "operator-orchestration-service"
    )
    broker_port = env_value(env, "BROKER_PORT", "8080")
    node_script = """
const brokerPath = process.env.BROKER_PATH || "/";
const brokerPort = process.env.BROKER_PORT || "8080";
const callerAllowedIds = (process.env.CALLER_ALLOWED_IDS || "")
  .split(",")
  .map((entry) => entry.trim())
  .filter(Boolean);
const callerId = callerAllowedIds[0] || "openproject-check-delivery-art-quality";
const callerSecret = process.env.CALLER_AUTH_SHARED_SECRET || "";

async function requestJson(url, { method = "GET", headers = {} } = {}) {
  const response = await fetch(url, { method, headers });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${method} ${url} failed: ${response.status} ${text}`);
  }
  return text ? JSON.parse(text) : null;
}

const brokerBase = `http://127.0.0.1:${brokerPort}`;
const ready = await requestJson(`${brokerBase}/readyz`);
if (!ready.ready) {
  throw new Error(`Broker is not ready: ${JSON.stringify(ready)}`);
}
const payload = await requestJson(`${brokerBase}${brokerPath}`, {
  headers: {
    "x-correlation-id": `openproject-check-delivery-art-quality-${Date.now()}`,
    "x-oos-caller-id": callerId,
    "x-oos-caller-secret": callerSecret,
  },
});
process.stdout.write(`${JSON.stringify(payload, null, 2)}\\n`);
"""
    return run_json(
        [
            *kubectl,
            "-n",
            broker_namespace,
            "exec",
            "-i",
            f"deploy/{broker_deployment}",
            "--",
            "env",
            f"BROKER_PATH={path}",
            f"BROKER_PORT={broker_port}",
            "node",
            "--input-type=module",
            "-e",
            node_script,
        ],
        env=env,
    )


def require_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"broker projection is missing object field {field_name}")
    return value


def count_projected_lists(projection: Mapping[str, object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, value in projection.items():
        if not isinstance(value, list):
            raise RuntimeError(f"broker projection field {key} must be a list")
        counts[str(key)] = len(value)
    return dict(sorted(counts.items()))


def build_scoped_report(
    payload: Mapping[str, object], *, delivery_id: str
) -> dict[str, object]:
    workflow_id = payload.get("workflow_id")
    if workflow_id != SCOPED_WORKFLOW_ID:
        raise RuntimeError(
            f"expected broker workflow {SCOPED_WORKFLOW_ID}, received {workflow_id!r}"
        )

    review_pack = require_mapping(payload.get("review_pack"), "review_pack")
    quality_drift = require_mapping(
        review_pack.get("quality_drift"), "review_pack.quality_drift"
    )
    drift_counts = count_projected_lists(quality_drift)
    issue_count = sum(drift_counts.values())

    return {
        "workflow_id": "platform-delivery-art-quality-projection",
        "source_workflow_id": workflow_id,
        "scope": {
            "delivery_id": delivery_id,
            "mode": "scoped-initiative",
        },
        "summary": {
            "healthy": issue_count == 0,
            "issue_count": issue_count,
            "issue_types": drift_counts,
        },
        "broker_projection": {
            "epic": review_pack.get("epic"),
            "initiative_review": review_pack.get("initiative_review"),
            "quality_drift": quality_drift,
            "summary": review_pack.get("summary"),
        },
    }


def build_unscoped_report(payload: Mapping[str, object]) -> dict[str, object]:
    workflow_id = payload.get("workflow_id")
    if workflow_id != UNSCOPED_WORKFLOW_ID:
        raise RuntimeError(
            f"expected broker workflow {UNSCOPED_WORKFLOW_ID}, received {workflow_id!r}"
        )

    workflow_health = require_mapping(
        payload.get("workflow_health"), "workflow_health"
    )
    summary = require_mapping(
        workflow_health.get("summary"), "workflow_health.summary"
    )
    if not isinstance(summary.get("healthy"), bool):
        raise RuntimeError("broker projection is missing boolean workflow health")

    projection_drift: dict[str, object] = {}
    issue_counts: dict[str, int] = {}
    for key in ("pm2_phase", "roadmap"):
        projection = require_mapping(
            workflow_health.get(key), f"workflow_health.{key}"
        )
        drift = projection.get("drift")
        if not isinstance(drift, list):
            raise RuntimeError(f"broker projection field workflow_health.{key}.drift must be a list")
        projection_drift[key] = projection
        issue_counts[key] = len(drift)

    return {
        "workflow_id": "platform-delivery-art-quality-projection",
        "source_workflow_id": workflow_id,
        "scope": {
            "delivery_id": None,
            "mode": "portfolio-projection",
        },
        "summary": {
            "healthy": summary["healthy"],
            "issue_count": sum(issue_counts.values()),
            "issue_types": issue_counts,
        },
        "broker_projection": {
            "compatible_views": workflow_health.get("compatible_views"),
            "portfolio_summary": payload.get("portfolio_summary"),
            "project": payload.get("project"),
            "projection_health": projection_drift,
            "summary": summary,
        },
    }


def main(*, env: dict[str, str] | None = None) -> int:
    runtime_env = dict(os.environ if env is None else env)
    target_epic_id = (runtime_env.get("TARGET_EPIC_ID") or "").strip()

    if target_epic_id:
        delivery_id = normalize_delivery_id(target_epic_id)
        payload = run_broker_json(
            f"/v1/delivery-initiatives/{delivery_id}/review-pack",
            env=runtime_env,
        )
        report = build_scoped_report(payload, delivery_id=delivery_id)
    else:
        payload = run_broker_json(
            "/v1/delivery-session/workflow-health",
            env=runtime_env,
        )
        report = build_unscoped_report(payload)

    print(json.dumps(report, indent=2))
    return 0 if report["summary"]["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
