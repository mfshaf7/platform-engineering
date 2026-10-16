#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import base64
import io
import json
from pathlib import Path
import tempfile
from datetime import timedelta
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace


SCRIPT = Path(__file__).with_name("console_complete_runtime.py")
SPEC = importlib.util.spec_from_file_location("console_complete_runtime", SCRIPT)
assert SPEC and SPEC.loader
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class CompleteRuntimeTests(unittest.TestCase):
    def test_repository_route_probe_uses_public_console_error_contract(self) -> None:
        policy = runtime.validate_policy()
        body = {"code": "repository_custody_oos_rejected", "error": "Repository custody request was not found.", "mode": "live", "status": "offline", "retryable": False}
        error = runtime.HTTPError("http://127.0.0.1/test", 404, "Not Found", {}, io.BytesIO(json.dumps(body).encode()))
        with patch.object(runtime, "urlopen", side_effect=error) as fetch:
            runtime.require_repository_projection_route(policy)
        self.assertIn("/api/repositories/provisioning/requests/", fetch.call_args.args[0].full_url)

    def test_repository_route_probe_recovers_tunnel_restart_but_rejects_false_readiness(self) -> None:
        policy = runtime.validate_policy()
        body = {"code": "repository_custody_oos_rejected", "error": "Repository custody request was not found.", "mode": "live", "status": "offline"}
        def failure(code, value):
            return runtime.HTTPError("http://127.0.0.1/test", code, "probe", {}, io.BytesIO(json.dumps(value).encode()))
        with (
            patch.object(runtime, "urlopen", side_effect=[runtime.URLError("tunnel restarting"), failure(404, body)]) as fetch,
            patch.object(runtime.time, "sleep"),
        ):
            runtime.require_repository_projection_route(policy)
            self.assertEqual(fetch.call_count, 2)
        for code, value in ((401, body), (404, {**body, "error": "Route not found."}), (404, {**body, "mode": "disconnected-preview"}), (404, [])):
            with self.subTest(code=code, value=value), patch.object(runtime, "urlopen", side_effect=failure(code, value)):
                with self.assertRaisesRegex(runtime.RuntimeError, "route is not active"):
                    runtime.require_repository_projection_route(policy)
        with (
            patch.object(runtime, "urlopen", side_effect=runtime.URLError("unavailable")),
            patch.object(runtime.time, "monotonic", side_effect=[0, 31]),
        ):
            with self.assertRaisesRegex(runtime.RuntimeError, "route is unavailable"):
                runtime.require_repository_projection_route(policy)

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
                    patch.object(runtime, "workflow_credential_manager") as workflows,
                ):
                    workflows.return_value.renew.return_value = {"refreshed": [], "identities": {}}
                    runtime.refresh_repository_credentials(policy)
                self.assertEqual(deliver.called, should_deliver)
                readiness.assert_called_once_with(policy)
                # The same annotation is always reconciled, including after a
                # crash following Secret delivery but preceding pod consumption.
                self.assertEqual(
                    workflows.return_value.renew.call_args.kwargs["extra_annotations"]["workspace-governance/repository-token-expires-at"],
                    delivered["token_expires_at"],
                )
                self.assertFalse(calls)
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
            "workflow_credentials_renewed": True,
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
            "workflow_credentials_renewed": True,
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


