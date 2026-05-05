import importlib.util
import pathlib
import unittest
from unittest import mock


SCRIPT_PATH = pathlib.Path(__file__).resolve().parent / "openproject_check_delivery_art_quality.py"
SPEC = importlib.util.spec_from_file_location(
    "openproject_check_delivery_art_quality", SCRIPT_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DeliveryArtQualityTest(unittest.TestCase):
    def test_planning_workflow_contract_constants_are_loaded(self) -> None:
        self.assertEqual(
            MODULE.BACKLOG_ITERATION_LABEL,
            "Not committed to a PI iteration yet.",
        )
        self.assertIn("ready", MODULE.ACTIVE_STATUSES)
        self.assertIn("PI Objective", MODULE.TARGET_PI_REQUIRED_TYPES)
        self.assertNotIn("User story", MODULE.TARGET_PI_REQUIRED_TYPES)
        self.assertNotIn("User story", MODULE.BACKLOG_FEATURE_CHILD_TYPES)
        self.assertIn("User story", MODULE.BACKLOG_FEATURE_PLANNED_CHILD_TYPES)
        self.assertIn("Defect", MODULE.FEATURE_LEAF_FRONT_CHILD_TYPES)
        self.assertIn("active", MODULE.PI_LIFECYCLE["states"])
        self.assertIn(
            "<target_pi> / ",
            MODULE.PI_ITERATION_ALLOWED_PREFIX_TEMPLATES,
        )
        self.assertTrue(
            MODULE.iteration_matches_target_pi(
                "PI-2026-03",
                "PI-2026-03 / Iteration 1",
            )
        )
        self.assertTrue(
            MODULE.iteration_matches_target_pi(
                "PI-2026-03",
                "Program-wide / planning",
            )
        )
        self.assertFalse(
            MODULE.iteration_matches_target_pi(
                "PI-2026-03",
                "PI-2026-02 / Iteration 1",
            )
        )

    def test_initiative_review_workflow_contract_constants_are_loaded(self) -> None:
        self.assertEqual(MODULE.PM2_CLOSING_PHASE, "Closing")
        self.assertIn(
            "initiative-closing-requires-system-demo",
            MODULE.INITIATIVE_CLOSING_REQUIRED_GATE_IDS,
        )
        self.assertIn(
            "initiative-done-requires-inspect-and-adapt",
            MODULE.INITIATIVE_DONE_REQUIRED_GATE_IDS,
        )
        self.assertIn(
            "initiative-retired-requires-terminal-descendants",
            MODULE.INITIATIVE_RETIRED_REQUIRED_GATE_IDS,
        )

    def test_blocker_workflow_contract_constants_are_loaded(self) -> None:
        self.assertEqual(MODULE.BLOCKED_STATUS, "blocked")
        self.assertIn("statement", MODULE.BLOCKER_REQUIRED_RESPONSE_KEYS)
        self.assertIn("follow_up_owner", MODULE.BLOCKER_FOLLOW_UP_RESPONSE_KEYS)

    def test_initiative_lineage_contract_constants_are_loaded(self) -> None:
        self.assertEqual(MODULE.INITIATIVE_FAMILY_FIELD_NAME, "Initiative Family")
        self.assertIn("governed-ai-control-plane", MODULE.INITIATIVE_FAMILY_KEYS)
        self.assertIn(
            "bounded-activation",
            MODULE.INITIATIVE_LINEAGE_ROLE_RULES,
        )

    def test_blank_env_values_fall_back_to_defaults(self) -> None:
        self.assertEqual(
            MODULE.resolve_openproject_namespace({"OPENPROJECT_NAMESPACE": ""}),
            "openproject",
        )
        self.assertEqual(
            MODULE.env_value({"BROKER_PORT": ""}, "BROKER_PORT", "8080"),
            "8080",
        )

    def test_polish_narrative_findings_are_summarized_by_default(self) -> None:
        findings = [
            {
                "finding_type": "description_does_not_start_with_heading",
                "severity": "polish",
                "work_package_id": 427,
            },
            {
                "finding_type": "missing_required_narrative_headings",
                "severity": "discussion-required",
                "work_package_id": 422,
            },
        ]

        self.assertEqual(
            MODULE.filter_narrative_findings_for_output(
                findings,
                include_polish_details=False,
            ),
            [findings[1]],
        )
        self.assertEqual(
            MODULE.filter_narrative_findings_for_output(
                findings,
                include_polish_details=True,
            ),
            findings,
        )

    def test_broker_namespace_defaults_to_openproject_namespace_for_profiles(self) -> None:
        self.assertEqual(
            MODULE.resolve_broker_namespace(
                {"OPENPROJECT_NAMESPACE": "devint-accepted-idea-delivery-mfshaf7"}
            ),
            "devint-accepted-idea-delivery-mfshaf7",
        )

    def test_broker_namespace_defaults_to_shared_namespace_for_default_openproject(self) -> None:
        self.assertEqual(
            MODULE.resolve_broker_namespace({"OPENPROJECT_NAMESPACE": "openproject"}),
            "operator-orchestration-service",
        )

    def test_done_state_narrative_drift_is_a_hard_failure(self) -> None:
        issues = []
        narrative_findings = []
        epic = {
            "id": 38,
            "record_ref": "openproject://work_packages/38",
            "status": "in-progress",
            "subject": "Establish the governed enterprise AI agent control plane and runtime foundation",
            "type": "Epic",
            "description_headings": [
                "What This Initiative Achieves",
                "Current PI Focus",
                "Scope Boundaries",
                "Execution Context",
            ],
        }
        root = {
            "id": 38,
            "children": [
                {
                    "assignee_login": "Operator Orchestration Service",
                    "children": [],
                    "completion_evidence_formatting_valid": True,
                    "completion_evidence_issues": [],
                    "completion_evidence_present": True,
                    "description_headings": [
                        "What This Achieves",
                        "Why This Matters Now",
                        "Evidence Expectation",
                        "Execution Context",
                    ],
                    "description_present": True,
                    "description_starts_with_heading": True,
                    "done_narrative_contract_applicable": True,
                    "done_narrative_contract_issues": [
                        "Execution Context: missing bullet `Parent item:`"
                    ],
                    "done_narrative_contract_satisfied": False,
                    "id": 214,
                    "iteration": "PI-2026-02 / local follow-on",
                    "owner_repo": "operator-orchestration-service",
                    "parent_id": 213,
                    "record_ref": "openproject://work_packages/214",
                    "responsible_login": "Operator Orchestration Service",
                    "status": "done",
                    "subject": "Enforce done-state ART narrative quality on broker complete and update writes",
                    "type": "Task",
                }
            ],
        }

        MODULE.evaluate_execution_summary(
            initiative_id=38,
            epic=epic,
            root=root,
            issues=issues,
            narrative_findings=narrative_findings,
        )

        self.assertEqual(len(narrative_findings), 0)
        self.assertTrue(
            any(
                issue["issue_type"] == "done_item_has_weak_done_narrative_contract"
                and "Parent item" in issue["detail"]
                for issue in issues
            )
        )

    def test_retired_initiative_requires_terminal_descendants(self) -> None:
        result = MODULE.evaluate_initiative_review_state(
            epic={
                "inspect_and_adapt_actions_present": False,
                "pm2_phase": "Executing",
                "status": "retired",
                "system_demo_evidence_present": False,
            },
            summary={
                "blocked_count": 0,
                "completed_with_weak_done_narrative_count": 0,
                "completed_with_weak_evidence_count": 0,
                "completed_without_evidence_count": 0,
                "completed_without_owner_count": 0,
                "open_descendant_count": 1,
                "unresolved_dependency_count": 0,
            },
        )

        self.assertFalse(result["retirement_transition_ready"])
        self.assertEqual(
            result["retirement_transition_reasons"],
            ["open_descendants_present", "pm2_phase_not_cleared_for_retired"],
        )

    def test_initiative_lineage_missing_family_is_reported_outside_shell_posture(self) -> None:
        issues = []
        MODULE.evaluate_initiative_lineage_state(
            epic={
                "id": 251,
                "record_ref": "openproject://work_packages/251",
                "status": "planning",
                "subject": "Activate the first bounded governed AI assist path",
                "target_pi": "PI-2026-03",
                "pm2_phase": "Planning",
            },
            initiative_id=251,
            initiatives_by_id={},
            issues=issues,
            work_packages_by_id={},
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "initiative_missing_family"
                and issue["gate_id"]
                == "initiative-family-required-before-planning-or-commitment"
                for issue in issues
            )
        )

    def test_initiative_lineage_anchor_family_mismatch_is_reported(self) -> None:
        issues = []
        MODULE.evaluate_initiative_lineage_state(
            epic={
                "id": 251,
                "record_ref": "openproject://work_packages/251",
                "status": "new",
                "subject": "Activate the first bounded governed AI assist path",
                "target_pi": "PI-2026-03",
                "pm2_phase": "Planning",
                "initiative_family": "enterprise-cybersecurity-baseline",
                "lineage_role": "bounded-activation",
                "architecture_anchor_ref": "openproject://work_packages/38",
                "required_upstream_ref": "openproject://work_packages/245",
            },
            initiative_id=251,
            initiatives_by_id={
                38: {
                    "epic": {
                        "id": 38,
                        "initiative_family": "governed-ai-control-plane",
                    }
                }
            },
            issues=issues,
            work_packages_by_id={
                245: {
                    "id": 245,
                    "parent_id": 227,
                },
                227: {
                    "id": 227,
                    "parent_id": None,
                },
            },
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "initiative_anchor_family_mismatch"
                and issue["gate_id"] == "initiative-anchor-family-must-match"
                for issue in issues
            )
        )

    def test_target_pi_version_drift_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 257,
                    "record_ref": "openproject://work_packages/257",
                    "subject": "Project ART Target PI into roadmap-compatible OpenProject versions and backfill existing drift",
                    "type": "Feature",
                    "status": "in-progress",
                    "parent_id": 256,
                    "execution_classification": "Business",
                    "description_headings": [
                        "What This Achieves",
                        "Benefit Hypothesis",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-02",
                    "version_name": None,
                },
                {
                    "id": 256,
                    "record_ref": "openproject://work_packages/256",
                    "subject": "Keep the OpenProject roadmap view truthful to ART PI placement",
                    "type": "Epic",
                    "status": "in-progress",
                    "parent_id": None,
                    "execution_classification": None,
                    "description_headings": [
                        "What This Initiative Achieves",
                        "Current PI Focus",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-02",
                    "version_name": None,
                },
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={256, 257},
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "target_pi_version_drift"
                and issue["work_package_id"] == 257
                for issue in issues
            )
        )

    def test_version_without_target_pi_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 300,
                    "record_ref": "openproject://work_packages/300",
                    "subject": "Defect: Repair stale roadmap projection",
                    "type": "Defect",
                    "status": "ready",
                    "parent_id": 257,
                    "execution_classification": None,
                    "description_headings": [
                        "What This Corrects",
                        "Why This Matters Now",
                        "Evidence Expectation",
                        "Execution Context",
                    ],
                    "target_pi": None,
                    "version_name": "PI-2026-02",
                },
                {
                    "id": 257,
                    "record_ref": "openproject://work_packages/257",
                    "subject": "Project ART Target PI into roadmap-compatible OpenProject versions and backfill existing drift",
                    "type": "Feature",
                    "status": "in-progress",
                    "parent_id": 256,
                    "execution_classification": "Business",
                    "description_headings": [
                        "What This Achieves",
                        "Benefit Hypothesis",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-02",
                    "version_name": "PI-2026-02",
                },
                {
                    "id": 256,
                    "record_ref": "openproject://work_packages/256",
                    "subject": "Keep the OpenProject roadmap view truthful to ART PI placement",
                    "type": "Epic",
                    "status": "in-progress",
                    "parent_id": None,
                    "execution_classification": None,
                    "description_headings": [
                        "What This Initiative Achieves",
                        "Current PI Focus",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-02",
                    "version_name": "PI-2026-02",
                },
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={256, 257, 300},
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "version_without_target_pi"
                and issue["work_package_id"] == 300
                for issue in issues
            )
        )

    def test_target_pi_iteration_mismatch_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 430,
                    "record_ref": "openproject://work_packages/430",
                    "subject": "Enabler: Repair PI lifecycle placement",
                    "type": "User story",
                    "status": "ready",
                    "parent_id": 429,
                    "execution_classification": "Enabler",
                    "description_headings": [
                        "What This Enables",
                        "Why This Matters Now",
                        "Evidence Expectation",
                        "Execution Context",
                    ],
                    "iteration": "PI-2026-02 / Iteration 1",
                    "target_pi": "PI-2026-03",
                    "version_name": "PI-2026-03",
                },
                {
                    "id": 429,
                    "record_ref": "openproject://work_packages/429",
                    "subject": "Enabler: Commit the PI lifecycle guard",
                    "type": "Feature",
                    "status": "in-progress",
                    "parent_id": 428,
                    "execution_classification": "Enabler",
                    "description_headings": [
                        "What This Enables",
                        "Benefit Hypothesis",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "iteration": "PI-2026-03 / Iteration 1",
                    "target_pi": "PI-2026-03",
                    "version_name": "PI-2026-03",
                },
                {
                    "id": 428,
                    "record_ref": "openproject://work_packages/428",
                    "subject": "Govern the ART PI lifecycle",
                    "type": "Epic",
                    "status": "in-progress",
                    "parent_id": None,
                    "execution_classification": None,
                    "description_headings": [
                        "What This Initiative Achieves",
                        "Current PI Focus",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-03",
                    "version_name": "PI-2026-03",
                },
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={428, 429, 430},
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "target_pi_iteration_mismatch"
                and issue["gate_id"]
                == "target-pi-iteration-must-align-with-pi-lifecycle"
                and issue["work_package_id"] == 430
                for issue in issues
            )
        )

    def test_retired_scope_in_unassigned_bucket_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 343,
                    "record_ref": "openproject://work_packages/343",
                    "subject": "Feature: Package and consume a standalone governance engine after the extraction gate is approved",
                    "type": "Feature",
                    "status": "retired",
                    "parent_id": 247,
                    "execution_classification": "Enabler",
                    "description_headings": [
                        "What This Achieves",
                        "Benefit Hypothesis",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": None,
                    "version_name": "Not yet committed to a PI",
                },
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={343},
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "retired_scope_in_wrong_roadmap_bucket"
                and issue["work_package_id"] == 343
                for issue in issues
            )
        )

    def test_retired_scope_missing_retired_bucket_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 344,
                    "record_ref": "openproject://work_packages/344",
                    "subject": "Feature: Activate bounded governed AI runtime assist after extraction is approved",
                    "type": "Feature",
                    "status": "retired",
                    "parent_id": 247,
                    "execution_classification": "Enabler",
                    "description_headings": [
                        "What This Achieves",
                        "Benefit Hypothesis",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": None,
                    "version_name": None,
                },
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={344},
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "roadmap_retired_bucket_missing"
                and issue["work_package_id"] == 344
                for issue in issues
            )
        )

    def test_retired_scope_retaining_target_pi_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 346,
                    "record_ref": "openproject://work_packages/346",
                    "subject": "User story: Preserve a broker-first governed triage path",
                    "type": "User story",
                    "status": "retired",
                    "parent_id": 252,
                    "execution_classification": "Business",
                    "description_headings": [
                        "What This Achieves",
                        "Why This Matters Now",
                        "Evidence Expectation",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-03",
                    "version_name": "PI-2026-03",
                },
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={346},
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "retired_scope_retains_target_pi"
                and issue["gate_id"] == "retired-scope-must-clear-target-pi"
                and issue["work_package_id"] == 346
                for issue in issues
            )
        )

    def test_retired_story_without_target_pi_is_not_reported_as_missing_commitment(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 347,
                    "record_ref": "openproject://work_packages/347",
                    "subject": "User story: Preserve a broker-first operator acceptance path",
                    "type": "User story",
                    "status": "retired",
                    "parent_id": 252,
                    "execution_classification": "Business",
                    "description_headings": [
                        "What This Achieves",
                        "Why This Matters Now",
                        "Evidence Expectation",
                        "Execution Context",
                    ],
                    "target_pi": None,
                    "version_name": "Retired scope",
                },
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={347},
        )

        self.assertFalse(
            any(
                issue["issue_type"] == "target_pi_required_type_missing_commitment"
                and issue["work_package_id"] == 347
                for issue in issues
            )
        )

    def test_blocked_item_missing_blocker_record_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 336,
                    "record_ref": "openproject://work_packages/336",
                    "subject": "Defect: State the exact blocker and stop adjacent ART mutation when a live mutation seam fails repeatedly",
                    "type": "Defect",
                    "status": "blocked",
                    "parent_id": 304,
                    "execution_classification": None,
                    "description_headings": [
                        "What This Corrects",
                        "Why This Matters Now",
                        "Evidence Expectation",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-03",
                    "version_name": "PI-2026-03",
                    "blocker_fields": {
                        "statement": "Closeout path is still blocked by repeated live mutation seam failure.",
                        "decision_path": "workaround",
                    },
                },
                {
                    "id": 304,
                    "record_ref": "openproject://work_packages/304",
                    "subject": "Establish seamless broker-owned ART workflow and zero-Rails normal operator path",
                    "type": "Epic",
                    "status": "in-progress",
                    "parent_id": None,
                    "execution_classification": None,
                    "description_headings": [
                        "What This Initiative Achieves",
                        "Current PI Focus",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-03",
                    "version_name": "PI-2026-03",
                    "blocker_fields": None,
                },
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={304, 336},
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "blocked_item_missing_blocker_record"
                and issue["work_package_id"] == 336
                and issue["gate_id"] == "blocked-status-requires-bounded-blocker-record"
                for issue in issues
            )
        )

    def test_blocked_item_accepts_display_name_blocker_fields(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 336,
                    "record_ref": "openproject://work_packages/336",
                    "subject": "Defect: State the exact blocker and stop adjacent ART mutation when a live mutation seam fails repeatedly",
                    "type": "Defect",
                    "status": "blocked",
                    "parent_id": 304,
                    "execution_classification": None,
                    "description_headings": [
                        "What This Corrects",
                        "Why This Matters Now",
                        "Evidence Expectation",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-03",
                    "version_name": "PI-2026-03",
                    "blocker_fields": {
                        "Blocker Statement": "Closeout path is blocked by runtime evidence.",
                        "Blocker Impact": "The active step cannot close honestly.",
                        "Blocker Owner": "Workspace Governance",
                        "Blocker Discovered On": "2026-04-29",
                        "Blocker Decision Path": "remove",
                        "Blocker Justification": "The exact blocker must be removed before execution resumes.",
                    },
                }
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={336},
        )

        self.assertFalse(
            any(
                issue["issue_type"] == "blocked_item_missing_blocker_record"
                and issue["work_package_id"] == 336
                for issue in issues
            )
        )

    def test_non_blocked_item_retaining_blocker_record_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 336,
                    "record_ref": "openproject://work_packages/336",
                    "subject": "Defect: State the exact blocker and stop adjacent ART mutation when a live mutation seam fails repeatedly",
                    "type": "Defect",
                    "status": "in-progress",
                    "parent_id": 304,
                    "execution_classification": None,
                    "description_headings": [
                        "What This Corrects",
                        "Why This Matters Now",
                        "Evidence Expectation",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-03",
                    "version_name": "PI-2026-03",
                    "blocker_fields": {
                        "statement": "Residual blocker note was left behind.",
                    },
                },
                {
                    "id": 304,
                    "record_ref": "openproject://work_packages/304",
                    "subject": "Establish seamless broker-owned ART workflow and zero-Rails normal operator path",
                    "type": "Epic",
                    "status": "in-progress",
                    "parent_id": None,
                    "execution_classification": None,
                    "description_headings": [
                        "What This Initiative Achieves",
                        "Current PI Focus",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-03",
                    "version_name": "PI-2026-03",
                    "blocker_fields": None,
                },
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={304, 336},
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "non_blocked_item_retains_active_blocker_record"
                and issue["work_package_id"] == 336
                and issue["gate_id"] == "active-blocker-record-must-stay-on-blocked-item"
                for issue in issues
            )
        )

    def test_missing_unassigned_roadmap_bucket_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 301,
                    "record_ref": "openproject://work_packages/301",
                    "subject": "Clarify future runtime extraction gate",
                    "type": "User story",
                    "status": "new",
                    "parent_id": 257,
                    "execution_classification": "Business",
                    "description_headings": [
                        "What This Achieves",
                        "Why This Matters Now",
                        "Evidence Expectation",
                        "Execution Context",
                    ],
                    "target_pi": None,
                    "version_name": None,
                },
                {
                    "id": 257,
                    "record_ref": "openproject://work_packages/257",
                    "subject": "Project ART Target PI into roadmap-compatible OpenProject versions and backfill existing drift",
                    "type": "Feature",
                    "status": "in-progress",
                    "parent_id": 256,
                    "execution_classification": "Business",
                    "description_headings": [
                        "What This Achieves",
                        "Benefit Hypothesis",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-02",
                    "version_name": "PI-2026-02",
                },
                {
                    "id": 256,
                    "record_ref": "openproject://work_packages/256",
                    "subject": "Keep the OpenProject roadmap view truthful to ART PI placement",
                    "type": "Epic",
                    "status": "in-progress",
                    "parent_id": None,
                    "execution_classification": None,
                    "description_headings": [
                        "What This Initiative Achieves",
                        "Current PI Focus",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-02",
                    "version_name": "PI-2026-02",
                },
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={256, 257, 301},
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "roadmap_unassigned_bucket_missing"
                and issue["work_package_id"] == 301
                for issue in issues
            )
        )

    def test_active_item_without_target_pi_commitment_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 400,
                    "record_ref": "openproject://work_packages/400",
                    "subject": "Risk: Shared platform control validation may outrun PI commitment",
                    "type": "Risk",
                    "status": "in-progress",
                    "parent_id": 87,
                    "execution_classification": None,
                    "description_headings": [
                        "Risk Event",
                        "Impact",
                        "Current Handling",
                        "Execution Context",
                    ],
                    "target_pi": None,
                    "version_name": "Not yet committed to a PI",
                },
                {
                    "id": 87,
                    "record_ref": "openproject://work_packages/87",
                    "subject": "Establish the governed enterprise cybersecurity control baseline, assurance, and compliance operating model",
                    "type": "Epic",
                    "status": "in-progress",
                    "parent_id": None,
                    "execution_classification": None,
                    "description_headings": [
                        "What This Initiative Achieves",
                        "Current PI Focus",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": None,
                    "version_name": "Not yet committed to a PI",
                },
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={87, 400},
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "active_item_missing_target_pi_commitment"
                and issue["work_package_id"] == 400
                for issue in issues
            )
        )
        self.assertFalse(
            any(
                issue["issue_type"] == "active_item_missing_target_pi_commitment"
                and issue["work_package_id"] == 87
                for issue in issues
            )
        )

    def test_initiative_review_state_requires_system_demo_and_clean_execution_for_closing(self) -> None:
        result = MODULE.evaluate_initiative_review_state(
            epic={
                "pm2_phase": "Executing",
                "system_demo_evidence_present": False,
                "inspect_and_adapt_actions_present": False,
            },
            summary={
                "blocked_count": 1,
                "completed_with_weak_done_narrative_count": 0,
                "completed_with_weak_evidence_count": 0,
                "completed_without_evidence_count": 0,
                "completed_without_owner_count": 0,
                "open_descendant_count": 2,
                "unresolved_dependency_count": 0,
            },
        )

        self.assertFalse(result["closing_transition_ready"])
        self.assertEqual(
            result["closing_transition_reasons"],
            [
                "system_demo_missing",
                "open_descendants_present",
                "blocked_items_present",
            ],
        )

    def test_initiative_review_state_requires_closing_and_inspect_and_adapt_for_done(self) -> None:
        result = MODULE.evaluate_initiative_review_state(
            epic={
                "pm2_phase": "Executing",
                "system_demo_evidence_present": True,
                "inspect_and_adapt_actions_present": False,
            },
            summary={
                "blocked_count": 0,
                "completed_with_weak_done_narrative_count": 0,
                "completed_with_weak_evidence_count": 0,
                "completed_without_evidence_count": 0,
                "completed_without_owner_count": 0,
                "open_descendant_count": 0,
                "unresolved_dependency_count": 0,
            },
        )

        self.assertFalse(result["completion_transition_ready"])
        self.assertEqual(
            result["completion_transition_reasons"],
            [
                "pm2_phase_not_closing",
                "inspect_and_adapt_missing",
            ],
        )

    def test_initiative_review_state_treats_done_narrative_drift_as_closeout_blocker(self) -> None:
        result = MODULE.evaluate_initiative_review_state(
            epic={
                "pm2_phase": "Closing",
                "system_demo_evidence_present": True,
                "inspect_and_adapt_actions_present": True,
            },
            summary={
                "blocked_count": 0,
                "completed_with_weak_done_narrative_count": 1,
                "completed_with_weak_evidence_count": 0,
                "completed_without_evidence_count": 0,
                "completed_without_owner_count": 0,
                "open_descendant_count": 0,
                "unresolved_dependency_count": 0,
            },
        )

        self.assertFalse(result["closing_transition_ready"])
        self.assertFalse(result["completion_transition_ready"])
        self.assertIn("done_narrative_weak", result["closing_transition_reasons"])

    def test_pi_objective_without_target_pi_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 500,
                    "record_ref": "openproject://work_packages/500",
                    "subject": "Prove the governed consume-to-PI-planning workflow in PI-2026-03",
                    "type": "PI Objective",
                    "status": "new",
                    "parent_id": 277,
                    "execution_classification": None,
                    "description_headings": [
                        "Outcome",
                        "Why This PI",
                        "Success Signal",
                        "Execution Context",
                    ],
                    "target_pi": None,
                    "version_name": "Not yet committed to a PI",
                    "iteration": "Program-wide / planning",
                },
                {
                    "id": 277,
                    "record_ref": "openproject://work_packages/277",
                    "subject": "Establish the governed consume-to-PI-planning workflow for Workspace Delivery ART",
                    "type": "Epic",
                    "status": "in-progress",
                    "parent_id": None,
                    "execution_classification": None,
                    "description_headings": [
                        "What This Initiative Achieves",
                        "Current PI Focus",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": None,
                    "version_name": "Not yet committed to a PI",
                },
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={277, 500},
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "target_pi_required_type_missing_commitment"
                and issue["work_package_id"] == 500
                for issue in issues
            )
        )

    def test_committed_item_without_iteration_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        project_payload = {
            "work_packages": [
                {
                    "id": 501,
                    "record_ref": "openproject://work_packages/501",
                    "subject": "Improvement: Align roadmap, boards, contracts, and operator surfaces to the canonical planning workflow",
                    "type": "Feature",
                    "status": "ready",
                    "parent_id": 277,
                    "execution_classification": "Improvement",
                    "description_headings": [
                        "What This Achieves",
                        "Benefit Hypothesis",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-03",
                    "version_name": "PI-2026-03",
                    "iteration": None,
                },
                {
                    "id": 277,
                    "record_ref": "openproject://work_packages/277",
                    "subject": "Establish the governed consume-to-PI-planning workflow for Workspace Delivery ART",
                    "type": "Epic",
                    "status": "in-progress",
                    "parent_id": None,
                    "execution_classification": None,
                    "description_headings": [
                        "What This Initiative Achieves",
                        "Current PI Focus",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "target_pi": "PI-2026-03",
                    "version_name": "PI-2026-03",
                },
            ]
        }

        MODULE.evaluate_live_project_taxonomy(
            project_payload=project_payload,
            issues=issues,
            narrative_findings=narrative_findings,
            scoped_ids={277, 501},
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "committed_item_missing_iteration"
                and issue["work_package_id"] == 501
                for issue in issues
            )
        )

    def test_backlog_feature_allows_planned_story_children_but_reports_executable_child_scope(self) -> None:
        issues = []
        narrative_findings = []
        epic = {
            "id": 277,
            "record_ref": "openproject://work_packages/277",
            "status": "in-progress",
            "subject": "Establish the governed consume-to-PI-planning workflow for Workspace Delivery ART",
            "type": "Epic",
            "description_headings": [
                "What This Initiative Achieves",
                "Current PI Focus",
                "Scope Boundaries",
                "Execution Context",
            ],
        }
        root = {
            "id": 277,
            "children": [
                {
                    "children": [
                        {
                            "children": [],
                            "completion_evidence_formatting_valid": False,
                            "completion_evidence_issues": [],
                            "completion_evidence_present": False,
                            "description_headings": [
                                "What This Achieves",
                                "Why This Matters Now",
                                "Evidence Expectation",
                                "Execution Context",
                            ],
                            "description_present": True,
                            "description_starts_with_heading": True,
                            "done_narrative_contract_applicable": False,
                            "done_narrative_contract_issues": [],
                            "done_narrative_contract_satisfied": True,
                            "id": 530,
                            "iteration": None,
                            "owner_repo": "platform-engineering",
                            "parent_id": 520,
                            "record_ref": "openproject://work_packages/530",
                            "responsible_login": "Platform Engineering",
                            "status": "new",
                            "subject": "Improvement: Define the PI planning shape, commitment rules, and rolling-wave decomposition depth",
                            "target_pi": None,
                            "type": "User story",
                        }
                    ],
                    "completion_evidence_formatting_valid": False,
                    "completion_evidence_issues": [],
                    "completion_evidence_present": False,
                    "description_headings": [
                        "What This Achieves",
                        "Benefit Hypothesis",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "description_present": True,
                    "description_starts_with_heading": True,
                    "done_narrative_contract_applicable": False,
                    "done_narrative_contract_issues": [],
                    "done_narrative_contract_satisfied": True,
                    "id": 520,
                    "iteration": None,
                    "owner_repo": "platform-engineering",
                    "parent_id": 277,
                    "record_ref": "openproject://work_packages/520",
                    "responsible_login": "Platform Engineering",
                    "status": "new",
                    "subject": "Improvement: Define the consume, frame, PI-plan, elaborate, execute, and review workflow with hard gates",
                    "target_pi": None,
                    "type": "Feature",
                }
            ],
        }

        MODULE.evaluate_execution_summary(
            initiative_id=277,
            epic=epic,
            root=root,
            issues=issues,
            narrative_findings=narrative_findings,
        )

        self.assertFalse(
            any(
                issue["issue_type"] == "backlog_feature_has_executable_child_scope"
                and issue["work_package_id"] == 520
                for issue in issues
            )
        )

        root["children"][0]["children"][0]["status"] = "ready"
        issues = []
        narrative_findings = []
        MODULE.evaluate_execution_summary(
            initiative_id=277,
            epic=epic,
            root=root,
            issues=issues,
            narrative_findings=narrative_findings,
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "backlog_feature_has_executable_child_scope"
                and issue["work_package_id"] == 520
                for issue in issues
            )
        )

    def test_planned_backlog_story_loose_description_is_polish_not_hard_issue(self) -> None:
        issues = []
        narrative_findings = []
        epic = {
            "id": 420,
            "record_ref": "openproject://work_packages/420",
            "status": "new",
            "subject": "Build Workspace Governance Control Fabric foundation",
            "type": "Epic",
            "description_headings": [
                "What This Initiative Achieves",
                "Current PI Focus",
                "Scope Boundaries",
                "Execution Context",
            ],
        }
        root = {
            "id": 420,
            "children": [
                {
                    "children": [
                        {
                            "children": [],
                            "completion_evidence_formatting_valid": False,
                            "completion_evidence_issues": [],
                            "completion_evidence_present": False,
                            "description_headings": [],
                            "description_present": True,
                            "description_starts_with_heading": False,
                            "done_narrative_contract_applicable": False,
                            "done_narrative_contract_issues": [],
                            "done_narrative_contract_satisfied": True,
                            "id": 427,
                            "iteration": None,
                            "owner_repo": "workspace-governance",
                            "parent_id": 426,
                            "record_ref": "openproject://work_packages/427",
                            "responsible_login": "Workspace Governance",
                            "status": "new",
                            "subject": "Enabler: Write the control-fabric architecture ADR",
                            "target_pi": None,
                            "type": "User story",
                        }
                    ],
                    "completion_evidence_formatting_valid": False,
                    "completion_evidence_issues": [],
                    "completion_evidence_present": False,
                    "description_headings": [
                        "What This Enables",
                        "Benefit Hypothesis",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "description_present": True,
                    "description_starts_with_heading": True,
                    "done_narrative_contract_applicable": False,
                    "done_narrative_contract_issues": [],
                    "done_narrative_contract_satisfied": True,
                    "id": 426,
                    "iteration": None,
                    "owner_repo": "workspace-governance",
                    "parent_id": 420,
                    "record_ref": "openproject://work_packages/426",
                    "responsible_login": "Workspace Governance",
                    "status": "new",
                    "subject": "Enabler: Define the control-fabric architecture",
                    "target_pi": None,
                    "type": "Feature",
                }
            ],
        }

        MODULE.evaluate_execution_summary(
            initiative_id=420,
            epic=epic,
            root=root,
            issues=issues,
            narrative_findings=narrative_findings,
        )

        self.assertFalse(
            any(
                issue["issue_type"] == "description_does_not_start_with_heading"
                and issue["work_package_id"] == 427
                for issue in issues
            )
        )
        self.assertTrue(
            any(
                finding["finding_type"] == "description_does_not_start_with_heading"
                and finding["work_package_id"] == 427
                and finding["severity"] == "polish"
                and finding["attention_scope"] == "backlog"
                for finding in narrative_findings
            )
        )

    def test_ready_story_loose_description_still_hard_fails(self) -> None:
        issues = []
        narrative_findings = []
        epic = {
            "id": 420,
            "record_ref": "openproject://work_packages/420",
            "status": "new",
            "subject": "Build Workspace Governance Control Fabric foundation",
            "type": "Epic",
            "description_headings": [
                "What This Initiative Achieves",
                "Current PI Focus",
                "Scope Boundaries",
                "Execution Context",
            ],
        }
        root = {
            "id": 420,
            "children": [
                {
                    "children": [
                        {
                            "children": [],
                            "completion_evidence_formatting_valid": False,
                            "completion_evidence_issues": [],
                            "completion_evidence_present": False,
                            "description_headings": [],
                            "description_present": True,
                            "description_starts_with_heading": False,
                            "done_narrative_contract_applicable": False,
                            "done_narrative_contract_issues": [],
                            "done_narrative_contract_satisfied": True,
                            "id": 423,
                            "iteration": "PI-2026-03 / Iteration 1",
                            "owner_repo": "workspace-governance",
                            "parent_id": 422,
                            "record_ref": "openproject://work_packages/423",
                            "responsible_login": "Workspace Governance",
                            "status": "ready",
                            "subject": "Enabler: Register the control-fabric repo",
                            "target_pi": "PI-2026-03",
                            "type": "User story",
                        }
                    ],
                    "completion_evidence_formatting_valid": False,
                    "completion_evidence_issues": [],
                    "completion_evidence_present": False,
                    "description_headings": [
                        "What This Enables",
                        "Benefit Hypothesis",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "description_present": True,
                    "description_starts_with_heading": True,
                    "done_narrative_contract_applicable": False,
                    "done_narrative_contract_issues": [],
                    "done_narrative_contract_satisfied": True,
                    "id": 422,
                    "iteration": "PI-2026-03 / Iteration 1",
                    "owner_repo": "workspace-governance",
                    "parent_id": 420,
                    "record_ref": "openproject://work_packages/422",
                    "responsible_login": "Workspace Governance",
                    "status": "new",
                    "subject": "Enabler: Admit the control-fabric repo and ownership surfaces",
                    "target_pi": "PI-2026-03",
                    "type": "Feature",
                }
            ],
        }

        MODULE.evaluate_execution_summary(
            initiative_id=420,
            epic=epic,
            root=root,
            issues=issues,
            narrative_findings=narrative_findings,
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "description_does_not_start_with_heading"
                and issue["work_package_id"] == 423
                for issue in issues
            )
        )

    def test_pi_committed_initiative_without_pi_objective_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        epic = {
            "id": 251,
            "record_ref": "openproject://work_packages/251",
            "status": "new",
            "subject": "Activate bounded governed AI runtime assist after parity, audit, and approval gates",
            "type": "Epic",
            "description_headings": [
                "What This Initiative Achieves",
                "Current PI Focus",
                "Scope Boundaries",
                "Execution Context",
            ],
        }
        root = {
            "id": 251,
            "children": [
                {
                    "children": [],
                    "completion_evidence_formatting_valid": False,
                    "completion_evidence_issues": [],
                    "completion_evidence_present": False,
                    "description_headings": [
                        "What This Enables",
                        "Benefit Hypothesis",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "description_present": True,
                    "description_starts_with_heading": True,
                    "done_narrative_contract_applicable": False,
                    "done_narrative_contract_issues": [],
                    "done_narrative_contract_satisfied": True,
                    "id": 252,
                    "iteration": "PI-2026-03 / Iteration 1",
                    "owner_repo": "operator-orchestration-service",
                    "parent_id": 251,
                    "record_ref": "openproject://work_packages/252",
                    "responsible_login": "Operator Orchestration-Service",
                    "status": "new",
                    "subject": "Enabler: Define the invocation and caller-control path",
                    "target_pi": "PI-2026-03",
                    "type": "Feature",
                }
            ],
        }

        MODULE.evaluate_execution_summary(
            initiative_id=251,
            epic=epic,
            root=root,
            issues=issues,
            narrative_findings=narrative_findings,
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "pi_committed_initiative_missing_pi_objective"
                and issue["work_package_id"] == 251
                for issue in issues
            )
        )

    def test_pi_committed_feature_without_leaf_child_is_reported(self) -> None:
        issues = []
        narrative_findings = []
        epic = {
            "id": 251,
            "record_ref": "openproject://work_packages/251",
            "status": "new",
            "subject": "Activate bounded governed AI runtime assist after parity, audit, and approval gates",
            "type": "Epic",
            "description_headings": [
                "What This Initiative Achieves",
                "Current PI Focus",
                "Scope Boundaries",
                "Execution Context",
            ],
        }
        root = {
            "id": 251,
            "children": [
                {
                    "children": [],
                    "completion_evidence_formatting_valid": False,
                    "completion_evidence_issues": [],
                    "completion_evidence_present": False,
                    "description_headings": [
                        "Outcome",
                        "Why This PI",
                        "Success Signal",
                        "Execution Context",
                    ],
                    "description_present": True,
                    "description_starts_with_heading": True,
                    "done_narrative_contract_applicable": False,
                    "done_narrative_contract_issues": [],
                    "done_narrative_contract_satisfied": True,
                    "id": 345,
                    "iteration": "PI-2026-03 / Iteration 1",
                    "owner_repo": "platform-engineering",
                    "parent_id": 251,
                    "record_ref": "openproject://work_packages/345",
                    "responsible_login": "Platform Engineering",
                    "status": "new",
                    "subject": "Deliver the first bounded governed runtime-assist slice for PI-2026-03",
                    "target_pi": "PI-2026-03",
                    "type": "PI Objective",
                },
                {
                    "children": [],
                    "completion_evidence_formatting_valid": False,
                    "completion_evidence_issues": [],
                    "completion_evidence_present": False,
                    "description_headings": [
                        "What This Enables",
                        "Benefit Hypothesis",
                        "Scope Boundaries",
                        "Execution Context",
                    ],
                    "description_present": True,
                    "description_starts_with_heading": True,
                    "done_narrative_contract_applicable": False,
                    "done_narrative_contract_issues": [],
                    "done_narrative_contract_satisfied": True,
                    "id": 252,
                    "iteration": "PI-2026-03 / Iteration 1",
                    "owner_repo": "operator-orchestration-service",
                    "parent_id": 251,
                    "record_ref": "openproject://work_packages/252",
                    "responsible_login": "Operator Orchestration-Service",
                    "status": "new",
                    "subject": "Enabler: Define the invocation and caller-control path",
                    "target_pi": "PI-2026-03",
                    "type": "Feature",
                },
            ],
        }

        MODULE.evaluate_execution_summary(
            initiative_id=251,
            epic=epic,
            root=root,
            issues=issues,
            narrative_findings=narrative_findings,
        )

        self.assertTrue(
            any(
                issue["issue_type"] == "pi_committed_feature_missing_leaf_child"
                and issue["work_package_id"] == 252
                for issue in issues
            )
        )


if __name__ == "__main__":
    unittest.main()
