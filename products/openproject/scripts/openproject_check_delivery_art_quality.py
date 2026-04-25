#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PRODUCT_DIR = SCRIPT_DIR.parent
PLANNING_WORKFLOW_PATH = PRODUCT_DIR / "delivery-art-planning-workflow.json"
PLANNING_WORKFLOW = json.loads(PLANNING_WORKFLOW_PATH.read_text(encoding="utf-8"))
INITIATIVE_REVIEW_WORKFLOW_PATH = (
    PRODUCT_DIR / "delivery-art-initiative-review-workflow.json"
)
INITIATIVE_REVIEW_WORKFLOW = json.loads(
    INITIATIVE_REVIEW_WORKFLOW_PATH.read_text(encoding="utf-8")
)

BACKLOG_ITERATION_LABEL = PLANNING_WORKFLOW["backlog_iteration_label"]
ROADMAP_UNASSIGNED_VERSION_NAME = PLANNING_WORKFLOW["roadmap_unassigned_version_name"]
ACTIVE_STATUSES = set(PLANNING_WORKFLOW["statuses"]["active"])
INACTIVE_STATUSES = {"retired"}
DONE_TREE_TERMINAL_STATUSES = {"done", "retired"}
TARGET_PI_REQUIRED_TYPES = set(
    PLANNING_WORKFLOW["planning_sets"]["target_pi_required_types"]
)
COMMITTED_ITERATION_REQUIRED_TYPES = set(
    PLANNING_WORKFLOW["planning_sets"]["iteration_required_when_target_pi_types"]
)
BACKLOG_FEATURE_CHILD_TYPES = set(
    PLANNING_WORKFLOW["planning_sets"]["backlog_feature_forbidden_child_types"]
)
FORBIDDEN_STRUCTURED_DESCRIPTION_HEADINGS = {
    "Acceptance Criteria",
    "Definition of Ready",
    "Definition of Done",
}
TAXONOMY_PATH = PRODUCT_DIR / "delivery-art-taxonomy.json"
PM2_CLOSING_PHASE = INITIATIVE_REVIEW_WORKFLOW["closing_transition"]["to_phase"]
INITIATIVE_CLOSING_REQUIRED_GATE_IDS = tuple(
    INITIATIVE_REVIEW_WORKFLOW["closing_transition"]["control_gate_ids"]
)
INITIATIVE_DONE_REQUIRED_GATE_IDS = tuple(
    INITIATIVE_REVIEW_WORKFLOW["completion_transition"]["control_gate_ids"]
)
INITIATIVE_RETIRED_REQUIRED_GATE_IDS = tuple(
    INITIATIVE_REVIEW_WORKFLOW["retirement_transition"]["control_gate_ids"]
)

