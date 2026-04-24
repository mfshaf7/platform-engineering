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
    def test_blank_env_values_fall_back_to_defaults(self) -> None:
        self.assertEqual(
            MODULE.resolve_openproject_namespace({"OPENPROJECT_NAMESPACE": ""}),
            "openproject",
        )
        self.assertEqual(
            MODULE.resolve_delivery_project_identifier(
                {"OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER": ""}
            ),
            "workspace-delivery-art",
        )
        self.assertEqual(
            MODULE.env_value({"BROKER_PORT": ""}, "BROKER_PORT", "8080"),
            "8080",
        )

    def test_openproject_deployment_resolves_from_profile_namespace(self) -> None:
        completed = mock.Mock(stdout="devint-accepted-idea-delivery-openproject-web")
        with mock.patch.object(MODULE.subprocess, "run", return_value=completed) as run_mock:
            deployment = MODULE.resolve_openproject_deployment(
                {"OPENPROJECT_NAMESPACE": "devint-accepted-idea-delivery-mfshaf7"}
            )

        self.assertEqual(deployment, "devint-accepted-idea-delivery-openproject-web")
        run_mock.assert_called_once()

    def test_openproject_deployment_falls_back_to_name_scan(self) -> None:
        selector_miss = mock.Mock(stdout="")
        deployment_scan = mock.Mock(
            stdout=(
                "devint-accepted-idea-delivery-openproject-cron\n"
                "devint-accepted-idea-delivery-openproject-web\n"
                "devint-accepted-idea-delivery-openproject-worker-default\n"
            )
        )
        with mock.patch.object(
            MODULE.subprocess,
            "run",
            side_effect=[selector_miss, deployment_scan],
        ) as run_mock:
            deployment = MODULE.resolve_openproject_deployment(
                {"OPENPROJECT_NAMESPACE": "devint-accepted-idea-delivery-mfshaf7"}
            )

        self.assertEqual(deployment, "devint-accepted-idea-delivery-openproject-web")
        self.assertEqual(run_mock.call_count, 2)

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

    def test_backlog_feature_with_story_children_is_reported(self) -> None:
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

        self.assertTrue(
            any(
                issue["issue_type"] == "backlog_feature_has_story_children"
                and issue["work_package_id"] == 520
                for issue in issues
            )
        )


if __name__ == "__main__":
    unittest.main()
