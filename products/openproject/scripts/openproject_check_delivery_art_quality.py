#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SHOW_INITIATIVES = REPO_ROOT / "products" / "openproject" / "scripts" / "openproject_show_delivery_initiatives.sh"
SHOW_EXECUTION = REPO_ROOT / "products" / "openproject" / "scripts" / "openproject_show_delivery_execution.sh"
BACKLOG_ITERATION_LABEL = "Not committed to a PI iteration yet."
ACTIVE_STATUSES = {"ready", "in-progress", "blocked"}
INACTIVE_STATUSES = {"retired"}
NARRATIVE_REQUIREMENTS = {
    "Epic": ["Current PI Focus", "Scope Boundaries"],
    "PI Objective": ["Outcome Statement", "Why This PI", "Success Signal"],
    "Risk": ["Trigger", "Impact", "Disposition"],
    "Feature": ["Delivery Outcome", "Scope Boundaries"],
    "Enabler": ["Delivery Outcome", "Runway Need"],
    "User story": ["Concrete Output", "Evidence Expectation"],
    "Task": ["Concrete Output", "Evidence Expectation"],
    "Milestone": ["Exit Condition"],
}


def run_json(command: list[str], *, env: dict[str, str]) -> dict[str, object]:
    actual_command = ["bash", command[0], *command[1:]] if command and command[0].endswith(".sh") else command
    try:
        completed = subprocess.run(actual_command, capture_output=True, text=True, env=env, check=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or f"exit status {exc.returncode}"
        raise RuntimeError(f"command failed: {' '.join(actual_command)}: {detail}") from exc
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
        raise RuntimeError(f"command returned no JSON payload: {' '.join(actual_command)}")
    return json.loads(payload)


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

    if scoped_execution_only:
        initiatives_payload = {
            "project": None,
            "initiatives": [],
        }
        initiatives = [
            {
                "epic": {
                    "id": int(target_epic_id),
                },
            }
        ]
    else:
        initiatives_payload = run_json([str(SHOW_INITIATIVES)], env=env)
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

        execution_payload = run_json(
            [str(SHOW_EXECUTION)],
            env={
                **env,
                "TARGET_EPIC_ID": str(initiative_id),
                "INCLUDE_DONE": include_done,
                "INCLUDE_PARKED": "true",
            },
        )
        root = execution_payload.get("epic")
        if not isinstance(root, dict):
            raise RuntimeError(f"unexpected execution payload shape for initiative {initiative_id}")
        epic = root
        descendants = flatten_tree(root)[1:]

        for node in descendants:
            status = node.get("status")
            completion_present = bool(node.get("completion_evidence_present"))
            if status == "done" and not completion_present:
                add_issue(
                    issues,
                    issue_type="done_item_missing_completion_evidence",
                    initiative_id=initiative_id,
                    target=node,
                    detail="done work item is missing substantive completion evidence",
                )
            if status != "done" and completion_present:
                add_issue(
                    issues,
                    issue_type="non_done_item_has_completion_evidence",
                    initiative_id=initiative_id,
                    target=node,
                    detail="non-done work item still carries completion evidence sections",
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
