#!/usr/bin/env python3
"""Bind native Console dispatch to reviewed inputs; retain normal manual workflows.

This helper executes inside the existing protected environment job. The separate
dispatch App cannot approve that environment, write source, or merge the PR.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
INPUTS = {
    "readiness": ("verification_evidence_ref", "verification_results", "verification_note", "approval_note"),
    "promotion": ("source_environment", "target_environment", "promotion_note", "suspend_stage_environment"),
    "runtime": ("state", "reason", "incident_ref", "operation_note"),
}
WORKFLOWS = {
    "readiness": "confirm-stage-promotion-readiness.yaml",
    "promotion": "promote-environment.yaml",
    "runtime": "manage-prod-environment.yaml",
}


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def guard(kind, env=os.environ):
    request = env.get("CONSOLE_REQUEST_ID", "")
    raw = env.get("CONSOLE_INTENT", "")
    # Native fields are a pair; an incomplete pair must never fall back to manual.
    if not request and not raw:
        if env.get("GITHUB_ACTOR") == "mfshaf7-governed-releases[bot]":
            raise ValueError("The dispatch App requires a native intent.")
        return None
    if kind not in INPUTS or not re.fullmatch(r"[a-f0-9]{64}", request) or len(raw) > 8192:
        raise ValueError("Invalid Console request binding.")
    intent = json.loads(raw)
    fields = {"schema_version", "command_id", "intent_digest", "operator_id", "platform_revision", "registry_revision", "workflow_id", "inputs_digest"}
    if not isinstance(intent, dict) or set(intent) != fields or intent["schema_version"] != 1:
        raise ValueError("Invalid Console intent envelope.")
    if (env.get("GITHUB_REPOSITORY") != "mfshaf7/platform-engineering"
            or env.get("GITHUB_REPOSITORY_ID") != "1195328534"
            or env.get("GITHUB_ACTOR") != "mfshaf7-governed-releases[bot]"
            or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("GITHUB_RUN_ATTEMPT") != "1"
            or not env.get("GITHUB_WORKFLOW_REF", "").endswith("/.github/workflows/" + WORKFLOWS[kind] + "@refs/heads/main")
            or intent["workflow_id"] != kind or intent["operator_id"] != "operator:mfshaf7"
            or intent["platform_revision"] != env.get("GITHUB_SHA")
            or not re.fullmatch(r"[a-f0-9]{40}", str(intent["platform_revision"]))
            or not re.fullmatch(r"[a-f0-9]{40}", str(intent["registry_revision"]))
            or intent["intent_digest"] != "sha256:" + request
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,255}", str(intent["command_id"]))):
        raise ValueError("Console actor, source, workflow or request binding differs from reviewed intent.")
    values = {key: env.get("RELEASE_" + key.upper(), "") for key in INPUTS[kind]}
    if digest(values) != intent["inputs_digest"]:
        raise ValueError("Workflow inputs differ from reviewed Console intent.")
    return intent


def publish(kind, env=os.environ):
    intent = guard(kind, env)
    if intent is None:
        return  # Preserve the manual workflow's existing compare-and-review path.
    run = env.get("GITHUB_RUN_ID", "")
    if not re.fullmatch(r"[1-9][0-9]*", run):
        raise ValueError("Invalid original workflow run identity.")
    if kind == "runtime":
        state = env.get("RELEASE_STATE")
        if state not in {"live", "traffic-stopped", "suspended", "quarantined"}:
            raise ValueError("Invalid runtime state.")
        branch = "prod/openclaw-" + state + "-" + run
    else:
        branch = ("stage/approve-" if kind == "readiness" else "promote/prod-") + run
    result = subprocess.run(["gh", "pr", "list", "--repo", "mfshaf7/platform-engineering", "--head", branch, "--base", "main", "--state", "all", "--json", "number"], check=True, capture_output=True, text=True)
    existing = json.loads(result.stdout)
    if existing:
        if len(existing) != 1:
            raise ValueError("Original branch has ambiguous source reviews.")
        return
    body = ("Console request: `" + intent["command_id"] + "`\n\n"
            "Reviewed intent: `" + intent["intent_digest"] + "`\n\n"
            "Accountable operator: `" + intent["operator_id"] + "`\n\n"
            "Original workflow: https://github.com/mfshaf7/platform-engineering/actions/runs/" + run + "\n\n"
            "Human source review and merge are required. Runtime health and post-release verification remain separate.\n\n"
            "If GitHub holds the PR checks, select **Approve workflows to run** and wait for required checks before merging.\n")
    subprocess.run(["gh", "pr", "create", "--repo", "mfshaf7/platform-engineering", "--base", "main", "--head", branch, "--title", "Console governed release: " + kind, "--body", body], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["guard", "publish", "summary"])
    parser.add_argument("workflow", choices=list(INPUTS))
    args = parser.parse_args()
    if args.action == "publish":
        publish(args.workflow)
    elif args.action == "summary":
        # User-entered values remain data, including quotes, newlines and $().
        values = {key: os.environ.get("RELEASE_" + key.upper(), "") for key in INPUTS[args.workflow]}
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write("## Governed release: " + args.workflow + "\n\n")
            stream.write("Human source review and merge are required for any prepared change.\n")
            stream.write("Workflow completion does not prove observed runtime health or post-release verification.\n\n")
            stream.write("Reviewed inputs:\n\n```json\n" + json.dumps(values, indent=2).replace("`", "\\u0060") + "\n```\n")
            run = os.environ["GITHUB_RUN_ID"]
            branch = ("stage/approve-" if args.workflow == "readiness" else "promote/prod-" if args.workflow == "promotion" else "prod/openclaw-" + values["state"] + "-") + run
            stream.write("\nInspect any retained branch: https://github.com/mfshaf7/platform-engineering/compare/main..." + branch + "?expand=1\n")
    else:
        intent = guard(args.workflow)
        if intent:
            with Path(os.environ["GITHUB_ENV"]).open("a") as stream:
                stream.write("RELEASE_ACCOUNTABLE_OPERATOR=" + intent["operator_id"].removeprefix("operator:") + "\n")


if __name__ == "__main__":
    main()
