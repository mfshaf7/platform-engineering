#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys


BACKLOG_ITERATION_LABEL = "Not committed to a PI iteration yet."
ACTIVE_STATUSES = {"ready", "in-progress", "blocked"}
INACTIVE_STATUSES = {"retired"}
DONE_TREE_TERMINAL_STATUSES = {"done", "retired"}
NARRATIVE_REQUIREMENTS = {
    "Epic": ["What This Initiative Achieves", "Current PI Focus", "Scope Boundaries", "Execution Context"],
    "PI Objective": ["Outcome", "Why This PI", "Success Signal", "Execution Context"],
    "Risk": ["Risk Event", "Impact", "Current Handling", "Execution Context"],
    "Feature": ["What This Achieves", "Benefit Hypothesis", "Scope Boundaries", "Execution Context"],
    "Enabler": ["What This Enables", "Benefit Hypothesis", "Scope Boundaries", "Execution Context"],
    "User story": ["What This Achieves", "Why This Matters Now", "Evidence Expectation", "Execution Context"],
    "Task": ["What This Achieves", "Why This Matters Now", "Evidence Expectation", "Execution Context"],
    "Milestone": ["Exit Condition", "Execution Context"],
}
FORBIDDEN_STRUCTURED_DESCRIPTION_HEADINGS = {
    "Acceptance Criteria",
    "Definition of Ready",
    "Definition of Done",
}


