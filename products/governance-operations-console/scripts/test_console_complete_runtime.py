#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
from datetime import timedelta
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("console_complete_runtime.py")
SPEC = importlib.util.spec_from_file_location("console_complete_runtime", SCRIPT)
assert SPEC and SPEC.loader
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class CompleteRuntimeTests(unittest.TestCase):
    def accepted_policy(self) -> dict:
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
        return policy

    def test_case_1291_positive_source_contract_is_one_existing_composition(self) -> None:
        policy = runtime.validate_policy()
        provider = policy["platform_operation_provider"]
        self.assertEqual(provider["composition_id"], "refinement-catalog")
        self.assertEqual(provider["profile_id"], "accepted-idea-delivery")
        self.assertEqual(provider["operator_id"], "operator:workspace-owner")
        self.assertEqual(policy["delivery"]["work_item_ref"], "openproject://work_packages/1291")
        self.assertEqual(policy["security"]["status"], "pending")
        self.assertTrue(policy["repository_provisioning"]["enabled"])
        self.assertEqual(
            policy["repository_provisioning"]["security_gate_id"],
            "gate:repository-custody-runtime-activation",
        )

    def test_case_1291_negative_pending_security_blocks_activation(self) -> None:
        policy = runtime.validate_policy()
        with self.assertRaisesRegex(runtime.RuntimeError, "not accepted"):
            runtime.require_activation_allowed(policy)

    def test_complete_runtime_commands_select_the_current_platform_checkout(self) -> None:
        policy = runtime.validate_policy()
        reviewed_checkout = Path("/tmp/reviewed-platform-worktree")
        with (
            patch.object(runtime, "REPO_ROOT", reviewed_checkout),
            patch.object(runtime, "REPO_PATH_OVERRIDES", {}),
        ):
            self.assertEqual(runtime.repo_path("platform-engineering"), reviewed_checkout)
            for command in (
                runtime.composition_command(policy, "up"),
                runtime.cross_domain_command("activate"),
            ):
                self.assertIn(
                    f"platform-engineering={reviewed_checkout}",
                    command,
                )

        explicit_checkout = Path("/tmp/explicit-platform-worktree")
        with (
            patch.object(runtime, "REPO_ROOT", reviewed_checkout),
            patch.object(
                runtime,
                "REPO_PATH_OVERRIDES",
                {"platform-engineering": explicit_checkout},
            ),
        ):
            self.assertEqual(runtime.repo_path("platform-engineering"), explicit_checkout)

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
        self.assertTrue(activation["owners"]["wgcf"]["workspace_continuity_projection_enabled"])
        self.assertTrue(activation["repository_custody"]["wgcf_readiness_enabled"])
        self.assertEqual(
            activation["repository_custody"]["provisioning_credential_binding_ref"],
            policy["repository_provisioning"]["credential_binding_ref"],
        )
        self.assertEqual(activation["authority"]["security_revision"], "f" * 40)
        self.assertEqual(set(activation["architecture"]["security_review_revisions"]), set(revisions.values()))
        self.assertFalse((runtime.PRODUCT_ROOT / "complete-runtime-activation-policy.yaml").exists())

    def test_merged_identical_source_survives_worktree_retirement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            main = workspace / "platform-engineering"
            candidate = workspace / "candidate"
            main.mkdir()

            def git(*args):
                return runtime.subprocess.run(
                    ["git", "-C", str(main), *args],
                    check=True, capture_output=True, text=True,
                )

            git("init", "-b", "main")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                "commit", "--allow-empty", "-m", "base")
            git("update-ref", "refs/remotes/origin/main", "HEAD")
            git("worktree", "add", "--detach", str(candidate), "HEAD")
            with (
                patch.object(runtime, "WORKSPACE_ROOT", workspace),
                patch.object(runtime, "REPO_ROOT", candidate),
                patch.object(runtime, "REPO_PATH_OVERRIDES", {}),
            ):
                self.assertEqual(runtime.persistent_platform_source(), main)
                self.assertEqual(
                    runtime.composition_command(runtime.validate_policy(), "up")[1],
                    str(main / "scripts/dev_integration.py"),
                )
                (candidate / "pending-change").write_text("unique work", encoding="utf-8")
                self.assertEqual(runtime.persistent_platform_source(), candidate)
                (candidate / "pending-change").unlink()
                (main / "pending-change").write_text("unique work", encoding="utf-8")
                self.assertEqual(runtime.persistent_platform_source(), candidate)

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

        with tempfile.TemporaryDirectory() as temp_dir:
            state_root = Path(temp_dir) / "oos-platform-operation"
            repository_state_root = Path(temp_dir) / "oos-repository-custody"
            with (
                patch.object(runtime, "run", side_effect=fake_run),
                patch.object(runtime, "namespace", return_value="devint-test"),
                patch.object(runtime, "OOS_STATE_ROOT", state_root),
                patch.object(runtime, "REPOSITORY_STATE_ROOT", repository_state_root),
            ):
                runtime.apply_kubernetes_binding(policy, "10.42.0.1", "secret-value-with-at-least-thirty-two-bytes")
            self.assertEqual(state_root.stat().st_mode & 0o777, 0o700)
        serialized_args = json.dumps([item[0] for item in calls])
        self.assertNotIn("secret-value-with-at-least-thirty-two-bytes", serialized_args)
        manifest = calls[0][1]["input_value"]
        self.assertIn("OOS_PLATFORM_OPERATION_PROVIDER_CALLER_SECRET", manifest)
        self.assertIn("secret-value-with-at-least-thirty-two-bytes", manifest)
        patch_call = next(args for args, _kwargs in calls if "patch" in args)
        state_patch = json.loads(patch_call[patch_call.index("--patch") + 1])
        pod = state_patch["spec"]["template"]["spec"]
        self.assertEqual(pod["volumes"], [
            {
                "name": runtime.OOS_STATE_VOLUME_NAME,
                "hostPath": {"path": str(state_root), "type": "Directory"},
            },
            {
                "name": "governance-console-repository-custody-state",
                "hostPath": {"path": str(repository_state_root), "type": "Directory"},
            },
        ])
        self.assertEqual(pod["containers"][0]["volumeMounts"], [
            {
                "name": runtime.OOS_STATE_VOLUME_NAME,
                "mountPath": runtime.OOS_STATE_MOUNT_PATH,
            },
            {
                "name": "governance-console-repository-custody-state",
                "mountPath": "/var/lib/oos/repository-custody",
            },
        ])
        flattened = " ".join(" ".join(call) for call, _kwargs in calls)
        self.assertIn("OOS_REPOSITORY_CUSTODY_ENABLED=true", flattened)
        self.assertIn(
            "--from=secret/operator-orchestration-service-repository-provisioning-provider",
            flattened,
        )

    def test_repository_private_key_uses_vault_stdin_and_private_temporary_file(self) -> None:
        policy = runtime.validate_policy()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((args, kwargs))
            return runtime.subprocess.CompletedProcess(
                args,
                0,
                stdout="-----BEGIN PRIVATE KEY-----\nmaterial\n-----END PRIVATE KEY-----\n",
                stderr="",
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            state_root = Path(temp_dir) / "state"
            private_root = state_root / "private"
            with (
                patch.object(runtime, "STATE_ROOT", state_root),
                patch.object(runtime, "PRIVATE_ROOT", private_root),
                patch.object(runtime, "vault_token", return_value="operator-vault-token"),
                patch.object(runtime, "run", side_effect=fake_run),
            ):
                path = runtime.repository_provisioning_private_key(policy)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn("BEGIN PRIVATE KEY", path.read_text(encoding="utf-8"))
        serialized_args = json.dumps(calls[0][0])
        self.assertNotIn("operator-vault-token", serialized_args)
        self.assertEqual(calls[0][1]["input_value"], "operator-vault-token\n")

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

    def test_repository_refresh_units_use_surviving_source_and_no_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            units = Path(temp_dir) / "units"
            with (
                patch.object(runtime, "UNIT_ROOT", units),
                patch.object(runtime, "repo_path", return_value=Path("/tmp/reviewed-source")),
                patch.object(runtime, "run"),
                patch.object(runtime.shutil, "which", return_value="/usr/bin/python3"),
            ):
                runtime.write_repository_refresh_units()
            service = (units / runtime.REPOSITORY_REFRESH_SERVICE).read_text()
            timer = (units / runtime.REPOSITORY_REFRESH_TIMER).read_text()
            self.assertIn("WorkingDirectory=/tmp/reviewed-source", service)
            self.assertIn("refresh-credentials", service)
            self.assertIn("ConditionPathExists=", service)
            self.assertIn("OnUnitActiveSec=300s", timer)
            self.assertNotIn("VAULT_TOKEN", service)
            self.assertNotIn("privateKey", service)

    def test_repository_refresh_is_early_idempotent_and_recovers_interrupted_consumption(self) -> None:
        policy = self.accepted_policy()
        for minutes, should_deliver in ((50, False), (10, True), (-5, True)):
            with self.subTest(minutes=minutes), tempfile.TemporaryDirectory() as temp_dir:
                state = Path(temp_dir)
                (state / "active.json").write_text(json.dumps({
                    "platform_tree": policy["security"]["platform_tree"],
                    "security_decision_digest": policy["security"]["decision_digest"],
                }))
                delivered = {
                    "token_expires_at": (runtime.datetime.now(runtime.UTC) + timedelta(minutes=minutes)).isoformat(),
                    "credential_binding_digest": policy["repository_provisioning"]["credential_binding_ref"]["digest"],
                }
                delivery_receipt = state / "delivery.json"
                delivery_receipt.write_text(json.dumps(delivered))
                calls = []
                with (
                    patch.object(runtime, "STATE_ROOT", state),
                    patch.object(runtime, "REPOSITORY_PROVISIONING_RECEIPT", delivery_receipt),
                    patch.object(runtime, "resolve_security_decision", return_value=(policy, {})),
                    patch.object(runtime, "require_materialized_policy"),
                    patch.object(runtime, "require_activation_allowed"),
                    patch.object(runtime, "deliver_repository_provisioning_identity", return_value=delivered) as deliver,
                    patch.object(runtime, "repository_provisioning_status") as readiness,
                    patch.object(runtime, "namespace", return_value="devint-test"),
                    patch.object(runtime, "receipt", return_value=state / "result.json") as receipt,
                    patch.object(runtime, "run", side_effect=lambda args, **kwargs: calls.append(args)),
                ):
                    runtime.refresh_repository_credentials(policy)
                self.assertEqual(deliver.called, should_deliver)
                readiness.assert_called_once_with(policy)
                # The same annotation is always reconciled, including after a
                # crash following Secret delivery but preceding pod consumption.
                patch_value = json.loads(calls[0][-1])
                self.assertEqual(
                    patch_value["spec"]["template"]["metadata"]["annotations"]["workspace-governance/repository-token-expires-at"],
                    delivered["token_expires_at"],
                )
                self.assertNotIn("restart", calls[1])
                self.assertEqual(receipt.call_args.args[2]["refreshed"], should_deliver)

    def test_repository_refresh_denies_stale_runtime_without_minting(self) -> None:
        policy = self.accepted_policy()
        with tempfile.TemporaryDirectory() as temp_dir:
            state = Path(temp_dir)
            (state / "active.json").write_text(json.dumps({"platform_tree": "stale"}))
            with (
                patch.object(runtime, "STATE_ROOT", state),
                patch.object(runtime, "resolve_security_decision", return_value=(policy, {})),
                patch.object(runtime, "require_materialized_policy"),
                patch.object(runtime, "require_activation_allowed"),
                patch.object(runtime, "deliver_repository_provisioning_identity") as deliver,
                patch.object(runtime, "run") as run,
            ):
                with self.assertRaisesRegex(runtime.RuntimeError, "binding is stale"):
                    runtime.refresh_repository_credentials(policy)
                deliver.assert_not_called()
                run.assert_not_called()

    def test_repository_refresh_does_not_wait_on_lifecycle_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = Path(temp_dir)
            with (
                patch.object(runtime, "STATE_ROOT", state),
                patch.object(runtime, "OPERATING_PROOF_LOCK_PATH", state / "lifecycle.lock"),
            ):
                with runtime.operating_proof_lock():
                    with self.assertRaisesRegex(runtime.RuntimeError, "lifecycle is busy"):
                        with runtime.operating_proof_lock(blocking=False):
                            self.fail("renewal acquired an occupied lifecycle lock")

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
        patch_call = next(call for call in calls if "patch" in call)
        state_patch = json.loads(patch_call[patch_call.index("--patch") + 1])
        pod = state_patch["spec"]["template"]["spec"]
        self.assertEqual(pod["volumes"], [
            {"name": runtime.OOS_STATE_VOLUME_NAME, "$patch": "delete"},
            {
                "name": "governance-console-repository-custody-state",
                "$patch": "delete",
            },
        ])
        self.assertEqual(pod["containers"][0]["volumeMounts"][0]["$patch"], "delete")
        self.assertIn("OOS_REPOSITORY_CUSTODY_ENABLED-", flattened)

    def test_rollback_removes_oos_binding_before_cross_domain_waits(self) -> None:
        policy = runtime.validate_policy()
        calls = []

        def fake_remove(_policy):
            calls.append("remove-oos-binding")
            return []

        def fake_run(args, **_kwargs):
            if runtime.RESOLVED_ACTIVATION_POLICY_PATH.name in " ".join(args):
                calls.append("cross-domain-rollback")
            return runtime.subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            activation = root / "cross-domain-policy.yaml"
            activation.write_text("present\n", encoding="utf-8")
            with (
                patch.object(runtime, "STATE_ROOT", root / "state"),
                patch.object(runtime, "PRIVATE_ROOT", root / "state" / "private"),
                patch.object(runtime, "RECEIPT_ROOT", root / "state" / "receipts"),
                patch.object(runtime, "UNIT_ROOT", root / "units"),
                patch.object(runtime, "RESOLVED_ACTIVATION_POLICY_PATH", activation),
                patch.object(runtime, "remove_kubernetes_binding", side_effect=fake_remove),
                patch.object(runtime, "run", side_effect=fake_run),
            ):
                runtime.rollback(policy)
        self.assertEqual(calls[:2], ["remove-oos-binding", "cross-domain-rollback"])

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
            receipts = root / "state" / "receipts"
            self.assertFalse(any(receipts.glob("*-rollback.json")))

    def test_receipt_contains_digests_and_never_credentials(self) -> None:
        policy = runtime.validate_policy()
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(runtime, "RECEIPT_ROOT", Path(temp_dir)):
                path = runtime.receipt("status", policy, {"provider_active": True})
            value = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(value["content_digest"].startswith("sha256:"))
        self.assertFalse(value["credential_values_embedded"])
        self.assertNotIn("caller_secret", json.dumps(value).casefold())

    def test_verify_operating_reuses_exact_locked_receipt(self) -> None:
        policy = self.accepted_policy()
        proof = {
            "activation_receipt": "/private/activate.json",
            "invalid_credential_denied": True,
            "revoked_gate_denied": True,
            "stale_state_denied": True,
            "process_loss_recovered": True,
            "restart_receipt": "/private/restart.json",
            "rollback_receipt": "/private/rollback.json",
            "teardown_receipt": "/private/teardown.json",
            "restored_activation_receipt": "/private/restored.json",
            "normal_availability_restored": True,
            "repository_provisioning_restored": True,
            "repository_credentials_renewed": True,
            "credential_refresh_receipt": "/private/refresh.json",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            state_root = Path(temp_dir) / "state"
            receipt_root = state_root / "receipts"
            lock_path = state_root / "verify-operating.lock"
            with (
                patch.object(runtime, "STATE_ROOT", state_root),
                patch.object(runtime, "RECEIPT_ROOT", receipt_root),
                patch.object(runtime, "OPERATING_PROOF_LOCK_PATH", lock_path),
            ):
                prior = runtime.receipt("verify-operating", policy, proof)
                with (
                    patch.object(runtime, "resolve_security_decision", return_value=(policy, {})),
                    patch.object(runtime, "activate", side_effect=AssertionError("cached proof must not activate")),
                ):
                    result = runtime.verify_operating(policy)
            self.assertEqual(result, prior)
            self.assertEqual(lock_path.stat().st_mode & 0o777, 0o600)

    def test_operating_receipt_reuse_rejects_stale_or_malformed_receipts(self) -> None:
        policy = self.accepted_policy()
        proof = {
            "activation_receipt": "/private/activate.json",
            "invalid_credential_denied": True,
            "revoked_gate_denied": True,
            "stale_state_denied": True,
            "process_loss_recovered": True,
            "restart_receipt": "/private/restart.json",
            "rollback_receipt": "/private/rollback.json",
            "teardown_receipt": "/private/teardown.json",
            "restored_activation_receipt": "/private/restored.json",
            "normal_availability_restored": True,
            "repository_provisioning_restored": True,
            "repository_credentials_renewed": True,
            "credential_refresh_receipt": "/private/refresh.json",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            receipt_root = Path(temp_dir) / "receipts"
            with patch.object(runtime, "RECEIPT_ROOT", receipt_root):
                path = runtime.receipt("verify-operating", policy, proof)
                stale = json.loads(json.dumps(policy))
                stale["security"]["decision_digest"] = "sha256:" + "9" * 64
                self.assertIsNone(runtime.reusable_operating_receipt(stale))
                value = json.loads(path.read_text(encoding="utf-8"))
                value["content_digest"] = "sha256:" + "0" * 64
                path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
                path.chmod(0o600)
                self.assertIsNone(runtime.reusable_operating_receipt(policy))


if __name__ == "__main__":
    unittest.main()
