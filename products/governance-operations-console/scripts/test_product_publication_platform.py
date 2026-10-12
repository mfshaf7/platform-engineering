from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).with_name("product_publication_platform.py")
SPEC = importlib.util.spec_from_file_location("product_publication_platform", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ProductPublicationPlatformTests(unittest.TestCase):
    def test_policy_is_exactly_internal_and_binds_activated_sources(self) -> None:
        policy = module.load_policy()
        binding = policy["product_publication"]
        self.assertEqual(policy["activation"]["delivery_id"], "delivery-894")
        self.assertEqual(
            policy["activation"]["work_item_ref"],
            "openproject://work_packages/1264",
        )
        self.assertEqual(
            policy["activation"]["security_gate_id"],
            "gate:product-publication-audience-activation",
        )
        self.assertEqual(
            policy["architecture"]["relationship"],
            "exact-security-reviewed-lineage",
        )
        self.assertEqual(binding["target"]["posture"], "internal")
        self.assertEqual(
            policy["owners"]["wgcf"]["revision"],
            "8cc666efbb4bb6c582571c438a3a8fa5c8342cdb",
        )
        self.assertEqual(
            policy["owners"]["wgcf"]["security_reviewed_revision"],
            "d12545242fed839df3bce65ad4dd5d6482e7854a",
        )
        self.assertEqual(
            policy["owners"]["oos"]["revision"],
            "a690e25b902c248b43f055a69f1b5e6647c01d3e",
        )
        self.assertEqual(policy["owners"]["oos"]["container"], "operator-orchestration-service")
        self.assertEqual(policy["owners"]["wgcf"]["container"], "api")
        self.assertEqual(
            binding["wgcf_contract_root"], "/app/contracts/product-publication"
        )
        self.assertEqual(
            binding["authority_revision"],
            "ade4549746bc6e727e97397be7b0c89758677a0c",
        )
        self.assertEqual(
            binding["security_reviewed_authority_revision"],
            "213b9fed48f8bd0e6e6fd658bfeae38cfd9e3784",
        )
        self.assertEqual(
            binding["manifest_revision"],
            "79f95608c71fd4d74244e89324c6c5d45cd416f7",
        )
        self.assertEqual(
            binding["security_reviewed_manifest_revision"],
            "83b0e20786bd6cd531e1043acf96df60ee5a3555",
        )
        self.assertEqual(
            binding["manifest_digest"],
            "sha256:e042aae5afc266cf23f02de747ee773561efb9541747ca14a94c0f35c614015e",
        )
        self.assertEqual(
            binding["security_decision"]["approved_target_postures"],
            ["internal"],
        )
        self.assertEqual(
            set(module.command_security_decision(policy)),
            {"uri", "digest", "revision"},
        )
        self.assertFalse(policy["credentials"]["browser_credentials_allowed"])

    def test_architecture_binds_current_corrected_packet_to_security_reviewed_anchor(self) -> None:
        policy = module.load_policy()
        architecture = policy["architecture"]
        review = "\n".join([
            architecture["security_reviewed"]["uri"],
            *architecture["security_review_revisions"],
        ])
        module.base.require_architecture_binding(policy, review)
        with self.assertRaisesRegex(module.base.ActivationError, "security-reviewed"):
            module.base.require_architecture_binding(
                policy,
                review.replace(architecture["security_reviewed"]["uri"], "missing"),
            )

    def test_canonical_manifest_digest_is_independent_of_json_key_order(self) -> None:
        first = {"product": {"id": "console", "revision": 1}, "active": True}
        second = {"active": True, "product": {"revision": 1, "id": "console"}}
        self.assertEqual(
            module.canonical_digest(first), module.canonical_digest(second)
        )

    def test_changed_authority_binding_supersedes_the_old_proof_identity(self) -> None:
        policy = module.load_policy()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            intent = state / "proof-intent.json"
            intent.write_text(
                json.dumps({
                    "request_id": "product-publication-request:platform:1258",
                    "idempotency_key": "product-publication:platform:1258",
                    "manifest_source": {"manifest_digest": "sha256:" + "0" * 64},
                }),
                encoding="utf-8",
            )
            with (
                patch.object(module, "STATE_ROOT", state),
                patch.object(module, "INTENT_PATH", intent),
                patch.object(module.base, "ensure_private_directory"),
            ):
                current = module.proof_intent(policy)
            self.assertNotEqual(
                current["request_id"], "product-publication-request:platform:1258"
            )
            self.assertTrue(list(state.glob("proof-intent-superseded-*.json")))

    def test_positive_proof_reads_a_durable_result_before_submitting(self) -> None:
        policy = module.load_policy()
        prior = policy["product_publication"]["existing_internal_publication"]
        result = {
            "state": "applied",
            "packet": {"grants": {
                "source_authority": False,
                "runtime_authority": False,
                "release_authority": False,
                "security_acceptance": False,
                "lifecycle_mutation": False,
            }, "authority_refs": {"readiness_receipt_ref": "wgcf://readiness"}},
            "receipt": {
                "receipt_id": prior["receipt_id"],
                "owner_receipt_ref": "oos://receipt/test",
                "publication_posture": "internal",
                "publication_version": 1,
            },
            "receipt_digest": prior["receipt_digest"],
            "command_digest": prior["command_digest"],
            "resolution": "read",
            "command": {
                "request_id": prior["request_id"],
                "security_decision": prior["security_decision"],
            },
        }
        calls: list[tuple[str, dict | None]] = []

        def request(_policy, path, *, body=None):
            calls.append((path, body))
            if len(calls) == 1:
                return 502, {
                    "code": "product_publication_oos_unavailable",
                    "retryable": True,
                }
            return 200, result

        with (
            patch.object(module, "console_request", side_effect=request),
            patch.object(module.time, "sleep"),
        ):
            proof = module.positive_proof(policy)
        self.assertEqual(proof["receipt_digest"], prior["receipt_digest"])
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(body is None for _, body in calls))

    def test_restart_reads_the_same_existing_receipt(self) -> None:
        policy = module.load_policy()
        positive = {
            "command": {"request_id": "product-publication-request:test"},
            "receipt_digest": "sha256:" + "1" * 64,
        }
        readback = {
            "resolution": "read",
            "receipt_digest": positive["receipt_digest"],
        }
        with (
            patch.object(module.base, "kubectl", return_value=Mock(stdout="")),
            patch.object(module.base, "run", return_value=Mock(returncode=0)),
            patch.object(module, "product_mode", return_value={"mode": "live"}),
            patch.object(module, "positive_proof", return_value=readback),
        ):
            result = module.restart_and_replay(policy, positive)
        self.assertEqual(result, readback)

    def test_negative_proof_rejects_every_inactive_target(self) -> None:
        policy = module.load_policy()
        intent = {
            "request_id": "product-publication-request:platform:1264:test",
            "idempotency_key": "product-publication:platform:1264:test",
            "manifest_source": {"manifest_digest": "sha256:" + "a" * 64},
        }
        positive = {
            "request_id": intent["request_id"],
            "receipt_digest": "sha256:" + "1" * 64,
            "command": {
                **intent,
                "action": "publish",
                "current_publication_posture": "unlisted",
                "security_decision": {
                    "uri": "security",
                    "digest": "sha256:" + "2" * 64,
                    "revision": "3" * 40,
                },
                "operator_decision": {"reason": "Existing decision."},
                "target_publication": policy["product_publication"]["target"],
            },
        }
        direct_results = [
            (401, {"error": "caller_auth_invalid"}),
            (403, {"error": "product_publication_security_decision_mismatch"}),
            (409, {"error": "product_publication_idempotency_conflict"}),
            *[
                (403, {"error": "product_publication_target_posture_not_approved"})
                for _ in range(4)
            ],
        ]
        console_results = [
            (502, {
                "code": "product_publication_oos_rejected",
                "error": "product_publication_readiness_mismatch",
            }),
            (200, {"receipt_digest": positive["receipt_digest"]}),
        ]
        with (
            patch.object(module, "proof_intent", return_value=intent),
            patch.object(module, "direct_oos_request", side_effect=direct_results),
            patch.object(module, "console_request", side_effect=console_results),
            patch.object(module.base, "read_oos_secret", return_value="secret"),
        ):
            outcomes = module.negative_proof(policy, positive)
        self.assertEqual(
            {key for key in outcomes if key.startswith("target-")},
            {"target-unlisted", "target-client", "target-public", "target-archived"},
        )
        self.assertEqual(
            outcomes["replay-conflict"]["code"],
            "product_publication_idempotency_conflict",
        )

    def test_process_loss_restores_oos_and_preserves_only_accepted_state(self) -> None:
        policy = module.load_policy()
        intent = {
            "request_id": "product-publication-request:platform:1264:test",
            "idempotency_key": "product-publication:platform:1264:test",
        }
        positive = {
            "request_id": intent["request_id"],
            "receipt_digest": "sha256:" + "1" * 64,
        }

        def kubectl(*args):
            if "get" in args:
                return Mock(stdout=json.dumps({"status": {"readyReplicas": 0}}))
            return Mock(stdout="")

        with (
            patch.object(module, "proof_intent", return_value=intent),
            patch.object(module.base, "kubectl", side_effect=kubectl) as kubectl_mock,
            patch.object(module.base, "run", return_value=Mock(returncode=0)),
            patch.object(module, "product_mode", return_value={"mode": "live"}),
            patch.object(module, "console_request", side_effect=[
                (503, {"code": "product_publication_oos_unavailable"}),
                (404, {"code": "not_found"}),
                (200, {"receipt_digest": positive["receipt_digest"]}),
            ]),
        ):
            evidence = module.process_loss_and_recovery(policy, positive)
        self.assertTrue(evidence["interrupted_state_absent"])
        self.assertEqual(evidence["accepted_receipt_digest"], positive["receipt_digest"])
        scale_calls = [call for call in kubectl_mock.call_args_list if "scale" in call.args]
        self.assertEqual(scale_calls[0].args[-1], "--replicas=0")
        self.assertEqual(scale_calls[-1].args[-1], "--replicas=1")

    def test_process_loss_rejects_an_unexpected_server_failure(self) -> None:
        policy = module.load_policy()
        intent = {
            "request_id": "product-publication-request:platform:1264:test",
            "idempotency_key": "product-publication:platform:1264:test",
        }
        positive = {
            "request_id": intent["request_id"],
            "receipt_digest": "sha256:" + "1" * 64,
        }

        def kubectl(*args):
            if "get" in args:
                return Mock(stdout=json.dumps({"status": {"readyReplicas": 0}}))
            return Mock(stdout="")

        with (
            patch.object(module, "proof_intent", return_value=intent),
            patch.object(module.base, "kubectl", side_effect=kubectl),
            patch.object(module.base, "run", return_value=Mock(returncode=0)),
            patch.object(module, "product_mode", return_value={"mode": "live"}),
            patch.object(
                module,
                "console_request",
                return_value=(500, {"code": "unexpected_internal_error"}),
            ),
        ):
            with self.assertRaisesRegex(
                module.ProductPublicationError,
                "did not fail as unavailable",
            ):
                module.process_loss_and_recovery(policy, positive)

    def test_partial_or_broader_policy_fails_closed(self) -> None:
        policy = module.load_policy()
        policy["product_publication"]["target"]["posture"] = "public"
        with patch.object(module.base, "validate"):
            with self.assertRaisesRegex(module.ProductPublicationError, "only the approved internal"):
                module.validate(policy)

    def test_console_environment_adds_integrity_metadata_without_credentials(self) -> None:
        policy = module.load_policy()
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory)
            env_path = private / "console.env"
            env_path.write_text("OOS_CALLER_SECRET=private-value\n", encoding="utf-8")
            with (
                patch.object(module.base, "PRIVATE_ROOT", private),
                patch.object(module.base, "run", return_value=Mock(returncode=0)),
            ):
                module.write_console_environment(policy)
            content = env_path.read_text(encoding="utf-8")
            self.assertIn("GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_AUTHORITY_REVISION=", content)
            self.assertIn("OOS_CALLER_SECRET=private-value", content)
            self.assertNotIn("WGCF_PRODUCT_PUBLICATION_CALLER_SECRET=", content)

    def test_workload_patch_uses_secret_reference_and_read_only_owner_source(self) -> None:
        policy = module.load_policy()
        patches: list[tuple[str, str, dict]] = []
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(module, "state_directory", return_value=Path(directory)),
                patch.object(module.base, "ensure_private_directory"),
                patch.object(module.base, "repo_path", return_value=Path("/owner")),
                patch.object(module.base, "kubectl", return_value=Mock(stdout="")),
                patch.object(
                    module,
                    "strategic_patch",
                    side_effect=lambda namespace, deployment, value: patches.append(
                        (namespace, deployment, value)
                    ),
                ),
            ):
                module.configure_workloads(policy)
        self.assertEqual(len(patches), 2)
        oos_container = patches[0][2]["spec"]["template"]["spec"]["containers"][0]
        secret = next(
            item for item in oos_container["env"]
            if item["name"] == "WGCF_PRODUCT_PUBLICATION_CALLER_SECRET"
        )
        self.assertIn("valueFrom", secret)
        self.assertNotIn("value", secret)
        wgcf_mount = patches[1][2]["spec"]["template"]["spec"]["containers"][0]["volumeMounts"][0]
        self.assertTrue(wgcf_mount["readOnly"])

    def test_workload_rollback_deletes_mounts_by_their_patch_merge_key(self) -> None:
        policy = module.load_policy()
        patches: list[dict] = []
        with (
            patch.object(module.base, "kubectl", return_value=Mock(stdout="")),
            patch.object(
                module,
                "strategic_patch",
                side_effect=lambda _namespace, _deployment, value: patches.append(value),
            ),
        ):
            module.remove_workload_binding(policy, "oos")
            module.remove_workload_binding(policy, "wgcf")
        mounts = [
            value["spec"]["template"]["spec"]["containers"][0]["volumeMounts"][0]
            for value in patches
        ]
        self.assertEqual(
            [mount["mountPath"] for mount in mounts],
            [
                policy["product_publication"]["oos_mount_path"],
                policy["product_publication"]["wgcf_owner_mount_path"],
            ],
        )
        self.assertTrue(all(mount["$patch"] == "delete" for mount in mounts))

    def test_receipt_digest_excludes_its_own_digest_field(self) -> None:
        policy = module.load_policy()
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(module, "STATE_ROOT", Path(directory)),
                patch.object(module, "RECEIPT_ROOT", Path(directory) / "receipts"),
                patch.object(module, "source_revisions", return_value={"platform-engineering": "a" * 40}),
                patch.object(module.base, "operator", return_value="operator"),
            ):
                path = module.receipt("test", policy, {"ok": True})
                value = json.loads(path.read_text(encoding="utf-8"))
                digest = value.pop("content_digest")
                self.assertEqual(
                    digest,
                    module.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()),
                )


if __name__ == "__main__":
    unittest.main()
