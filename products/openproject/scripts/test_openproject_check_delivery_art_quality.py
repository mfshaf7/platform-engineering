import importlib.util
import pathlib
import unittest


SCRIPT_PATH = pathlib.Path(__file__).resolve().parent / "openproject_check_delivery_art_quality.py"
SPEC = importlib.util.spec_from_file_location(
    "openproject_check_delivery_art_quality", SCRIPT_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DeliveryArtQualityTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
