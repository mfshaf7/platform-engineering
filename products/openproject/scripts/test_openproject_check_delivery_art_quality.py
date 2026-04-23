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


if __name__ == "__main__":
    unittest.main()