class WorkflowCredentialTests(unittest.TestCase):
    def manager(self, root: Path, *, minutes=50):
        module = runtime.workflow_credentials
        self.target = SimpleNamespace(namespace="devint-test", profile_id="accepted-idea-delivery", session_id="session-current")
        self.secrets = {}
        self.calls = []
        self.providers = []
        self.keys = []
        self.probe_http = 200
        self.consume_ok = True
        def key_loader(vault):
            key = root / (vault["secret_path"].split("/")[-1] + ".pem")
            key.write_text("synthetic private key")
            key.chmod(0o600)
            self.keys.append(key)
            return key
        def execute(args, **kwargs):
            self.calls.append((args, kwargs))
            if "get" in args:
                slug = next(slug for slug, secret in self.secrets.items() if secret["metadata"]["name"] in args)
                return SimpleNamespace(returncode=0, stdout=json.dumps(self.secrets[slug]))
            if "replace" in args:
                secret = json.loads(kwargs["input_value"])
                slug = next(slug for slug, old in self.secrets.items() if old["metadata"]["name"] == secret["metadata"]["name"])
                self.assertEqual(secret["metadata"]["resourceVersion"], self.secrets[slug]["metadata"]["resourceVersion"])
                secret["metadata"]["resourceVersion"] = str(int(secret["metadata"]["resourceVersion"]) + 1)
                self.secrets[slug] = secret
            if "exec" in args:
                program = args[-1]
                provider = "if(!true)" in program
                if provider and not self.consume_ok:
                    return SimpleNamespace(returncode=1, stdout="")
                results = {slug: {"configured": True, **({"http": self.probe_http, "token_consumed": True,
                            "repository_id": manager.contract(slug)[0].repository_id} if provider else {})} for slug in module.WORKFLOWS}
                return SimpleNamespace(returncode=0, stdout=json.dumps(results))
            return SimpleNamespace(returncode=0, stdout="")
        manager = module.Credentials(repo_root=runtime.REPO_ROOT, workspace_root=root,
                                     session_manifest=root / "session.yaml", run=execute, private_key=key_loader)
        manager.target = lambda contract: self.target
        for slug, ids in module.WORKFLOWS.items():
            contract, _ = manager.contract(slug)
            self.secrets[slug] = {"apiVersion": "v1", "kind": "Secret", "type": "Opaque",
                "metadata": {"name": contract.runtime_secret_name, "namespace": self.target.namespace, "resourceVersion": "42",
                    "labels": {"app.kubernetes.io/managed-by": "platform-engineering"},
                    "annotations": {module.ANNOTATION + "credential-binding-digest": module.intake_identity.binding_digest(
                        contract, *ids, module.ProviderRepository(contract.repository, contract.repository_id)),
                        module.ANNOTATION + "dev-integration-profile": self.target.profile_id,
                        module.ANNOTATION + "dev-integration-session": self.target.session_id,
                        module.ANNOTATION + "token-expires-at": (runtime.datetime.now(runtime.UTC) + timedelta(minutes=minutes)).isoformat()}},
                "data": {contract.runtime_secret_key: base64.b64encode(("ghs_old_" + slug).encode()).decode(),
                         "wgcf-caller-secret": base64.b64encode(b"synthetic-preserved-caller").decode()}}
        return manager

    def issue(self, args, contract):
        self.assertTrue(all(key.exists() for key in self.keys))
        self.assertEqual((args.app_id, args.installation_id), runtime.workflow_credentials.WORKFLOWS[args.private_key_file.stem])
        client = Mock()
        self.providers.append(client)
        return client, SimpleNamespace(token="ghs_new_" + args.private_key_file.stem,
                    expires_at=(runtime.datetime.now(runtime.UTC) + timedelta(minutes=60)).isoformat()), None

    def test_policy_requires_whole_closed_identity_group(self):
        policy = runtime.validate_policy()
        for required in ([], policy["workflow_credentials"]["required"][:-1], [*policy["workflow_credentials"]["required"], "unapproved"]):
            with self.subTest(required=required), self.assertRaises(runtime.workflow_credentials.CredentialError):
                runtime.workflow_credentials.validate_policy({**policy, "workflow_credentials": {"enabled": True, "required": required}})

    def test_target_reuses_existing_local_cluster_guard_before_secret_access(self):
        module = runtime.workflow_credentials
        manager = module.Credentials(repo_root=runtime.REPO_ROOT, workspace_root=Path("/tmp/test"),
                                     session_manifest=Path("/tmp/test/session.yaml"), run=Mock(), private_key=Mock())
        target = SimpleNamespace(namespace="devint-test")
        with patch.object(module, "load_dev_integration_target", return_value=target), patch.object(module, "verify_dev_integration_cluster", return_value=target) as verify:
            self.assertIs(manager.target(Mock()), target)
            verify.assert_called_once_with("k3s kubectl", target)
        with patch.object(module, "load_dev_integration_target", return_value=target), patch.object(module, "verify_dev_integration_cluster", side_effect=module.IdentityError("wrong cluster")):
            with self.assertRaisesRegex(module.IdentityError, "wrong cluster"):
                manager.binding("proposal-target")
        manager.run.assert_not_called()

    def test_expired_group_rotates_once_preserving_owner_fields_and_proves_consumption(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp), minutes=-5)
            with patch.object(runtime.workflow_credentials.intake_identity, "validated_token", side_effect=self.issue) as issue:
                result = manager.renew(extra_annotations={"repository-version": "current"})
            self.assertEqual(issue.call_count, 5)
            self.assertEqual(len(result["identities"]), 5)
            self.assertEqual(len([args for args, _ in self.calls if "patch" in args]), 1)
            self.assertEqual(len([args for args, _ in self.calls if "rollout" in args]), 1)
            self.assertFalse(any("restart" in args for args, _ in self.calls))
            for secret in self.secrets.values():
                self.assertEqual(base64.b64decode(secret["data"]["wgcf-caller-secret"]), b"synthetic-preserved-caller")
                self.assertEqual(secret["metadata"]["resourceVersion"], "43")
            for client in self.providers:
                client.revoke_token.assert_called_once()
                self.assertTrue(client.revoke_token.call_args.args[0].startswith("ghs_old_"))
            self.assertTrue(all(not key.exists() for key in self.keys))
            for args, kwargs in self.calls:
                for slug in runtime.workflow_credentials.WORKFLOWS:
                    self.assertNotIn("ghs_old_" + slug, json.dumps(args))
                    self.assertNotIn("ghs_new_" + slug, json.dumps(args))
            self.assertNotIn("ghs_", json.dumps(result))

    def test_unchanged_tick_and_interrupted_consumption_reuse_existing_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp))
            with patch.object(runtime.workflow_credentials.intake_identity, "validated_token") as issue:
                result = manager.renew()
            issue.assert_not_called()
            self.assertEqual(result["refreshed"], [])
            patch_index = next(i for i, (args, _) in enumerate(self.calls) if "patch" in args)
            provider_index = next(i for i, (args, _) in enumerate(self.calls) if "exec" in args and "if(!true)" in args[-1])
            self.assertLess(patch_index, provider_index)
            self.assertEqual(len([args for args, _ in self.calls if "rollout" in args]), 1)

    def test_force_renews_all_even_before_expiry(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp))
            with patch.object(runtime.workflow_credentials.intake_identity, "validated_token", side_effect=self.issue) as issue:
                manager.renew(force=True)
            self.assertEqual(issue.call_count, 5)

    def test_failed_consumption_keeps_owner_state_and_recovers_without_reminting(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp), minutes=-5)
            self.consume_ok = False
            with patch.object(runtime.workflow_credentials.intake_identity, "validated_token", side_effect=self.issue) as issue:
                with self.assertRaisesRegex(runtime.workflow_credentials.CredentialError, "actual OOS"):
                    manager.renew()
                self.assertEqual(issue.call_count, 5)
                for client in self.providers:
                    client.revoke_token.assert_not_called()
                self.consume_ok = True
                recovered = manager.renew()
                self.assertEqual(issue.call_count, 5)
                self.assertEqual(recovered["refreshed"], [])
                self.assertEqual(len(recovered["identities"]), 5)
            self.assertTrue(all(not key.exists() for key in self.keys))

    def test_invalid_mounted_token_is_renewed_even_with_fresh_expiry_annotation(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp))
            self.probe_http = 401
            def issue(args, contract):
                self.probe_http = 200
                return self.issue(args, contract)
            with patch.object(runtime.workflow_credentials.intake_identity, "validated_token", side_effect=issue) as minted:
                result = manager.renew()
            self.assertEqual(minted.call_count, 5)
            self.assertEqual(len(result["refreshed"]), 5)

    def test_missing_key_denies_group_before_any_credential_change(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp), minutes=-5)
            original = manager.private_key
            def key(vault):
                if vault["secret_path"].endswith("prototype-closure"):
                    raise runtime.RuntimeError("Vault source unavailable")
                return original(vault)
            manager.private_key = key
            with patch.object(runtime.workflow_credentials.intake_identity, "validated_token") as issue:
                with self.assertRaisesRegex(runtime.RuntimeError, "Vault source"):
                    manager.renew()
            issue.assert_not_called()
            self.assertFalse(any("replace" in args for args, _ in self.calls))
            self.assertTrue(all(not key.exists() for key in self.keys))

    def test_binding_drift_and_missing_owner_secret_never_gain_activation_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp))
            for path, replacement in (("namespace", "wrong-owner"), ("resourceVersion", 42)):
                with self.subTest(path=path):
                    original = self.secrets["proposal-target"]["metadata"][path]
                    self.secrets["proposal-target"]["metadata"][path] = replacement
                    with self.assertRaises(runtime.workflow_credentials.CredentialError):
                        manager.status()
                    self.secrets["proposal-target"]["metadata"][path] = original
            manager.run = Mock(return_value=SimpleNamespace(returncode=1, stdout=""))
            with self.assertRaisesRegex(runtime.workflow_credentials.CredentialError, "commissioning"):
                manager.renew()

    def test_expired_stale_or_unconsumed_credentials_cannot_pass_status(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp), minutes=-1)
            with self.assertRaisesRegex(runtime.workflow_credentials.CredentialError, "expired"):
                manager.status()
            manager = self.manager(Path(temp))
            self.secrets["proposal-target"]["metadata"]["annotations"][runtime.workflow_credentials.ANNOTATION + "dev-integration-session"] = "prior-session"
            with self.assertRaisesRegex(runtime.workflow_credentials.CredentialError, "stale"):
                manager.status()
            manager = self.manager(Path(temp))
            self.consume_ok = False
            with self.assertRaisesRegex(runtime.workflow_credentials.CredentialError, "actual OOS"):
                manager.status()

    def test_provider_denial_is_not_readiness(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp))
            for status in (401, 403):
                self.probe_http = status
                with self.subTest(status=status), self.assertRaises(runtime.workflow_credentials.CredentialError):
                    manager.status()

    def test_cas_replacement_failure_revokes_unprojected_token(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp), minutes=-5)
            execute = manager.run
            def conflict(args, **kwargs):
                if "replace" in args:
                    raise runtime.RuntimeError("conflict")
                return execute(args, **kwargs)
            manager.run = conflict
            with patch.object(runtime.workflow_credentials.intake_identity, "validated_token", side_effect=self.issue):
                with self.assertRaisesRegex(runtime.workflow_credentials.CredentialError, "replacement failed"):
                    manager.renew()
            self.providers[0].revoke_token.assert_called_once_with("ghs_new_proposal-target")
            self.assertTrue(all(not key.exists() for key in self.keys))

    def test_later_invalid_key_or_grant_cannot_partially_rotate_the_group(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp), minutes=-5)
            def invalid(args, contract):
                if args.private_key_file.stem == "prototype-maturity":
                    raise runtime.workflow_credentials.IdentityError("key invalid")
                return self.issue(args, contract)
            with patch.object(runtime.workflow_credentials.intake_identity, "validated_token", side_effect=invalid):
                with self.assertRaisesRegex(runtime.workflow_credentials.IdentityError, "key invalid"):
                    manager.renew()
            self.assertFalse(any("replace" in args for args, _ in self.calls))
            self.assertEqual(len(self.providers), 2)
            for provider in self.providers:
                self.assertTrue(provider.revoke_token.call_args.args[0].startswith("ghs_new_"))
            self.assertTrue(all(not key.exists() for key in self.keys))

    def test_wrong_repo_or_malformed_provider_proof_is_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp))
            execute = manager.run
            def invalid(args, **kwargs):
                result = execute(args, **kwargs)
                if "exec" in args:
                    value = json.loads(result.stdout)
                    value["proposal-target"]["repository_id"] = 999
                    return SimpleNamespace(returncode=0, stdout=json.dumps(value))
                return result
            manager.run = invalid
            with self.assertRaisesRegex(runtime.workflow_credentials.CredentialError, "incomplete"):
                manager.status()


if __name__ == "__main__":
    unittest.main()
