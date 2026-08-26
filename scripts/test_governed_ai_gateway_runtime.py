from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = REPO_ROOT / "dev-integration/profiles/governed-ai-gateway/runtime"
sys.path.insert(0, str(RUNTIME_ROOT))

from gateway_app import GatewayRuntime  # noqa: E402
from model_profile_resolver import resolve_model_profile_registry  # noqa: E402
from ollama_adapter import ProviderResult  # noqa: E402


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


class FakeAdapter:
    def __init__(self, output: dict) -> None:
        self.output = output
        self.calls: list[dict] = []

    def invoke(self, **kwargs) -> ProviderResult:
        self.calls.append(kwargs)
        return ProviderResult(
            output=self.output,
            model_digest=(
                "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"
            ),
            runtime_version="0.32.15",
            latency_ms=4,
            usage={"prompt_tokens": 20, "completion_tokens": 8},
            prompt_version=kwargs["prompt_version"],
        )


class GatewayRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="governed-ai-runtime-")
        self.addCleanup(self.temp_dir.cleanup)
        self.audit_root = Path(self.temp_dir.name)

    def test_suspended_work_design_is_denied_before_provider_access(self) -> None:
        resolved = copy.deepcopy(selections())
        profile = resolved["profiles"]["delivery-work-design-advisor-v1"]
        profile["profile_status"] = "suspended"
        profile["profile_activation_allowed"] = False
        profile["activation_eligible"] = False
        adapter = FakeAdapter({"text": "must not be returned"})
        runtime = GatewayRuntime(
            selections=resolved,
            audit_root=self.audit_root,
            compatibility_profile_id="intake-classifier-v1",
            adapters={"delivery-work-design-advisor-v1": adapter},
        )

        status, payload = runtime.invoke(self.work_design_request())

        self.assertEqual(status, 403)
        self.assertEqual(payload["policy_decision"], "deny")
        self.assertIn("profile-not-active", payload["reasons"])
        self.assertEqual(adapter.calls, [])
        event = runtime.latest_audit_event()["latest"]
        self.assertEqual(event["task_kind"], "tree_advice")
        self.assertEqual(event["task_contract_ref"], "oos.delivery-work-design.v1")
        self.assertEqual(event["task_contract_version"], "1.0")

    def test_legacy_intake_response_shape_is_preserved(self) -> None:
        adapter = FakeAdapter(
            {"suggested_decision": "proposed", "confidence": "medium"}
        )
        runtime = GatewayRuntime(
            selections=selections(),
            audit_root=self.audit_root,
            compatibility_profile_id="intake-classifier-v1",
            adapters={"intake-classifier-v1": adapter},
        )

        status, payload = runtime.invoke(self.intake_request())

        self.assertEqual(status, 200)
        self.assertEqual(
            set(payload),
            {
                "profile_id",
                "policy_status",
                "policy_decision",
                "decision_id",
                "generated_at",
                "confidence",
                "caller_id",
                "invocation_path",
                "binding_selection_ref",
                "suggested_decision",
                "audit_ref",
            },
        )
        self.assertEqual(payload["suggested_decision"], "proposed")
        self.assertEqual(payload["confidence"], "medium")
        self.assertEqual(len(adapter.calls), 1)

    def test_independently_activated_work_design_returns_typed_result(self) -> None:
        resolved = copy.deepcopy(selections())
        profile = resolved["profiles"]["delivery-work-design-advisor-v1"]
        profile["profile_status"] = "active"
        profile["binding_status"] = "active"
        profile["profile_activation_allowed"] = True
        profile["activation_eligible"] = True
        adapter = FakeAdapter(
            {
                "confidence": "high",
                "required_operator_action": "review",
                "text": "Keep one outcome per Feature.",
                "affected_node_id": "feature-1",
                "patch_proposal": None,
            }
        )
        runtime = GatewayRuntime(
            selections=resolved,
            audit_root=self.audit_root,
            compatibility_profile_id="intake-classifier-v1",
            adapters={"delivery-work-design-advisor-v1": adapter},
        )

        status, payload = runtime.invoke(self.work_design_request())

        self.assertEqual(status, 200)
        self.assertEqual(
            payload["task"],
            {
                "kind": "tree_advice",
                "contract_ref": "oos.delivery-work-design.v1",
                "version": "1.0",
            },
        )
        self.assertEqual(payload["output"]["affected_node_id"], "feature-1")
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(
            adapter.calls[0]["system_prompt"],
            "Review the tree without applying changes.",
        )

    def test_active_refinement_profile_returns_typed_result(self) -> None:
        adapter = FakeAdapter(
            {
                "confidence": "high",
                "required_operator_action": "review",
                "field_key": "definition_of_ready",
                "value": "Repository readiness is current and receipt-bound.",
                "summary": "Use the current readiness receipt.",
                "rationale": "The proposal is specific and independently reviewable.",
            }
        )
        runtime = GatewayRuntime(
            selections=selections(),
            audit_root=self.audit_root,
            compatibility_profile_id="intake-classifier-v1",
            adapters={"delivery-refinement-advisor-v1": adapter},
        )

        status, payload = runtime.invoke(self.refinement_request())

        self.assertEqual(status, 200)
        self.assertEqual(
            payload["task"],
            {
                "kind": "metadata_advice",
                "contract_ref": "oos.delivery-refinement.v1",
                "version": "1.0",
            },
        )
        self.assertEqual(payload["output"]["field_key"], "definition_of_ready")
        self.assertEqual(len(adapter.calls), 1)

    def test_suspended_refinement_is_denied_before_provider_access(self) -> None:
        resolved = copy.deepcopy(selections())
        profile = resolved["profiles"]["delivery-refinement-advisor-v1"]
        profile["profile_status"] = "suspended"
        profile["binding_status"] = "suspended"
        profile["profile_activation_allowed"] = False
        profile["activation_eligible"] = False
        adapter = FakeAdapter({"field_key": "must-not-run"})
        runtime = GatewayRuntime(
            selections=resolved,
            audit_root=self.audit_root,
            compatibility_profile_id="intake-classifier-v1",
            adapters={"delivery-refinement-advisor-v1": adapter},
        )

        status, payload = runtime.invoke(self.refinement_request())

        self.assertEqual(status, 403)
        self.assertEqual(payload["policy_decision"], "deny")
        self.assertIn("profile-not-active", payload["reasons"])
        self.assertEqual(adapter.calls, [])

    def test_readiness_stays_available_when_compatibility_profile_is_suspended(self) -> None:
        resolved = copy.deepcopy(selections())
        intake = resolved["profiles"]["intake-classifier-v1"]
        intake["profile_status"] = "suspended"
        intake["binding_status"] = "suspended"
        intake["profile_activation_allowed"] = False
        intake["activation_eligible"] = False
        work_design = resolved["profiles"]["delivery-work-design-advisor-v1"]
        work_design["profile_status"] = "active"
        work_design["binding_status"] = "active"
        work_design["profile_activation_allowed"] = True
        work_design["activation_eligible"] = True
        runtime = GatewayRuntime(
            selections=resolved,
            audit_root=self.audit_root,
            compatibility_profile_id="intake-classifier-v1",
            adapters={},
        )

        readiness = runtime.readiness()

        self.assertTrue(readiness["ready"])
        self.assertFalse(readiness["compatibility_profile_ready"])
        self.assertEqual(
            readiness["ready_profile_ids"],
            [
                "delivery-refinement-advisor-v1",
                "delivery-work-design-advisor-v1",
            ],
        )
        self.assertFalse(readiness["profiles"]["intake-classifier-v1"]["ready"])
        self.assertTrue(
            readiness["profiles"]["delivery-work-design-advisor-v1"]["ready"]
        )

    def test_readiness_fails_when_no_profile_is_activation_eligible(self) -> None:
        resolved = copy.deepcopy(selections())
        for profile in resolved["profiles"].values():
            profile["profile_status"] = "suspended"
            profile["binding_status"] = "suspended"
            profile["profile_activation_allowed"] = False
            profile["activation_eligible"] = False
        runtime = GatewayRuntime(
            selections=resolved,
            audit_root=self.audit_root,
            compatibility_profile_id="intake-classifier-v1",
            adapters={},
        )

        readiness = runtime.readiness()

        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["ready_profile_ids"], [])

    @staticmethod
    def intake_request() -> dict:
        profile_id = "intake-classifier-v1"
        return {
            "profile_id": profile_id,
            "caller_identity": caller(
                profile_id, "workspace-governance/intake-assist"
            ),
            "operator_identity": {"operator_id": "operator:test"},
            "provider_output_schema_ref": (
                "platform-engineering/security/schemas/"
                "intake-classification-result.schema.json"
            ),
            "input": {"operator_supplied_intake_notes": "Review this entrant."},
        }

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