INITIATIVE_REVIEW_REASON_DETAILS = {
    "system_demo_missing": {
        "issue_type_closing": "closing_initiative_missing_system_demo",
        "issue_type_done": "done_initiative_missing_system_demo",
        "detail": "System Demo Evidence must be recorded on the initiative Epic.",
        "gate_id": "initiative-closing-requires-system-demo",
    },
    "open_descendants_present": {
        "issue_type_closing": "closing_initiative_has_open_descendants",
        "issue_type_done": "done_initiative_has_open_descendants",
        "issue_type_retired": "retired_initiative_has_open_descendants",
        "detail": "Initiative still has descendants outside done or retired.",
        "gate_id": "initiative-closing-requires-clean-execution-state",
        "gate_id_retired": "initiative-retired-requires-terminal-descendants",
    },
    "pm2_phase_not_cleared_for_retired": {
        "issue_type_retired": "retired_initiative_retains_pm2_phase",
        "detail": "Retired initiative must not retain a PM² Phase value.",
        "gate_id": "initiative-retired-clears-pm2-phase",
    },
    "blocked_items_present": {
        "issue_type_closing": "closing_initiative_has_blocked_items",
        "issue_type_done": "done_initiative_has_blocked_items",
        "detail": "Initiative still has blocked descendant work.",
        "gate_id": "initiative-closing-requires-clean-execution-state",
    },
    "completion_evidence_missing": {
        "issue_type_closing": "closing_initiative_missing_descendant_completion_evidence",
        "issue_type_done": "done_initiative_missing_descendant_completion_evidence",
        "detail": "Done descendants are still missing completion evidence.",
        "gate_id": "initiative-closing-requires-clean-execution-state",
    },
    "completion_evidence_weak": {
        "issue_type_closing": "closing_initiative_has_weak_descendant_completion_evidence",
        "issue_type_done": "done_initiative_has_weak_descendant_completion_evidence",
        "detail": "Done descendants still have weak completion evidence.",
        "gate_id": "initiative-closing-requires-clean-execution-state",
    },
    "completed_items_missing_ownership": {
        "issue_type_closing": "closing_initiative_has_descendants_missing_ownership",
        "issue_type_done": "done_initiative_has_descendants_missing_ownership",
        "detail": "Done descendants are still missing Owner Repo, Assignee, or Responsible.",
        "gate_id": "initiative-closing-requires-clean-execution-state",
    },
    "done_narrative_weak": {
        "issue_type_closing": "closing_initiative_has_weak_done_narrative",
        "issue_type_done": "done_initiative_has_weak_done_narrative",
        "detail": "Done descendants still have weak done-state narrative evidence.",
        "gate_id": "initiative-closing-requires-clean-execution-state",
    },
    "unresolved_dependencies_present": {
        "issue_type_closing": "closing_initiative_has_unresolved_dependencies",
        "issue_type_done": "done_initiative_has_unresolved_dependencies",
        "detail": "Initiative still has unresolved dependency relations.",
        "gate_id": "initiative-closing-requires-clean-execution-state",
    },
    "pm2_phase_not_closing": {
        "issue_type_done": "done_initiative_not_in_closing_phase",
        "detail": "Done initiative must remain in PM² Closing.",
        "gate_id": "initiative-done-requires-closing-phase",
    },
    "inspect_and_adapt_missing": {
        "issue_type_done": "done_initiative_missing_inspect_and_adapt",
        "detail": "Inspect & Adapt Actions must be recorded before initiative closeout.",
        "gate_id": "initiative-done-requires-inspect-and-adapt",
    },
}


def load_taxonomy() -> dict[str, object]:
    with TAXONOMY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


TAXONOMY = load_taxonomy()
CLASSIFICATION_FIELD_NAME = TAXONOMY["classification_field"]["name"]
CLASSIFICATION_REQUIRED_TYPES = set(TAXONOMY["classification_field"]["required_for_types"])
CLASSIFICATION_VALUES = set(TAXONOMY["classification_field"]["values"])
LEGACY_SUBJECT_PREFIXES = set(TAXONOMY["legacy_subject_prefixes"])
STRUCTURAL_TYPES = TAXONOMY["structural_types"]
STRUCTURAL_TYPE_NAMES = set(STRUCTURAL_TYPES.keys())
SEMANTIC_PREFIXES = {
    *(
        spec.get("derived_subject_prefix")
        for spec in STRUCTURAL_TYPES.values()
        if spec.get("derived_subject_prefix")
    ),
    *(
        prefix
        for spec in STRUCTURAL_TYPES.values()
        for prefix in (spec.get("derived_subject_prefix_by_classification") or {}).values()
    ),
}


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
    return json.loads(payload)


def env_value(env: dict[str, str], key: str, default: str) -> str:
    value = (env.get(key) or "").strip()
    return value or default


def resolve_openproject_namespace(env: dict[str, str]) -> str:
    return env_value(env, "OPENPROJECT_NAMESPACE", "openproject")


def resolve_broker_namespace(env: dict[str, str]) -> str:
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
    return value if value.startswith("delivery-") else f"delivery-{value}"