def run_json(command: list[str], *, env: dict[str, str]) -> dict[str, object]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, env=env, check=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or f"exit status {exc.returncode}"
        raise RuntimeError(f"command failed: {' '.join(command)}: {detail}") from exc
    lines = completed.stdout.splitlines()
    cleaned = "\n".join(
        line for line in lines
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
    return json.loads(payload)


def resolve_broker_namespace(env: dict[str, str]) -> str:
    broker_namespace = (env.get("BROKER_NAMESPACE") or "").strip()
    if broker_namespace:
        return broker_namespace
    openproject_namespace = (env.get("OPENPROJECT_NAMESPACE") or "openproject").strip() or "openproject"
    if openproject_namespace == "openproject":
        return "operator-orchestration-service"
    return openproject_namespace


def normalize_delivery_id(raw_id: str) -> str:
    value = raw_id.strip()
    if not value:
        raise RuntimeError("delivery id is required")
    return value if value.startswith("delivery-") else f"delivery-{value}"


def run_broker_json(path: str, *, env: dict[str, str]) -> dict[str, object]:
    kubectl = shlex.split(env.get("KUBECTL", "k3s kubectl"))
    broker_namespace = resolve_broker_namespace(env)
    broker_deployment = env.get("BROKER_DEPLOYMENT", "operator-orchestration-service")
    broker_port = env.get("BROKER_PORT", "8080")
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


def flatten_tree(node: dict[str, object]) -> list[dict[str, object]]:
    children = node.get("children") or []
    flattened = [node]
    for child in children:
        flattened.extend(flatten_tree(child))
    return flattened


def add_issue(
    issues: list[dict[str, object]],
    *,
    issue_type: str,
    initiative_id: int,
    target: dict[str, object],
    detail: str,
) -> None:
    issues.append(
        {
            "issue_type": issue_type,
            "initiative_id": initiative_id,
            "work_package_id": target.get("id"),
            "work_package_ref": target.get("record_ref"),
            "subject": target.get("subject"),
            "status": target.get("status"),
            "detail": detail,
        }
    )


def add_narrative_finding(
    findings: list[dict[str, object]],
    *,
    finding_type: str,
    initiative_id: int,
    target: dict[str, object],
    severity: str,
    attention_scope: str,
    missing_headings: list[str],
    detail: str,
) -> None:
    findings.append(
        {
            "finding_type": finding_type,
            "initiative_id": initiative_id,
            "work_package_id": target.get("id"),
            "work_package_ref": target.get("record_ref"),
            "subject": target.get("subject"),
            "type": target.get("type"),
            "status": target.get("status"),
            "severity": severity,
            "attention_scope": attention_scope,
            "missing_headings": missing_headings,
            "detail": detail,
        }
    )


def main() -> int:
    env = os.environ.copy()
    include_done = env.get("INCLUDE_DONE", "true")
    target_epic_id = env.get("TARGET_EPIC_ID", "").strip()
    scoped_execution_only = bool(target_epic_id)
    include_done_param = "true" if include_done == "true" else "false"

    if scoped_execution_only:
        initiatives_payload = {
            "project": None,
            "initiatives": [],
        }
        initiatives = [
            {
                "epic": {
                    "id": int(normalize_delivery_id(target_epic_id).split("-", 1)[1]),
                },
            }
        ]
    else:
        initiatives_payload = run_broker_json(
            f"/v1/delivery-initiatives?include_done={include_done_param}&include_inactive=false",
            env=env,
        )
        initiatives = initiatives_payload.get("initiatives", [])
        if not isinstance(initiatives, list):
            raise RuntimeError("unexpected initiative payload shape")

    issues: list[dict[str, object]] = []
    narrative_findings: list[dict[str, object]] = []

    for initiative in initiatives:
        epic = initiative.get("epic") or {}
        if not isinstance(epic, dict):
            continue
        initiative_id = int(epic["id"])
        epic_status = epic.get("status")
        if not scoped_execution_only and epic_status not in {"new", "parked", "retired"}:
            if not epic.get("pm2_phase"):
                add_issue(
                    issues,
                    issue_type="initiative_missing_pm2_phase",
                    initiative_id=initiative_id,
                    target=epic,
                    detail="active initiative is missing PM² Phase",
                )
            if not epic.get("sponsor"):
                add_issue(
                    issues,
                    issue_type="initiative_missing_sponsor",
                    initiative_id=initiative_id,
                    target=epic,
                    detail="active initiative is missing Sponsor",
                )
            if not epic.get("business_objective_present"):
                add_issue(
                    issues,
                    issue_type="initiative_missing_business_objective",
                    initiative_id=initiative_id,
                    target=epic,
                    detail="active initiative is missing Business Objective",
                )
            if not epic.get("success_criteria_present"):
                add_issue(
                    issues,
                    issue_type="initiative_missing_success_criteria",
                    initiative_id=initiative_id,
                    target=epic,
                    detail="active initiative is missing Success Criteria",
                )

        execution_payload = run_broker_json(
            (
                f"/v1/delivery-initiatives/{normalize_delivery_id(str(initiative_id))}"
                f"/execution-summary?include_done={include_done_param}&include_parked=true"
            ),
            env=env,
        )
        execution_summary = execution_payload.get("execution_summary")
        if not isinstance(execution_summary, dict):
            raise RuntimeError(f"unexpected execution payload shape for initiative {initiative_id}")
        epic = execution_summary.get("epic")
        root = execution_summary.get("execution_tree")
        if not isinstance(epic, dict) or not isinstance(root, dict):
            raise RuntimeError(f"unexpected execution payload shape for initiative {initiative_id}")
        all_nodes = flatten_tree(root)
        descendants = all_nodes[1:]

        for node in descendants:
            status = node.get("status")
            completion_present = bool(node.get("completion_evidence_present"))
            completion_formatting_valid = bool(node.get("completion_evidence_formatting_valid", True))
            completion_issues = node.get("completion_evidence_issues") or []
            present_headings = set(node.get("description_headings") or [])
            duplicated_structured_headings = sorted(
                present_headings & FORBIDDEN_STRUCTURED_DESCRIPTION_HEADINGS
            )
            if status == "done" and not completion_present:
                add_issue(
                    issues,
                    issue_type="done_item_missing_completion_evidence",
                    initiative_id=initiative_id,
                    target=node,
                    detail="done work item is missing substantive completion evidence",
                )
            if status == "done" and completion_present and not completion_formatting_valid:
                add_issue(
                    issues,
                    issue_type="done_item_has_weak_completion_evidence",
                    initiative_id=initiative_id,
                    target=node,
                    detail=f"done work item completion evidence does not meet the closeout standard: {'; '.join(completion_issues)}",
                )
            if status != "done" and completion_present:
                add_issue(
                    issues,
                    issue_type="non_done_item_has_completion_evidence",
                    initiative_id=initiative_id,
                    target=node,
                    detail="non-done work item still carries completion evidence sections",
                )
            if duplicated_structured_headings:
                add_issue(
                    issues,
                    issue_type="description_duplicates_structured_execution_fields",
                    initiative_id=initiative_id,
                    target=node,
                    detail=(
                        "description duplicates structured execution fields as markdown headings: "
                        + ", ".join(duplicated_structured_headings)
                    ),
                )
            if not node.get("description_starts_with_heading", False) and node.get("description_present"):
                add_issue(
                    issues,
                    issue_type="description_does_not_start_with_heading",
                    initiative_id=initiative_id,
                    target=node,
                    detail="description must start with a markdown heading instead of loose prose",
                )
            if status in ACTIVE_STATUSES and node.get("ready_contract_applicable") and not node.get("ready_contract_satisfied"):
                missing = node.get("ready_contract_missing_fields") or []
                add_issue(
                    issues,
                    issue_type="active_item_missing_execution_contract",
                    initiative_id=initiative_id,
                    target=node,
                    detail=f"active work item is missing required execution fields: {', '.join(missing)}",
                )
            if status == "done":
                missing_done_ownership: list[str] = []
                if not node.get("assignee_login"):
                    missing_done_ownership.append("Assignee")
                if not node.get("responsible_login"):
                    missing_done_ownership.append("Responsible")
                if not node.get("owner_repo"):
                    missing_done_ownership.append("Owner Repo")
                if missing_done_ownership:
                    add_issue(
                        issues,
                        issue_type="done_item_missing_ownership_contract",
                        initiative_id=initiative_id,
                        target=node,
                        detail=f"done work item is missing required ownership fields: {', '.join(missing_done_ownership)}",
                    )

            if node.get("iteration") == BACKLOG_ITERATION_LABEL:
                if node.get("target_pi"):
                    add_issue(
                        issues,
                        issue_type="backlog_item_has_target_pi",
                        initiative_id=initiative_id,
                        target=node,
                        detail="backlog item marked as not committed to a PI iteration still has Target PI assigned",
                    )
                if node.get("start_date") or node.get("due_date"):
                    add_issue(
                        issues,
                        issue_type="backlog_item_has_schedule",
                        initiative_id=initiative_id,
                        target=node,
                        detail="backlog item marked as not committed to a PI iteration still has concrete schedule dates",
                    )

        for node in all_nodes:
            if node.get("status") != "done":
                continue

            blocking_descendants = [
                descendant
                for descendant in flatten_tree(node)[1:]
                if descendant.get("status") not in DONE_TREE_TERMINAL_STATUSES
            ]
            if not blocking_descendants:
                continue

            rendered_descendants = ", ".join(
                f"#{descendant.get('id')} ({descendant.get('status')})"
                for descendant in blocking_descendants[:5]
            )
            overflow_note = (
                f" and {len(blocking_descendants) - 5} more"
                if len(blocking_descendants) > 5
                else ""
            )
            add_issue(
                issues,
                issue_type="done_item_has_open_descendants",
                initiative_id=initiative_id,
                target=node,
                detail=(
                    "done work item still has descendants outside done or retired: "
                    f"{rendered_descendants}{overflow_note}"
                ),
            )

        narrative_targets = [
            epic,
            *[
                node
                for node in descendants
                if node.get("status") not in {"done", *INACTIVE_STATUSES}
            ],
        ]
        for node in narrative_targets:
            node_type = node.get("type")
            required_headings = NARRATIVE_REQUIREMENTS.get(str(node_type), [])
            if not required_headings:
                continue

            present_headings = set(node.get("description_headings") or [])
            missing_headings = [heading for heading in required_headings if heading not in present_headings]
            if not missing_headings:
                continue

            status = str(node.get("status"))
            target_pi = node.get("target_pi")
            iteration = node.get("iteration")
            if status in {"in-progress", "blocked"} or node_type == "Epic":
                attention_scope = "active"
                severity = "rewrite-required" if len(missing_headings) == len(required_headings) else "discussion-required"
            elif status == "ready" or (target_pi and iteration != BACKLOG_ITERATION_LABEL):
                attention_scope = "next-up"
                severity = "discussion-required"
            else:
                attention_scope = "backlog"
                severity = "polish"

            add_narrative_finding(
                narrative_findings,
                finding_type="missing_required_narrative_headings",
                initiative_id=initiative_id,
                target=node,
                severity=severity,
                attention_scope=attention_scope,
                missing_headings=missing_headings,
                detail=f"{node_type} is missing required narrative headings: {', '.join(missing_headings)}",
            )

    result = {
        "project": initiatives_payload.get("project"),
        "scope": {
            "include_done": include_done == "true",
            "mode": "scoped-execution" if scoped_execution_only else "full-portfolio",
            "target_epic_id": int(target_epic_id) if target_epic_id else None,
        },
        "summary": {
            "initiatives_checked": len(initiatives),
            "issue_count": len(issues),
            "narrative_finding_count": len(narrative_findings),
            "issue_types": {
                issue_type: sum(1 for issue in issues if issue["issue_type"] == issue_type)
                for issue_type in sorted({issue["issue_type"] for issue in issues})
            },
            "narrative_finding_types": {
                finding_type: sum(1 for finding in narrative_findings if finding["finding_type"] == finding_type)
                for finding_type in sorted({finding["finding_type"] for finding in narrative_findings})
            },
            "narrative_findings_by_severity": {
                severity: sum(1 for finding in narrative_findings if finding["severity"] == severity)
                for severity in sorted({finding["severity"] for finding in narrative_findings})
            },
            "initiative_ids_with_issues": sorted({issue["initiative_id"] for issue in issues}),
            "initiative_ids_with_narrative_findings": sorted({finding["initiative_id"] for finding in narrative_findings}),
            "discussion_required_before_execution": any(
                finding["severity"] in {"rewrite-required", "discussion-required"}
                and finding["attention_scope"] in {"active", "next-up"}
                for finding in narrative_findings
            ),
        },
        "issues": issues,
        "narrative_findings": narrative_findings,
    }

    print(json.dumps(result, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
