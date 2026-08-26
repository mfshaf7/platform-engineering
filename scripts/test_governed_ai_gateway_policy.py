from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = REPO_ROOT / "dev-integration/profiles/governed-ai-gateway/runtime"
sys.path.insert(0, str(RUNTIME_ROOT))

from gateway_policy import GatewayPolicy  # noqa: E402
from model_profile_resolver import resolve_model_profile_registry  # noqa: E402


def selections() -> dict:
    return resolve_model_profile_registry(
        REPO_ROOT / "security/governed-ai-model-profiles.yaml",
        REPO_ROOT / "security/governed-ai-access-plane.yaml",
        environment="dev-integration",
    )


def caller(profile_id: str, caller_id: str) -> dict:
    return {
        "caller_id": caller_id,
        "caller_repo": caller_id.split("/", 1)[0],
        "caller_workflow": caller_id.split("/", 1)[1],
        "decision_or_correlation_id": "correlation-1",
        "requested_profile_id": profile_id,
    }


class GatewayPolicyTests(unittest.TestCase):
    def test_intake_compatibility_request_resolves_the_default_task(self) -> None:
        request = {
            "profile_id": "intake-classifier-v1",
            "caller_identity": caller(
                "intake-classifier-v1", "workspace-governance/intake-assist"
            ),
            "operator_identity": {"operator_id": "operator:test"},
            "provider_output_schema_ref": (
                "platform-engineering/security/schemas/"
                "intake-classification-result.schema.json"
            ),
            "input": {"operator_supplied_intake_notes": "Review this entrant."},
        }

        decision = GatewayPolicy(selections()).evaluate(request)

        self.assertTrue(decision.allowed)
        self.assertTrue(decision.compatibility_mode)
        self.assertEqual(decision.task["task_kind"], "intake_classification")

    def test_work_design_profile_allows_the_reviewed_typed_request(self) -> None:
        request = self.work_design_request()

        decision = GatewayPolicy(selections()).evaluate(request)

        self.assertTrue(decision.allowed)
        self.assertFalse(decision.compatibility_mode)
        self.assertEqual(decision.task["task_kind"], "tree_advice")

    def test_work_design_suspension_does_not_disable_intake(self) -> None:
        resolved = selections()
        profile = resolved["profiles"]["delivery-work-design-advisor-v1"]
        profile["profile_status"] = "suspended"
        profile["profile_activation_allowed"] = False
        profile["activation_eligible"] = False

        work_design = GatewayPolicy(resolved).evaluate(self.work_design_request())
        intake = GatewayPolicy(resolved).evaluate(
            {
                "profile_id": "intake-classifier-v1",
                "caller_identity": caller(
                    "intake-classifier-v1", "workspace-governance/intake-assist"
                ),
                "operator_identity": {"operator_id": "operator:test"},
                "provider_output_schema_ref": (
                    "platform-engineering/security/schemas/"
                    "intake-classification-result.schema.json"
                ),
                "input": {"operator_supplied_intake_notes": "Review this entrant."},
            }
        )

        self.assertFalse(work_design.allowed)
        self.assertIn("profile-not-active", work_design.reasons)
        self.assertIn("profile-activation-not-allowed", work_design.reasons)
        self.assertTrue(intake.allowed)

    def test_refinement_profile_allows_the_reviewed_typed_request(self) -> None:
        decision = GatewayPolicy(selections()).evaluate(self.refinement_request())

        self.assertTrue(decision.allowed)
        self.assertFalse(decision.compatibility_mode)
        self.assertEqual(decision.task["task_kind"], "metadata_advice")

    def test_suspended_refinement_profile_fails_closed(self) -> None:
        resolved = selections()
        profile = resolved["profiles"]["delivery-refinement-advisor-v1"]
        profile["profile_status"] = "suspended"
        profile["binding_status"] = "suspended"
        profile["profile_activation_allowed"] = False
        profile["activation_eligible"] = False

        decision = GatewayPolicy(resolved).evaluate(self.refinement_request())

        self.assertFalse(decision.allowed)
        self.assertIn("profile-not-active", decision.reasons)
        self.assertIn("binding-not-active", decision.reasons)
        self.assertIn("profile-activation-not-allowed", decision.reasons)

    def test_unknown_caller_task_schema_and_profile_fail_closed(self) -> None:
        request = self.work_design_request()
        request["caller_identity"]["caller_id"] = "unknown/caller"
        request["task"]["contract_ref"] = "wrong.contract"
        request["provider_output_schema_ref"] = "invalid/schema.json"

        decision = GatewayPolicy(selections()).evaluate(request)

        self.assertFalse(decision.allowed)
        self.assertIn("caller-not-allowed", decision.reasons)
        self.assertIn("task-contract-mismatch", decision.reasons)
        self.assertIn("output-schema-mismatch", decision.reasons)
        unknown = copy.deepcopy(request)
        unknown["profile_id"] = "missing-profile"
        self.assertEqual(
            GatewayPolicy(selections()).evaluate(unknown).reasons,
            ("profile-not-allowed",),
        )

    def test_caller_identity_and_profile_request_limit_fail_closed(self) -> None:
        resolved = selections()
        request = self.work_design_request()
        request["caller_identity"]["caller_repo"] = "spoofed-repo"
        request["input"]["operator_prompt"] = "x" * 300001

        decision = GatewayPolicy(resolved).evaluate(request)

        self.assertFalse(decision.allowed)
        self.assertIn("caller-identity-mismatch", decision.reasons)
        self.assertIn("request-too-large-for-profile", decision.reasons)

    @staticmethod
    def work_design_request() -> dict:
        profile_id = "delivery-work-design-advisor-v1"
        return {
            "profile_id": profile_id,
            "caller_identity": caller(
                profile_id, "operator-orchestration-service/work-design-assist"
            ),
            "operator_identity": {"operator_id": "operator:test"},
            "task": {
                "kind": "tree_advice",
                "contract_ref": "oos.delivery-work-design.v1",
                "version": "1.0",
            },
            "provider_output_schema_ref": (
                "platform-engineering/security/schemas/"
                "delivery-work-design-advice.schema.json"
            ),
            "input": {
                "task_instruction": "Review the tree without applying changes.",
                "operator_prompt": "Check package boundaries.",
                "model_safe_packet": {
                    "packet_ref": "/v1/context/packets/work-design-1",
                    "redaction_receipt_ref": "/v1/context/receipts/work-design-1",
                    "projection_receipt_ref": (
                        "/v1/context/work-design/projections/work-design-1"
                    ),
                    "content": "A bounded model-safe package projection.",
                },
            },
        }

    @staticmethod
    def refinement_request() -> dict:
        profile_id = "delivery-refinement-advisor-v1"
        return {
            "profile_id": profile_id,
            "caller_identity": caller(
                profile_id, "operator-orchestration-service/refinement-assist"
            ),
            "operator_identity": {"operator_id": "operator:test"},
            "task": {
                "kind": "metadata_advice",
                "contract_ref": "oos.delivery-refinement.v1",
                "version": "1.0",
            },
            "provider_output_schema_ref": (
                "platform-engineering/security/schemas/"
                "delivery-refinement-advice.schema.json"
            ),
            "input": {
                "task_instruction": "Suggest a value without applying it.",
                "operator_prompt": "Make the readiness field verifiable.",
                "model_safe_packet": {
                    "packet_ref": "/v1/context/packets/refinement-1",
                    "redaction_receipt_ref": "/v1/context/receipts/refinement-1",
                    "projection_receipt_ref": (
                        "/v1/context/refinement/projections/refinement-1"
                    ),
                    "content": "A bounded model-safe Refinement projection.",
                },
            },
        }


if __name__ == "__main__":
    unittest.main()
