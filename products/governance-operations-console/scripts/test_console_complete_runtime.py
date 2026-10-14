#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("console_complete_runtime.py")
SPEC = importlib.util.spec_from_file_location("console_complete_runtime", SCRIPT)
assert SPEC and SPEC.loader
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class CompleteRuntimeTests(unittest.TestCase):
    def test_case_1291_positive_source_contract_is_one_existing_composition(self) -> None:
        policy = runtime.validate_policy()
        provider = policy["platform_operation_provider"]
        self.assertEqual(provider["composition_id"], "refinement-catalog")
        self.assertEqual(provider["profile_id"], "accepted-idea-delivery")
        self.assertEqual(provider["operator_id"], "operator:workspace-owner")
        self.assertEqual(policy["delivery"]["work_item_ref"], "openproject://work_packages/1291")
        self.assertEqual(policy["security"]["status"], "pending")

    def test_case_1291_negative_pending_security_blocks_activation(self) -> None:
        policy = runtime.validate_policy()
        with self.assertRaisesRegex(runtime.RuntimeError, "not accepted"):
            runtime.require_activation_allowed(policy)

    def test_security_decision_materializes_exact_runtime_without_source_pin_update(self) -> None:
        policy = runtime.validate_policy()
        revisions = {
            "governance-operations-console": "a" * 40,
            "operator-orchestration-service": "b" * 40,
            "platform-engineering": "c" * 40,
            "workspace-governance": "d" * 40,
            "workspace-governance-control-fabric": "e" * 40,
        }
        policy["security"].update({
            "status": "accepted",
            "decision_uri": "security-architecture://git/" + "f" * 40 + "/decision.yaml",
            "decision_digest": "sha256:" + "1" * 64,
            "platform_revision": revisions["platform-engineering"],
            "platform_tree": "2" * 40,
            "reviewed_revisions": revisions,
            "security_revision": "f" * 40,
        })
        activation = runtime.resolved_activation_policy(policy)
        self.assertEqual(activation["console"]["revision"], revisions["governance-operations-console"])
        self.assertEqual(activation["owners"]["oos"]["revision"], revisions["operator-orchestration-service"])
        self.assertEqual(activation["authority"]["security_revision"], "f" * 40)
        self.assertEqual(set(activation["architecture"]["security_review_revisions"]), set(revisions.values()))
        self.assertFalse((runtime.PRODUCT_ROOT / "complete-runtime-activation-policy.yaml").exists())

    def test_kubernetes_secret_is_sent_on_stdin_not_process_arguments(self) -> None:
        policy = runtime.validate_policy()
        policy["security"] = {
            "decision_digest": "sha256:" + "a" * 64,
            "decision_uri": "security-architecture://decision/platform-operation-v1",
            "reviewed_revisions": {"operator-orchestration-service": "b" * 40},
        }
        calls = []

        def fake_run(args, **kwargs):
            calls.append((args, kwargs))
            return runtime.subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with (
            patch.object(runtime, "run", side_effect=fake_run),
            patch.object(runtime, "namespace", return_value="devint-test"),
        ):
            runtime.apply_kubernetes_binding(policy, "10.42.0.1", "secret-value-with-at-least-thirty-two-bytes")
        serialized_args = json.dumps([item[0] for item in calls])
        self.assertNotIn("secret-value-with-at-least-thirty-two-bytes", serialized_args)
        manifest = calls[0][1]["input_value"]
        self.assertIn("OOS_PLATFORM_OPERATION_PROVIDER_CALLER_SECRET", manifest)
        self.assertIn("secret-value-with-at-least-thirty-two-bytes", manifest)

    def test_provider_unit_uses_private_environment_and_no_inline_secret(self) -> None:
        policy = runtime.validate_policy()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with (
                patch.object(runtime, "STATE_ROOT", root / "state"),
                patch.object(runtime, "PRIVATE_ROOT", root / "state" / "private"),
                patch.object(runtime, "UNIT_ROOT", root / "units"),
                patch.object(runtime, "run"),
                patch.object(runtime.shutil, "which", return_value="/usr/bin/python3"),
            ):
                runtime.write_provider_unit(policy, "10.42.0.1", "secret-value-with-at-least-thirty-two-bytes")
                unit = (root / "units" / runtime.UNIT_NAME).read_text(encoding="utf-8")
                env = root / "state" / "private" / "provider.env"
            self.assertIn(f"EnvironmentFile={env}", unit)
            self.assertNotIn("secret-value-with-at-least-thirty-two-bytes", unit)
            self.assertEqual(env.stat().st_mode & 0o777, 0o600)

    def test_rollback_removes_only_complete_runtime_bindings(self) -> None:
        policy = runtime.validate_policy()
        calls = []
        with (
            patch.object(runtime, "run", side_effect=lambda args, **kwargs: calls.append(args) or runtime.subprocess.CompletedProcess(args, 0, stdout="", stderr="")),
            patch.object(runtime, "namespace", return_value="devint-test"),
        ):
            runtime.remove_kubernetes_binding(policy)
        flattened = " ".join(" ".join(call) for call in calls)
        self.assertIn("OOS_PLATFORM_OPERATION_ENABLED-", flattened)
        self.assertIn(runtime.SECRET_NAME, flattened)
        self.assertNotIn("WGCF_REPOSITORY_READINESS_CALLER_SECRET-", flattened)

    def test_incomplete_rollback_fails_without_success_receipt(self) -> None:
        policy = runtime.validate_policy()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def fake_run(args, **_kwargs):
                failed = "set" in args and "env" in args
                return runtime.subprocess.CompletedProcess(args, 1 if failed else 0, stdout="", stderr="")

            with (
                patch.object(runtime, "STATE_ROOT", root / "state"),
                patch.object(runtime, "PRIVATE_ROOT", root / "state" / "private"),
                patch.object(runtime, "RECEIPT_ROOT", root / "state" / "receipts"),
                patch.object(runtime, "UNIT_ROOT", root / "units"),
                patch.object(runtime, "RESOLVED_ACTIVATION_POLICY_PATH", root / "missing-policy.yaml"),
                patch.object(runtime, "run", side_effect=fake_run),
                patch.object(runtime, "namespace", return_value="devint-test"),
            ):
                with self.assertRaisesRegex(runtime.RuntimeError, "rollback is incomplete"):
                    runtime.rollback(policy)
            self.assertFalse((root / "state" / "receipts").exists())

    def test_receipt_contains_digests_and_never_credentials(self) -> None:
        policy = runtime.validate_policy()
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(runtime, "RECEIPT_ROOT", Path(temp_dir)):
                path = runtime.receipt("status", policy, {"provider_active": True})
            value = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(value["content_digest"].startswith("sha256:"))
        self.assertFalse(value["credential_values_embedded"])
        self.assertNotIn("caller_secret", json.dumps(value).casefold())


if __name__ == "__main__":
    unittest.main()
