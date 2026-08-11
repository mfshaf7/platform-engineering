import importlib.util
import io
import json
import pathlib
import unittest
from contextlib import redirect_stdout
from unittest import mock


SCRIPT_PATH = pathlib.Path(__file__).resolve().parent / "openproject_check_delivery_art_quality.py"
SPEC = importlib.util.spec_from_file_location(
    "openproject_check_delivery_art_quality", SCRIPT_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def scoped_payload(*, quality_drift=None):
    return {
        "workflow_id": "delivery-initiative-review-pack",
        "review_pack": {
            "epic": {
                "id": 698,
                "record_ref": "openproject://work_packages/698",
            },
            "initiative_review": {
                "closing_transition_ready": False,
            },
            "quality_drift": quality_drift
            or {
                "completed_with_weak_evidence": [],
                "completed_with_weak_done_narrative": [],
                "completed_without_evidence": [],
                "completed_without_owner": [],
                "ready_without_contract": [],
            },
            "summary": {
                "blocked_count": 1,
                "open_descendant_count": 4,
            },
        },
    }


def unscoped_payload(*, healthy=True, roadmap_drift=None):
    return {
        "workflow_id": "delivery-session-workflow-health",
        "project": {"identifier": "workspace-delivery-art"},
        "portfolio_summary": {"total_initiatives": 2},
        "workflow_health": {
            "compatible_views": {"roadmap": {"truthful": healthy}},
            "pm2_phase": {"drift": [], "healthy": True},
            "roadmap": {
                "drift": roadmap_drift or [],
                "healthy": healthy,
            },
            "summary": {
                "healthy": healthy,
                "pm2_projection_drift_count": 0,
                "roadmap_projection_drift_count": len(roadmap_drift or []),
            },
        },
    }


class DeliveryArtQualityProjectionTest(unittest.TestCase):
    def run_main(self, *, env, payload):
        stdout = io.StringIO()
        with mock.patch.object(MODULE, "run_broker_json", return_value=payload) as broker:
            with redirect_stdout(stdout):
                exit_code = MODULE.main(env=env)
        return exit_code, json.loads(stdout.getvalue()), broker

    def test_blank_env_values_fall_back_to_defaults(self) -> None:
        self.assertEqual(
            MODULE.resolve_openproject_namespace({"OPENPROJECT_NAMESPACE": ""}),
            "openproject",
        )
        self.assertEqual(
            MODULE.env_value({"BROKER_PORT": ""}, "BROKER_PORT", "8080"),
            "8080",
        )

    def test_broker_namespace_defaults_to_profile_namespace(self) -> None:
        self.assertEqual(
            MODULE.resolve_broker_namespace(
                {"OPENPROJECT_NAMESPACE": "devint-accepted-idea-delivery-mfshaf7"}
            ),
            "devint-accepted-idea-delivery-mfshaf7",
        )

    def test_broker_namespace_defaults_to_shared_namespace(self) -> None:
        self.assertEqual(
            MODULE.resolve_broker_namespace({"OPENPROJECT_NAMESPACE": "openproject"}),
            "operator-orchestration-service",
        )

    def test_normalize_delivery_id_accepts_numeric_and_canonical_values(self) -> None:
        self.assertEqual(MODULE.normalize_delivery_id("698"), "delivery-698")
        self.assertEqual(
            MODULE.normalize_delivery_id("delivery-698"), "delivery-698"
        )
        with self.assertRaisesRegex(RuntimeError, "must look like"):
            MODULE.normalize_delivery_id("epic-698")

    def test_scoped_check_consumes_one_review_pack_and_passes_clean_projection(self) -> None:
        exit_code, report, broker = self.run_main(
            env={"TARGET_EPIC_ID": "698"},
            payload=scoped_payload(),
        )

        self.assertEqual(exit_code, 0)
        broker.assert_called_once_with(
            "/v1/delivery-initiatives/delivery-698/review-pack",
            env={"TARGET_EPIC_ID": "698"},
        )
        self.assertEqual(report["source_workflow_id"], MODULE.SCOPED_WORKFLOW_ID)
        self.assertEqual(report["scope"]["mode"], "scoped-initiative")
        self.assertTrue(report["summary"]["healthy"])
        self.assertEqual(report["summary"]["issue_count"], 0)

    def test_scoped_check_fails_on_broker_projected_quality_drift(self) -> None:
        payload = scoped_payload(
            quality_drift={
                "completed_without_evidence": [
                    {"id": 802, "record_ref": "openproject://work_packages/802"}
                ],
                "ready_without_contract": [
                    {"id": 804, "record_ref": "openproject://work_packages/804"}
                ],
            }
        )

        exit_code, report, broker = self.run_main(
            env={"TARGET_EPIC_ID": "delivery-698"},
            payload=payload,
        )

        self.assertEqual(exit_code, 1)
        broker.assert_called_once()
        self.assertFalse(report["summary"]["healthy"])
        self.assertEqual(report["summary"]["issue_count"], 2)
        self.assertEqual(
            report["summary"]["issue_types"],
            {"completed_without_evidence": 1, "ready_without_contract": 1},
        )
        self.assertEqual(
            report["broker_projection"]["quality_drift"],
            payload["review_pack"]["quality_drift"],
        )

    def test_unscoped_check_consumes_one_workflow_health_projection(self) -> None:
        exit_code, report, broker = self.run_main(env={}, payload=unscoped_payload())

        self.assertEqual(exit_code, 0)
        broker.assert_called_once_with(
            "/v1/delivery-session/workflow-health",
            env={},
        )
        self.assertEqual(report["source_workflow_id"], MODULE.UNSCOPED_WORKFLOW_ID)
        self.assertEqual(report["scope"]["mode"], "portfolio-projection")
        self.assertTrue(report["summary"]["healthy"])

    def test_unscoped_check_trusts_broker_health_and_preserves_drift(self) -> None:
        drift = [
            {
                "issue_type": "target_pi_version_drift",
                "item": {"id": 804},
            }
        ]
        exit_code, report, broker = self.run_main(
            env={},
            payload=unscoped_payload(healthy=False, roadmap_drift=drift),
        )

        self.assertEqual(exit_code, 1)
        broker.assert_called_once()
        self.assertFalse(report["summary"]["healthy"])
        self.assertEqual(report["summary"]["issue_count"], 1)
        self.assertEqual(
            report["broker_projection"]["projection_health"]["roadmap"]["drift"],
            drift,
        )

    def test_rejects_unexpected_broker_workflow(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "expected broker workflow"):
            MODULE.build_scoped_report(
                {"workflow_id": "unexpected"},
                delivery_id="delivery-698",
            )

    def test_rejects_non_list_quality_projection(self) -> None:
        payload = scoped_payload(quality_drift={"ready_without_contract": 1})
        with self.assertRaisesRegex(RuntimeError, "must be a list"):
            MODULE.build_scoped_report(payload, delivery_id="delivery-698")


if __name__ == "__main__":
    unittest.main()