def run_broker_json(path: str, *, env: dict[str, str]) -> dict[str, object]:
    kubectl = shlex.split(env.get("KUBECTL", "k3s kubectl"))
    broker_namespace = resolve_broker_namespace(env)
    broker_deployment = env_value(env, "BROKER_DEPLOYMENT", "operator-orchestration-service")
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
    initiative_id: int | None,
    target: dict[str, object],
    detail: str,
    gate_id: str | None = None,
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
            "gate_id": gate_id,
        }
    )


def add_narrative_finding(
    findings: list[dict[str, object]],
    *,
    finding_type: str,
    initiative_id: int | None,
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


def add_initiative_review_issue(
    issues: list[dict[str, object]],
    *,
    epic: dict[str, object],
    initiative_id: int,
    reason_id: str,
    transition: str,
) -> None:
    reason_detail = INITIATIVE_REVIEW_REASON_DETAILS.get(reason_id)
    if not reason_detail:
        return

    issue_key = f"issue_type_{transition}"
    issue_type = reason_detail.get(issue_key)
    if not issue_type:
        return
    gate_id = reason_detail.get(f"gate_id_{transition}", reason_detail["gate_id"])

    add_issue(
        issues,
        issue_type=issue_type,
        initiative_id=initiative_id,
        target=epic,
        detail=reason_detail["detail"],
        gate_id=gate_id,
    )


def evaluate_initiative_review_state(
    *,
    epic: dict[str, object],
    summary: dict[str, object],
) -> dict[str, object]:
    closing_reasons: list[str] = []
    if not epic.get("system_demo_evidence_present"):
        closing_reasons.append("system_demo_missing")
    if summary.get("open_descendant_count", 0) > 0:
        closing_reasons.append("open_descendants_present")
    if summary.get("blocked_count", 0) > 0:
        closing_reasons.append("blocked_items_present")
    if summary.get("completed_without_evidence_count", 0) > 0:
        closing_reasons.append("completion_evidence_missing")
    if summary.get("completed_with_weak_evidence_count", 0) > 0:
        closing_reasons.append("completion_evidence_weak")
    if summary.get("completed_with_weak_done_narrative_count", 0) > 0:
        closing_reasons.append("done_narrative_weak")
    if summary.get("completed_without_owner_count", 0) > 0:
        closing_reasons.append("completed_items_missing_ownership")
    if summary.get("unresolved_dependency_count", 0) > 0:
        closing_reasons.append("unresolved_dependencies_present")

    completion_reasons = list(closing_reasons)
    if epic.get("pm2_phase") != PM2_CLOSING_PHASE:
        completion_reasons.append("pm2_phase_not_closing")
    if not epic.get("inspect_and_adapt_actions_present"):
        completion_reasons.append("inspect_and_adapt_missing")

    retirement_reasons: list[str] = []
    if summary.get("open_descendant_count", 0) > 0:
        retirement_reasons.append("open_descendants_present")
    if epic.get("status") == "retired" and epic.get("pm2_phase"):
        retirement_reasons.append("pm2_phase_not_cleared_for_retired")

    return {
        "closing_transition_ready": len(closing_reasons) == 0,
        "closing_transition_reasons": closing_reasons,
        "completion_transition_ready": len(completion_reasons) == 0,
        "completion_transition_reasons": completion_reasons,
        "retirement_transition_ready": len(retirement_reasons) == 0,
        "retirement_transition_reasons": retirement_reasons,
    }


def detect_subject_prefix(subject: str | None) -> str | None:
    rendered = (subject or "").strip()
    for prefix in sorted(LEGACY_SUBJECT_PREFIXES | SEMANTIC_PREFIXES, key=len, reverse=True):
        if re.match(rf"^{re.escape(prefix)}:\s*", rendered, re.IGNORECASE):
            return prefix
    return None


def derived_subject_prefix(type_name: str | None, classification: str | None) -> str | None:
    if not type_name or type_name not in STRUCTURAL_TYPES:
        return None
    spec = STRUCTURAL_TYPES[type_name]
    if classification:
        classified = spec.get("derived_subject_prefix_by_classification") or {}
        if classification in classified:
            return classified[classification]
    return spec.get("derived_subject_prefix")


def required_headings(type_name: str | None, classification: str | None) -> list[str]:
    if not type_name or type_name not in STRUCTURAL_TYPES:
        return []
    headings = STRUCTURAL_TYPES[type_name]["narrative_headings"]
    if isinstance(headings, list):
        return headings
    return headings.get(classification, headings.get("default", []))


def build_subtree_scope_ids(
    work_packages_by_id: dict[int, dict[str, object]], target_epic_id: int | None
) -> set[int]:
    if target_epic_id is None:
        return set(work_packages_by_id.keys())

    children_by_parent: dict[int | None, list[int]] = defaultdict(list)
    for entry in work_packages_by_id.values():
        children_by_parent[entry.get("parent_id")].append(int(entry["id"]))

    scoped_ids: set[int] = set()
    stack = [target_epic_id]
    while stack:
        current = stack.pop()
        if current in scoped_ids:
            continue
        scoped_ids.add(current)
        stack.extend(children_by_parent.get(current, []))
    return scoped_ids


def evaluate_execution_summary(
    *,
    initiative_id: int,
    epic: dict[str, object],
    root: dict[str, object],
    issues: list[dict[str, object]],
    narrative_findings: list[dict[str, object]],
) -> None:
    all_nodes = flatten_tree(root)
    descendants = all_nodes[1:]

    for node in descendants:
        status = node.get("status")
        completion_present = bool(node.get("completion_evidence_present"))
        completion_formatting_valid = bool(node.get("completion_evidence_formatting_valid", True))
        completion_issues = node.get("completion_evidence_issues") or []
        done_narrative_applicable = bool(node.get("done_narrative_contract_applicable"))
        done_narrative_satisfied = bool(node.get("done_narrative_contract_satisfied", True))
        done_narrative_issues = node.get("done_narrative_contract_issues") or []
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
        if status == "done" and done_narrative_applicable and not done_narrative_satisfied:
            add_issue(
                issues,
                issue_type="done_item_has_weak_done_narrative_contract",
                initiative_id=initiative_id,
                target=node,
                detail=f"done work item narrative does not meet the closeout standard: {'; '.join(done_narrative_issues)}",
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
                    gate_id="committed-non-epic-must-carry-non-backlog-iteration",
                )
            if node.get("start_date") or node.get("due_date"):
                add_issue(
                    issues,
                    issue_type="backlog_item_has_schedule",
                    initiative_id=initiative_id,
                    target=node,
                    detail="backlog item marked as not committed to a PI iteration still has concrete schedule dates",
                )
        if (
            node.get("type") in COMMITTED_ITERATION_REQUIRED_TYPES
            and node.get("status") not in DONE_TREE_TERMINAL_STATUSES
            and node.get("target_pi")
            and not node.get("iteration")
        ):
            add_issue(
                issues,
                issue_type="committed_item_missing_iteration",
                initiative_id=initiative_id,
                target=node,
                detail="PI-committed non-Epic work must carry a non-backlog Iteration",
                gate_id="committed-non-epic-must-carry-non-backlog-iteration",
            )

        if (
            node.get("type") == "Feature"
            and not node.get("target_pi")
            and any(
                child.get("type") in BACKLOG_FEATURE_CHILD_TYPES
                for child in (node.get("children") or [])
                if child.get("status") not in DONE_TREE_TERMINAL_STATUSES
            )
        ):
            child_ids = ", ".join(
                f"#{child.get('id')}"
                for child in (node.get("children") or [])
                if child.get("type") in BACKLOG_FEATURE_CHILD_TYPES
                and child.get("status") not in DONE_TREE_TERMINAL_STATUSES
            )
            add_issue(
                issues,
                issue_type="backlog_feature_has_story_children",
                initiative_id=initiative_id,
                target=node,
                detail=(
                    "backlog Feature must stay umbrella-shaped until PI commitment; "
                    f"open story children: {child_ids}"
                ),
                gate_id="backlog-feature-must-stay-umbrella-shaped",
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
        node_classification = node.get("execution_classification")
        needed = required_headings(str(node_type), node_classification)
        if not needed:
            continue

        present_headings = set(node.get("description_headings") or [])
        missing_headings = [heading for heading in needed if heading not in present_headings]
        if not missing_headings:
            continue

        status = str(node.get("status"))
        target_pi = node.get("target_pi")
        iteration = node.get("iteration")
        if status in {"in-progress", "blocked"} or node_type == "Epic":
            attention_scope = "active"
            severity = "rewrite-required" if len(missing_headings) == len(needed) else "discussion-required"
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


def evaluate_live_project_taxonomy(
    *,
    project_payload: dict[str, object],
    issues: list[dict[str, object]],
    narrative_findings: list[dict[str, object]],
    scoped_ids: set[int],
) -> dict[str, object]:
    work_packages = project_payload.get("work_packages") or []
    work_packages_by_id = {
        int(entry["id"]): entry for entry in work_packages if isinstance(entry, dict) and "id" in entry
    }
    type_counts = Counter()
    prefix_counts = Counter()

    for entry_id in scoped_ids:
        entry = work_packages_by_id.get(entry_id)
        if not entry:
            continue
        type_name = entry.get("type")
        subject = entry.get("subject") or ""
        status = entry.get("status")
        classification = entry.get("execution_classification")
        parent_id = entry.get("parent_id")
        type_counts[str(type_name)] += 1
        detected_prefix = detect_subject_prefix(subject)
        prefix_counts[detected_prefix or "<none>"] += 1

        if type_name == "Enabler":
            add_issue(
                issues,
                issue_type="legacy_enabler_type_present",
                initiative_id=None,
                target=entry,
                detail="Enabler must no longer exist as a structural type; use Feature or User story with Execution Classification instead",
            )

        if type_name not in STRUCTURAL_TYPE_NAMES:
            add_issue(
                issues,
                issue_type="unsupported_structural_type",
                initiative_id=None,
                target=entry,
                detail=f"type {type_name} is not part of the canonical delivery taxonomy",
            )
            continue

        if parent_id is None:
            if type_name != "Epic":
                add_issue(
                    issues,
                    issue_type="root_non_epic_work_item",
                    initiative_id=None,
                    target=entry,
                    detail="only Epic may exist at the project root",
                )
        else:
            parent = work_packages_by_id.get(int(parent_id))
            if parent is None:
                add_issue(
                    issues,
                    issue_type="missing_parent_reference",
                    initiative_id=None,
                    target=entry,
                    detail=f"parent work package {parent_id} is missing from the project dump",
                )
            else:
                allowed_parent_types = STRUCTURAL_TYPES[type_name]["allowed_parent_types"]
                if parent.get("type") not in allowed_parent_types:
                    add_issue(
                        issues,
                        issue_type="invalid_parent_type",
                        initiative_id=None,
                        target=entry,
                        detail=f"{type_name} must be parented by {', '.join(allowed_parent_types)}, not {parent.get('type')}",
                    )

        if type_name in CLASSIFICATION_REQUIRED_TYPES:
            if not classification:
                add_issue(
                    issues,
                    issue_type="missing_execution_classification",
                    initiative_id=None,
                    target=entry,
                    detail=f"{type_name} requires {CLASSIFICATION_FIELD_NAME}",
                )
            elif classification not in CLASSIFICATION_VALUES:
                add_issue(
                    issues,
                    issue_type="invalid_execution_classification",
                    initiative_id=None,
                    target=entry,
                    detail=f"{classification} is not an allowed {CLASSIFICATION_FIELD_NAME} value",
                )
        elif classification:
            add_issue(
                issues,
                issue_type="unexpected_execution_classification",
                initiative_id=None,
                target=entry,
                detail=f"{CLASSIFICATION_FIELD_NAME} is not allowed on {type_name}",
            )

        target_pi = entry.get("target_pi")
        version_name = entry.get("version_name")
        if target_pi and version_name != target_pi:
            add_issue(
                issues,
                issue_type="target_pi_version_drift",
                initiative_id=None,
                target=entry,
                detail=f"Target PI {target_pi!r} must project to matching version, not {version_name!r}",
                gate_id="roadmap-version-must-match-target-pi-projection",
            )
        elif not target_pi and version_name != ROADMAP_UNASSIGNED_VERSION_NAME:
            issue_type = (
                "roadmap_unassigned_bucket_missing"
                if not version_name
                else "version_without_target_pi"
            )
            add_issue(
                issues,
                issue_type=issue_type,
                initiative_id=None,
                target=entry,
                detail=(
                    f"work without canonical Target PI must project to derived roadmap bucket "
                    f"{ROADMAP_UNASSIGNED_VERSION_NAME!r}, not {version_name!r}"
                ),
                gate_id="roadmap-version-must-match-target-pi-projection",
            )

        if (
            type_name != "Epic"
            and status in {"ready", "in-progress", "blocked"}
            and not target_pi
        ):
            add_issue(
                issues,
                issue_type="active_item_missing_target_pi_commitment",
                initiative_id=None,
                target=entry,
                detail=(
                    "non-epic work in ready, in-progress, or blocked must carry canonical "
                    "Target PI instead of remaining in the unassigned backlog bucket"
                ),
                gate_id="active-non-epic-must-not-stay-uncommitted",
            )

        if type_name in TARGET_PI_REQUIRED_TYPES and not target_pi:
            add_issue(
                issues,
                issue_type="target_pi_required_type_missing_commitment",
                initiative_id=None,
                target=entry,
                detail=f"{type_name} must carry canonical Target PI before it exists in ART",
                gate_id="target-pi-required-on-committed-leaf-types",
            )

        if (
            type_name == "Defect"
            and not target_pi
            and status != "new"
        ):
            add_issue(
                issues,
                issue_type="backlog_defect_not_new",
                initiative_id=None,
                target=entry,
                detail="Defect without Target PI must stay in new backlog posture until committed",
                gate_id="active-non-epic-must-not-stay-uncommitted",
            )

        iteration = entry.get("iteration")
        if (
            type_name in COMMITTED_ITERATION_REQUIRED_TYPES
            and type_name != "Epic"
            and status not in DONE_TREE_TERMINAL_STATUSES
            and target_pi
            and not iteration
        ):
            add_issue(
                issues,
                issue_type="committed_item_missing_iteration",
                initiative_id=None,
                target=entry,
                detail="PI-committed non-Epic work must carry a non-backlog Iteration",
                gate_id="committed-non-epic-must-carry-non-backlog-iteration",
            )

        expected_prefix = derived_subject_prefix(type_name, classification)
        if detected_prefix in LEGACY_SUBJECT_PREFIXES:
            add_issue(
                issues,
                issue_type="legacy_subject_prefix_present",
                initiative_id=None,
                target=entry,
                detail=f"legacy prefix {detected_prefix}: is no longer allowed in ART subjects",
            )
        elif expected_prefix and detected_prefix != expected_prefix:
            add_issue(
                issues,
                issue_type="derived_subject_prefix_mismatch",
                initiative_id=None,
                target=entry,
                detail=f"{type_name} with classification {classification or 'Business'} must use subject prefix {expected_prefix}:",
            )
        elif not expected_prefix and detected_prefix in SEMANTIC_PREFIXES:
            add_issue(
                issues,
                issue_type="semantic_subject_prefix_not_allowed",
                initiative_id=None,
                target=entry,
                detail=f"subject prefix {detected_prefix}: is not allowed on structural type {type_name}",
            )

        if status in {"ready", "in-progress", "blocked"}:
            needed = required_headings(type_name, classification)
            present = set(entry.get("description_headings") or [])
            missing = [heading for heading in needed if heading not in present]
            if missing:
                add_narrative_finding(
                    narrative_findings,
                    finding_type="missing_required_narrative_headings",
                    initiative_id=None,
                    target=entry,
                    severity="discussion-required" if status == "ready" else "rewrite-required",
                    attention_scope="next-up" if status == "ready" else "active",
                    missing_headings=missing,
                    detail=f"{type_name} is missing required narrative headings: {', '.join(missing)}",
                )

    return {
        "scoped_work_package_count": len(scoped_ids),
        "type_counts": dict(sorted(type_counts.items())),
        "subject_prefix_counts": dict(sorted(prefix_counts.items())),
    }


def main() -> int:
    env = os.environ.copy()
    include_done = env.get("INCLUDE_DONE", "true")
    target_epic_id = env.get("TARGET_EPIC_ID", "").strip()
    scoped_execution_only = bool(target_epic_id)
    include_done_param = "true" if include_done == "true" else "false"

    quality_pack_payload = run_broker_json("/v1/delivery-session/quality-pack", env=env)
    quality_pack = quality_pack_payload.get("quality_pack") or {}
    work_packages = quality_pack.get("work_packages") or []
    work_packages_by_id = {
        int(entry["id"]): entry for entry in work_packages if isinstance(entry, dict) and "id" in entry
    }
    scoped_ids = build_subtree_scope_ids(
        work_packages_by_id,
        int(target_epic_id) if target_epic_id else None,
    )

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
            f"/v1/delivery-initiatives?include_done={include_done_param}&include_inactive=true",
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
        evaluate_execution_summary(
            initiative_id=initiative_id,
            epic=epic,
            root=root,
            issues=issues,
            narrative_findings=narrative_findings,
        )
        initiative_review = evaluate_initiative_review_state(
            epic=epic,
            summary=execution_summary.get("summary") or {},
        )
        if epic.get("pm2_phase") == PM2_CLOSING_PHASE:
            for reason_id in initiative_review["closing_transition_reasons"]:
                add_initiative_review_issue(
                    issues,
                    epic=epic,
                    initiative_id=initiative_id,
                    reason_id=reason_id,
                    transition="closing",
                )
        if epic.get("status") == "done":
            for reason_id in initiative_review["completion_transition_reasons"]:
                add_initiative_review_issue(
                    issues,
                    epic=epic,
                    initiative_id=initiative_id,
                    reason_id=reason_id,
                    transition="done",
                )
        if epic.get("status") == "retired":
            for reason_id in initiative_review["retirement_transition_reasons"]:
                add_initiative_review_issue(
                    issues,
                    epic=epic,
                    initiative_id=initiative_id,
                    reason_id=reason_id,
                    transition="retired",
                )

    project_taxonomy_summary = evaluate_live_project_taxonomy(
        project_payload=quality_pack,
        issues=issues,
        narrative_findings=narrative_findings,
        scoped_ids=scoped_ids,
    )

    result = {
        "project": initiatives_payload.get("project"),
        "openproject_project": quality_pack_payload.get("project"),
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
            "initiative_ids_with_issues": sorted(
                {issue["initiative_id"] for issue in issues if issue["initiative_id"] is not None}
            ),
            "initiative_ids_with_narrative_findings": sorted(
                {
                    finding["initiative_id"]
                    for finding in narrative_findings
                    if finding["initiative_id"] is not None
                }
            ),
            "discussion_required_before_execution": any(
                finding["severity"] in {"rewrite-required", "discussion-required"}
                and finding["attention_scope"] in {"active", "next-up"}
                for finding in narrative_findings
            ),
        },
        "workflow_health": {
            "compatible_views": quality_pack.get("compatible_views") or {},
            "projection_health": quality_pack.get("projection_health") or {},
            "summary": quality_pack.get("summary") or {},
        },
        "project_taxonomy_summary": project_taxonomy_summary,
        "issues": issues,
        "narrative_findings": narrative_findings,
    }

    print(json.dumps(result, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
