#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import base64
import io
import json
import os
from pathlib import Path
import tempfile
from datetime import timedelta
from contextlib import ExitStack
import unittest
import uuid
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace


SCRIPT = Path(__file__).with_name("console_complete_runtime.py")
SPEC = importlib.util.spec_from_file_location("console_complete_runtime", SCRIPT)
assert SPEC and SPEC.loader
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class CompleteRuntimeTests(unittest.TestCase):
    def test_provider_tools_use_only_the_controlled_service_path(self):
        with patch.object(runtime.Path, "home", return_value=Path("/operator")), patch.dict(os.environ, {"PATH": "/untrusted"}):
            path = runtime.provider_service_path()
            self.assertEqual(path, "/operator/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
            with patch.object(runtime.shutil, "which", return_value="/resolved/tool") as which:
                runtime.require_provider_tools()
            self.assertEqual(which.call_args_list, [unittest.mock.call(name, path=path) for name in ("vault", "openssl", "git", "k3s")])

    def test_missing_provider_tools_deny_activation_before_runtime_effects(self):
        policy = self.accepted_policy()
        with ExitStack() as stack:
            stack.enter_context(patch.object(runtime, "resolve_security_decision", return_value=(policy, {})))
            admission = stack.enter_context(patch.object(runtime, "require_activation_allowed"))
            effects = [stack.enter_context(patch.object(runtime, name)) for name in
                       ("write_resolved_policies", "write_composition_supervisor", "refresh_record_authorities", "run", "credential", "deliver_repository_provisioning_identity", "write_provider_unit")]
            stack.enter_context(patch.object(runtime.shutil, "which", side_effect=lambda name, **kwargs: None if name == "vault" else "/resolved/tool"))
            with self.assertRaisesRegex(runtime.RuntimeError, "required tools unavailable: vault"):
                runtime.activate(policy)
            admission.assert_called_once_with(policy)
            for effect in effects:
                effect.assert_not_called()

    def test_missing_provider_tools_deny_normal_activation_before_supervisor_restart(self):
        policy = self.accepted_policy()
        with (patch.object(runtime.sys, "argv", ["complete-runtime", "activate"]),
              patch.object(runtime, "validate_policy", return_value=policy),
              patch.object(runtime, "resolve_security_decision", return_value=(policy, {})),
              patch.object(runtime, "require_activation_allowed"),
              patch.object(runtime, "inside_composition_supervisor", return_value=False),
              patch.object(runtime.shutil, "which", return_value=None),
              patch.object(runtime, "write_composition_supervisor") as supervisor,
              patch.object(runtime, "run") as commands,
              patch.object(runtime.sys, "stderr", io.StringIO()) as errors):
            self.assertEqual(runtime.main(), 1)
            self.assertIn("required tools unavailable", errors.getvalue())
            supervisor.assert_not_called()
            commands.assert_not_called()

    def test_current_provider_is_not_restarted_during_same_source_callback(self):
        policy = self.accepted_policy()
        catalog = runtime.provider.capability_catalog(policy, policy["security"]["platform_revision"], activated=True)
        with patch.object(runtime, "credential", return_value="synthetic-secret"), patch.object(runtime, "provider_catalog", return_value=catalog), patch.object(runtime, "run") as commands:
            self.assertEqual(runtime.require_current_provider(policy), catalog)
            runtime.refresh_stale_provider(policy)
            commands.assert_not_called()

    def test_self_declared_current_catalog_does_not_hide_wrong_source_or_unavailable_capabilities(self):
        policy = self.accepted_policy()
        current = runtime.provider.capability_catalog(policy, policy["security"]["platform_revision"], activated=True)
        stale = runtime.provider.capability_catalog(policy, "9" * 40, activated=True)
        unavailable = runtime.provider.capability_catalog(policy, policy["security"]["platform_revision"], activated=False)
        missing = json.loads(json.dumps(current)); missing["subjects"][0]["capabilities"].pop()
        malformed = json.loads(json.dumps(current)); malformed["subjects"][0]["capabilities"] = None
        for catalog in (stale, unavailable, missing, malformed):
            with self.subTest(catalog=catalog), patch.object(runtime, "credential", return_value="synthetic-secret"), patch.object(runtime, "provider_catalog", return_value=catalog):
                with self.assertRaises(runtime.RuntimeError):
                    runtime.require_current_provider(policy)

    def test_stale_provider_refreshes_once_and_waits_for_real_ready_readback(self):
        policy = self.accepted_policy()
        current = runtime.provider.capability_catalog(policy, policy["security"]["platform_revision"], activated=True)
        stale = runtime.provider.capability_catalog(policy, "9" * 40, activated=True)
        with (patch.object(runtime, "credential", return_value="synthetic-secret"),
              patch.object(runtime, "provider_catalog", side_effect=[stale, runtime.RuntimeError("starting"), current]),
              patch.object(runtime, "run") as commands,
              patch.object(runtime.time, "monotonic", side_effect=[0, 1, 2]),
              patch.object(runtime.time, "sleep")):
            runtime.refresh_stale_provider(policy)
            commands.assert_called_once_with(["systemctl", "--user", "restart", runtime.UNIT_NAME])

    def test_persistent_stale_provider_is_bounded_failure_not_an_endless_restart_loop(self):
        policy = self.accepted_policy()
        stale = runtime.provider.capability_catalog(policy, "9" * 40, activated=True)
        with (patch.object(runtime, "credential", return_value="synthetic-secret"),
              patch.object(runtime, "provider_catalog", return_value=stale),
              patch.object(runtime, "run") as commands,
              patch.object(runtime.time, "monotonic", side_effect=[0, 1, 31]),
              patch.object(runtime.time, "sleep")):
            with self.assertRaisesRegex(runtime.RuntimeError, "bounded refresh"):
                runtime.refresh_stale_provider(policy)
            commands.assert_called_once_with(["systemctl", "--user", "restart", runtime.UNIT_NAME])

    def test_activation_refreshes_after_current_marker_and_before_success_status(self):
        policy = self.accepted_policy(); events = []
        ignored = ("write_resolved_policies", "require_activation_allowed", "require_provider_tools", "write_composition_supervisor", "refresh_record_authorities", "run", "write_provider_unit", "apply_kubernetes_binding", "apply_record_authority_binding")
        with ExitStack() as stack:
            for name in ignored: stack.enter_context(patch.object(runtime, name))
            stack.enter_context(patch.object(runtime, "resolve_security_decision", return_value=(policy, {})))
            stack.enter_context(patch.object(runtime, "composition_command", return_value=[]))
            stack.enter_context(patch.object(runtime, "cross_domain_command", return_value=[]))
            stack.enter_context(patch.object(runtime, "deliver_repository_provisioning_identity", return_value={"token_expires_at": "synthetic-expiry"}))
            stack.enter_context(patch.object(runtime, "workflow_credential_manager"))
            stack.enter_context(patch.object(runtime, "credential", return_value="synthetic-secret"))
            stack.enter_context(patch.object(runtime, "cni_gateway", return_value="127.0.0.1"))
            for name in ("write_active_marker", "refresh_stale_provider", "write_repository_refresh_units", "status"):
                stack.enter_context(patch.object(runtime, name, side_effect=lambda *args, _name=name, **kwargs: events.append(_name)))
            runtime.activate(policy)
        self.assertEqual(events, ["write_active_marker", "refresh_stale_provider", "write_repository_refresh_units", "status"])

    def test_current_operator_policies_match_native_source_identity_without_aliases(self):
        policy = runtime.validate_policy()
        identity = runtime.require_operator_policy(policy)
        principals = runtime.session_projection.load_policy().principals
        self.assertEqual([p.operator for p in principals.values() if p.reference == identity], ["mfshaf7"])
        self.assertEqual(identity, "operator:mfshaf7")
        wrong = json.loads(json.dumps(policy))
        wrong["platform_operation_provider"]["operator_id"] = "operator:workspace-owner"
        with self.assertRaisesRegex(runtime.RuntimeError, "bindings disagree"):
            runtime.require_operator_policy(wrong)
        with patch.object(runtime.provider, "require_security_activation"), patch.object(runtime.provider, "git_head", return_value="a" * 40):
            with patch.object(runtime, "operator", return_value="mfshaf7"):
                runtime.require_activation_allowed(policy)
            with patch.object(runtime, "operator", return_value="someone-else"):
                with self.assertRaisesRegex(runtime.RuntimeError, "selected dev-integration operator"):
                    runtime.require_activation_allowed(policy)

    def test_each_commissioned_operator_policy_is_checked_against_the_principal(self):
        policy = runtime.validate_policy()
        files = ("session-projection-policy.yaml", "product-publication-commissioning-policy.yaml",
                 "proposal-target-commissioning-policy.yaml", "repository-catalog-commissioning-policy.yaml")
        for changed in files:
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for filename in files:
                    runtime.shutil.copyfile(runtime.PRODUCT_ROOT / filename, root / filename)
                path = root / changed
                value = runtime.yaml.safe_load(path.read_text())
                if changed == "session-projection-policy.yaml":
                    value["principals"]["mfshaf7"]["reference"] = "operator:workspace-owner"
                else:
                    value["session"]["operator_id"] = "operator:workspace-owner"
                path.write_text(runtime.yaml.safe_dump(value))
                with patch.object(runtime, "PRODUCT_ROOT", root):
                    with self.assertRaisesRegex(runtime.RuntimeError, "disagree"):
                        runtime.require_operator_policy(policy)

    def test_actual_node_readback_checks_every_operator_family_without_environment_values(self):
        policy = runtime.validate_policy()
        identity = runtime.require_operator_policy(policy)
        maps = {name: json.dumps({runtime.CONSOLE_CALLER: identity}) for name in runtime.CONSOLE_OPERATOR_FAMILIES}
        def execute_node(args, **kwargs):
            self.assertEqual(args[:2], ["k3s", "kubectl"])
            self.assertIn("exec", args)
            self.assertNotIn("caller-secret", args[-1])
            return runtime.subprocess.run(["node", "-e", args[-1]], env={"PATH": os.environ["PATH"], **maps}, capture_output=True, text=True, check=True)
        with patch.object(runtime, "run", side_effect=execute_node):
            proof = runtime.require_console_operator_bindings(policy)
            self.assertTrue(proof["consistent"])
            self.assertEqual(set(proof["families"]), set(runtime.CONSOLE_OPERATOR_FAMILIES))
            for name in runtime.CONSOLE_OPERATOR_FAMILIES:
                original = maps[name]
                for invalid in (json.dumps({runtime.CONSOLE_CALLER: "operator:workspace-owner"}), "{", "{}"):
                    with self.subTest(name=name, invalid=invalid):
                        maps[name] = invalid
                        with self.assertRaisesRegex(runtime.RuntimeError, "live Console workflow operator bindings disagree"):
                            runtime.require_console_operator_bindings(policy)
                maps[name] = original

    def test_record_group_keeps_unchanged_checkpoints_and_invalidates_peers_on_change_or_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owners = sorted(runtime.record_authority.OWNERS)
            files = {owner: root / owner / ".git" / runtime.record_authority.CHECKPOINT for owner in owners}
            for file in files.values():
                file.parent.mkdir(parents=True)
                file.write_text("prior accepted checkpoint")
            policy = {"security": {"reviewed_revisions": {owner: "a" * 40 for owner in owners}}}
            calls = []
            change = False
            fail = False
            def refresh(cache, source, owner, reviewed, *, before_change):
                calls.append(owner)
                if fail:
                    raise runtime.record_authority.RecordAuthorityError("offline")
                if change and owner == owners[-1]:
                    before_change()
                    self.assertTrue(all(not file.exists() for file in files.values()))
                elif not change:
                    self.assertTrue(all(file.exists() for file in files.values()))
                files[owner].write_text("fresh accepted checkpoint")
                return {"record_revision": reviewed}
            with (patch.object(runtime, "RECORD_AUTHORITY_ROOT", root),
                  patch.object(runtime, "repo_path", side_effect=lambda owner: root / owner),
                  patch.object(runtime.record_authority, "refresh_snapshot", side_effect=refresh)):
                runtime.refresh_record_authorities(policy)
                self.assertEqual(calls, owners)
                change = True
                calls.clear()
                runtime.refresh_record_authorities(policy)
                self.assertEqual(calls, owners + [owners[0]])
                self.assertTrue(all(file.exists() for file in files.values()))
                fail = True
                with self.assertRaises(runtime.record_authority.RecordAuthorityError):
                    runtime.refresh_record_authorities(policy)
                self.assertTrue(all(not file.exists() for file in files.values()))

    def test_security_anchor_tracks_relevant_decisions_not_unrelated_index_commits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return runtime.subprocess.run(["git", "-C", str(root), *args], check=True,
                    text=True, capture_output=True).stdout.strip()
            git("init", "-b", "main")
            git("config", "user.name", "Synthetic security owner")
            git("config", "user.email", "test@example.invalid")
            (root / "decision.yaml").write_text("status: accepted\n")
            (root / "review.md").write_text("Exact source acceptance\n")
            git("add", "."); git("commit", "-m", "accept reviewed source")
            accepted = git("rev-parse", "HEAD")
            (root / "generated-index.yaml").write_text("records: []\n")
            git("add", "."); git("commit", "-m", "update unrelated record index")
            current = git("rev-parse", "HEAD")
            self.assertNotEqual(current, accepted)
            self.assertEqual(runtime.security_acceptance_anchor(root, current, ["decision.yaml", "review.md"]), accepted)
            (root / "decision.yaml").write_text("status: revoked\n")
            git("add", "."); git("commit", "-m", "revoke decision")
            revoked = git("rev-parse", "HEAD")
            self.assertEqual(runtime.security_acceptance_anchor(root, revoked, ["decision.yaml", "review.md"]), revoked)

    def test_retained_supervision_is_required_before_uncached_live_proof(self) -> None:
        policy = self.accepted_policy()
        with (
            patch.object(runtime, "resolve_security_decision", return_value=(policy, {})),
            patch.object(runtime, "reusable_operating_receipt", return_value=None),
            patch.object(runtime, "operating_proof_lock"),
            patch.object(runtime, "require_retained_supervision", side_effect=runtime.RuntimeError("retained supervisor required")),
            patch.object(runtime, "activate") as activate,
        ):
            with self.assertRaisesRegex(runtime.RuntimeError, "retained supervisor"):
                runtime.verify_operating(policy)
            activate.assert_not_called()

    def test_normal_activation_delegates_before_lifecycle_lock_to_avoid_self_deadlock(self) -> None:
        policy = self.accepted_policy()
        with (
            patch.object(runtime.sys, "argv", ["console_complete_runtime.py", "activate"]),
            patch.object(runtime, "validate_policy", return_value=policy),
            patch.object(runtime, "inside_composition_supervisor", return_value=False),
            patch.object(runtime, "resolve_security_decision", return_value=(policy, {})),
            patch.object(runtime, "require_activation_allowed"),
            patch.object(runtime, "require_provider_tools") as tools,
            patch.object(runtime, "write_composition_supervisor") as install,
            patch.object(runtime, "composition_supervisor_unit", return_value="workspace-devint-accepted-idea-delivery-synthetic.service"),
            patch.object(runtime, "run") as commands,
            patch.object(runtime, "status", return_value=Path("/private/result.json")),
            patch.object(runtime, "operating_proof_lock", side_effect=AssertionError("outer delegate must not hold the inner unit's lock")),
        ):
            self.assertEqual(runtime.main(), 0)
            tools.assert_called_once_with()
            install.assert_called_once_with(policy)
            commands.assert_called_once_with(["systemctl", "--user", "restart", "workspace-devint-accepted-idea-delivery-synthetic.service"])

    def test_fixed_profile_supervisor_reuses_the_existing_unit_and_survives_generic_base_refresh(self) -> None:
        sys_scripts = str(runtime.REPO_ROOT / "scripts")
        import sys
        sys.path.insert(0, sys_scripts)
        try:
            import dev_integration_auto_resume as resume
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = root / "operator-orchestration-service"
            profile = owner / "dev-integration/profiles/accepted-idea-delivery/profile.yaml"
            profile.parent.mkdir(parents=True)
            profile.write_text("runtime:\n  state_model: persistent\n  resume_policy: operator-login\n")
            with (
                patch.dict(os.environ, {"XDG_CONFIG_HOME": str(root / "config")}),
                patch.object(runtime, "operator", return_value="synthetic"),
                patch.object(runtime, "repo_path", side_effect=lambda name: owner if name == "operator-orchestration-service" else runtime.REPO_ROOT),
                patch.object(runtime, "selected_repo_paths", return_value={"platform-engineering": runtime.REPO_ROOT}),
                patch.object(resume, "_run_systemctl", return_value=runtime.subprocess.CompletedProcess([], 0, "enabled\n", "")),
                patch.object(runtime, "run"),
            ):
                runtime.write_composition_supervisor(self.accepted_policy())
            units = root / "config/systemd/user"
            unit = units / "workspace-devint-accepted-idea-delivery-synthetic.service"
            dropin = units / f"{unit.name}.d/console-runtime.conf"
            self.assertIn("RemainAfterExit=yes", unit.read_text())
            self.assertIn("DEVINT_AUTO_RESUME=1", unit.read_text())
            self.assertIn("--composition", unit.read_text())
            self.assertIn("refinement-catalog", unit.read_text())
            self.assertIn("ExecStart=\nExecStart=", dropin.read_text())
            self.assertIn("console_complete_runtime.py", dropin.read_text())
            self.assertIn('"activate"', dropin.read_text())
            self.assertEqual(len(list(units.glob("*.service"))), 1)

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
            "context-governance-gateway": "3" * 40,
            "governance-operations-console": "a" * 40,
            "operator-orchestration-service": "b" * 40,
            "platform-engineering": "c" * 40,
            "workspace-governance": "d" * 40,
            "workspace-governance-control-fabric": "e" * 40,
            "workspace-prototype-studio": "1" * 40,
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
        self.assertEqual(provider["operator_id"], runtime.require_operator_policy(policy))
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
            "context-governance-gateway": "3" * 40,
            "governance-operations-console": "a" * 40,
            "operator-orchestration-service": "b" * 40,
            "platform-engineering": "c" * 40,
            "workspace-governance": "d" * 40,
            "workspace-governance-control-fabric": "e" * 40,
            "workspace-prototype-studio": "1" * 40,
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
        self.assertEqual(activation["authority"]["workspace_governance_binding"], "reviewed-record-only")
        self.assertEqual(set(activation["architecture"]["security_review_revisions"]), set(revisions.values()))
        self.assertFalse((runtime.PRODUCT_ROOT / "complete-runtime-activation-policy.yaml").exists())

    def test_current_composed_boundary_requires_the_changed_context_producer(self) -> None:
        policy = runtime.validate_policy()
        self.assertIn("context-governance-gateway", policy["security"]["required_reviewed_repos"])
        policy["security"]["required_reviewed_repos"].remove("context-governance-gateway")
        with patch.object(runtime.provider, "load_policy", return_value=policy):
            with self.assertRaisesRegex(runtime.RuntimeError, "Security decision selector is invalid"):
                runtime.validate_policy()

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
            if "-e" in args:
                return runtime.subprocess.CompletedProcess(args, 0, stdout=json.dumps({
                    "enabled": True, "bindings": {runtime.CONSOLE_CALLER: "operator:workspace-owner", "retained-caller": "operator:retained"},
                }), stderr="")
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
        manifest = next(kwargs["input_value"] for _args, kwargs in calls if kwargs.get("input_value"))
        self.assertIn("OOS_PLATFORM_OPERATION_PROVIDER_CALLER_SECRET", manifest)
        self.assertIn("secret-value-with-at-least-thirty-two-bytes", manifest)
        document = next(item for item in runtime.yaml.safe_load_all(manifest) if item["kind"] == "Secret")
        publication = json.loads(document["stringData"]["OOS_PRODUCT_PUBLICATION_CALLER_OPERATOR_BINDINGS_JSON"])
        self.assertEqual(publication[runtime.CONSOLE_CALLER], policy["platform_operation_provider"]["operator_id"])
        self.assertEqual(publication["retained-caller"], "operator:retained")
        self.assertNotIn("OOS_PRODUCT_PUBLICATION_ENABLED", document["stringData"])
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
            self.assertIn(f"Environment=PATH={runtime.provider_service_path()}", unit)
            self.assertIn("Environment=VAULT_ADDR=http://127.0.0.1:32200", unit)
            self.assertIn("Environment=XDG_RUNTIME_DIR=%t", unit)
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
            self.assertIn("OnUnitActiveSec=60s", timer)
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
                    patch.object(runtime, "refresh_record_authorities", return_value={"status": "current"}),
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

    def test_record_refresh_failure_withholds_writes_without_skipping_credential_renewal(self) -> None:
        policy = self.accepted_policy()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            (state / "active.json").write_text(json.dumps({
                "platform_tree": policy["security"]["platform_tree"],
                "security_decision_digest": policy["security"]["decision_digest"],
            }))
            delivered = {"token_expires_at": (runtime.datetime.now(runtime.UTC) + timedelta(minutes=50)).isoformat()}
            with (
                patch.object(runtime, "STATE_ROOT", state),
                patch.object(runtime, "REPOSITORY_PROVISIONING_RECEIPT", state / "missing.json"),
                patch.object(runtime, "resolve_security_decision", return_value=(policy, {})),
                patch.object(runtime, "require_materialized_policy"),
                patch.object(runtime, "require_activation_allowed"),
                patch.object(runtime, "refresh_record_authorities", side_effect=runtime.record_authority.RecordAuthorityError("provider unavailable")),
                patch.object(runtime, "deliver_repository_provisioning_identity", return_value=delivered) as deliver,
                patch.object(runtime, "workflow_credential_manager") as credentials,
                patch.object(runtime, "repository_provisioning_status") as readiness,
                patch.object(runtime, "receipt", return_value=state / "result.json") as receipt,
            ):
                with self.assertRaisesRegex(runtime.RuntimeError, "credentials remain maintained"):
                    runtime.refresh_repository_credentials(policy)
                deliver.assert_called_once_with(policy)
                credentials.return_value.renew.assert_called_once()
                readiness.assert_called_once_with(policy)
                self.assertEqual(receipt.call_args.args[2]["record_authority"], {"status": "unavailable"})

    def record_deployments(self, policy: dict) -> dict:
        """Capture the real producer patches; no cluster or credentials involved."""
        deployments = {}
        def fake_run(args, **kwargs):
            if "patch" in args:
                spec = json.loads(args[args.index("--patch") + 1])["spec"]
                deployments[next(item for item in args if item.startswith("deployment/"))] = {
                    "metadata": {"generation": 4}, "spec": {"replicas": 1, **spec},
                    "status": {"observedGeneration": 4, "updatedReplicas": 1, "availableReplicas": 1},
                }
            return runtime.subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        with patch.object(runtime, "run", side_effect=fake_run):
            runtime.apply_record_authority_binding(policy)
        return deployments

    def test_record_binding_proves_exact_owner_mounts_flags_and_consumed_generation(self) -> None:
        policy = self.accepted_policy()
        deployments = self.record_deployments(policy)
        self.assertEqual(len(deployments), 2)
        original = deployments[f"deployment/{policy['runtime']['oos_deployment']}"]
        self.assertEqual(len(original["spec"]["template"]["spec"]["containers"][0]["volumeMounts"]), 5)
        def readback(values):
            return lambda args, **kwargs: runtime.subprocess.CompletedProcess(args, 0,
                stdout=json.dumps(values[next(item for item in args if item.startswith("deployment/"))]), stderr="")
        with (
            patch.object(runtime, "run", side_effect=readback(deployments)),
            patch.object(runtime, "record_authority_status", return_value={"status": "current"}),
        ):
            self.assertEqual(runtime.record_binding_status(policy), {"status": "current"})
        for failure in ("missing", "wrong-owner", "writable", "wrong-path", "subpath", "sidecar-only", "guard-off", "wrong-profile", "old-generation", "not-updated", "not-available"):
            with self.subTest(failure=failure):
                values = json.loads(json.dumps(deployments))
                deployment = values[f"deployment/{policy['runtime']['oos_deployment']}"]
                pod = deployment["spec"]["template"]["spec"]
                container = pod["containers"][0]
                if failure == "missing":
                    container["volumeMounts"].pop()
                elif failure == "wrong-owner":
                    pod["volumes"][0]["hostPath"]["path"] = str(runtime.RECORD_AUTHORITY_ROOT / "workspace-prototype-studio")
                elif failure == "writable":
                    container["volumeMounts"][0]["readOnly"] = False
                elif failure == "wrong-path":
                    container["volumeMounts"][0]["mountPath"] = "/wrong-source"
                elif failure == "subpath":
                    container["volumeMounts"][0]["subPath"] = "not-the-owner-root"
                elif failure == "sidecar-only":
                    container["name"] = "unrelated-sidecar"
                elif failure in ("guard-off", "wrong-profile"):
                    key = "OOS_RECORD_AUTHORITY_FRESHNESS_REQUIRED" if failure == "guard-off" else "OOS_SOURCE_REALIZATION_PROFILE_ID"
                    next(item for item in container["env"] if item["name"] == key)["value"] = "wrong"
                elif failure == "old-generation":
                    deployment["status"]["observedGeneration"] = 3
                elif failure == "not-updated":
                    deployment["status"]["updatedReplicas"] = 0
                elif failure == "not-available":
                    deployment["status"]["availableReplicas"] = 0
                with (
                    patch.object(runtime, "run", side_effect=readback(values)),
                    patch.object(runtime, "record_authority_status", return_value={"status": "current"}),
                    self.assertRaises(runtime.RuntimeError),
                ):
                    runtime.record_binding_status(policy)

    def test_record_binding_rollback_restores_owner_roots_and_disables_new_guards(self) -> None:
        calls = []
        with patch.object(runtime, "run", side_effect=lambda args, **kwargs: calls.append(args) or runtime.subprocess.CompletedProcess(args, 0, "", "")):
            runtime.apply_record_authority_binding(self.accepted_policy(), enabled=False)
        patches = [json.loads(args[args.index("--patch") + 1])["spec"]["template"]["spec"] for args in calls if "patch" in args]
        self.assertEqual(len(patches), 2)
        for pod in patches:
            for volume in pod["volumes"]:
                self.assertIn(volume["hostPath"]["path"], [str(runtime.repo_path(owner)) for owner in runtime.record_authority.OWNERS])
            for item in pod["containers"][0]["env"]:
                if item["name"].endswith("REQUIRED") or item["name"] == "OOS_SOURCE_REALIZATION_ENABLED":
                    self.assertEqual(item["value"], "false")
            self.assertTrue(all(item["readOnly"] for item in pod["containers"][0]["volumeMounts"]))
        with patch.object(runtime, "run", return_value=runtime.subprocess.CompletedProcess([], 1, "", "")) as commands:
            runtime.apply_record_authority_binding(self.accepted_policy(), enabled=False)
            self.assertFalse(any("patch" in call.args[0] for call in commands.call_args_list))

    def test_primary_console_records_require_live_models_not_fixture_or_failed_reads(self) -> None:
        policy = self.accepted_policy()
        prototype = {"mode": "live", "projection": {"readModel": {"records": []}}}
        delivery = {"mode": "live", "projection": {"packages": []}}
        def response(value):
            context = Mock()
            context.__enter__ = Mock(return_value=io.BytesIO(json.dumps(value).encode()))
            context.__exit__ = Mock(return_value=False)
            return context
        with patch.object(runtime, "urlopen", side_effect=[response(prototype), response(delivery)]) as reads:
            self.assertEqual(runtime.require_console_primary_records(policy), {"prototype": 0, "delivery": 0})
            self.assertTrue(reads.call_args_list[0].args[0].endswith("/api/prototypes/records"))
            self.assertTrue(reads.call_args_list[1].args[0].endswith("/api/delivery/workspace"))
        for malformed in ({**prototype, "mode": "disconnected-preview"}, {"mode": "live", "projection": None}, {"mode": "live", "projection": {"readModel": {"records": {}}}}):
            with patch.object(runtime, "urlopen", return_value=response(malformed)), self.assertRaisesRegex(runtime.RuntimeError, "fixtures are not readiness"):
                runtime.require_console_primary_records(policy)
        with patch.object(runtime, "urlopen", side_effect=runtime.URLError("unavailable")), self.assertRaisesRegex(runtime.RuntimeError, "primary canonical read is unavailable"):
            runtime.require_console_primary_records(policy)

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
            if "apply" in args:
                secret = json.loads(kwargs["input_value"])
                slug = next(slug for slug, old in self.secrets.items() if old["metadata"]["name"] == secret["metadata"]["name"])
                contract, _ = manager.contract(slug)
                field_manager = "platform-workspace-intake" if slug == "workspace-intake" else f"platform-{contract.workflow_slug}"
                self.assertIn("--server-side", args)
                self.assertIn("--field-manager=" + field_manager, args)
                self.assertNotIn("managedFields", secret["metadata"])
                self.assertEqual(secret["metadata"]["resourceVersion"], self.secrets[slug]["metadata"]["resourceVersion"])
                secret["metadata"]["resourceVersion"] = str(int(secret["metadata"]["resourceVersion"]) + 1)
                self.secrets[slug] = secret
            if "exec" in args:
                program = args[-1]
                provider = "if(!true)" in program
                if provider and not self.consume_ok:
                    return SimpleNamespace(returncode=1, stdout="")
                results = {slug: {"configured": True, **({"http": self.probe_http, "token_consumed": True,
                            "repository_id": manager.contract(slug)[0].repository_id,
                            **({"readiness_authenticated": True} if slug in module.READINESS_WORKFLOWS else {})} if provider else {})} for slug in module.WORKFLOWS}
                return SimpleNamespace(returncode=0, stdout=json.dumps(results))
            return SimpleNamespace(returncode=0, stdout="")
        manager = module.Credentials(repo_root=runtime.REPO_ROOT, workspace_root=root,
                                     session_manifest=root / "session.yaml", run=execute, private_key=key_loader,
                                     readiness_revision="a" * 40)
        manager.target = lambda contract: self.target
        manager.readiness_source = Mock(return_value=("synthetic-preserved-caller", "http://current-wgcf:8080"))
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

    def test_caller_only_drift_repairs_whole_group_without_mint_and_uses_resource_versions(self):
        module = runtime.workflow_credentials
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp))
            manager.readiness_source.return_value = ("current-synthetic-caller-credential-123456", "http://current-wgcf:8080")
            with self.assertRaisesRegex(module.CredentialError, "projection is stale"):
                manager.status()
            with patch.object(module.intake_identity, "validated_token") as issue:
                result = manager.renew()
                issue.assert_not_called()
            self.assertEqual(result["refreshed"], [])
            self.assertEqual(len([args for args, _ in self.calls if "apply" in args]), 3)
            for slug in module.READINESS_WORKFLOWS:
                secret = self.secrets[slug]
                self.assertEqual(base64.b64decode(secret["data"]["wgcf-caller-secret"]).decode(), manager.readiness_source.return_value[0])
                self.assertEqual(secret["metadata"]["resourceVersion"], "43")
                self.assertTrue(result["identities"][slug]["readiness_authenticated"])
            versions = [json.loads(args[-1])["spec"]["template"]["metadata"]["annotations"]
                        for args, _ in self.calls if "patch" in args][-1]
            for slug in module.READINESS_WORKFLOWS:
                self.assertEqual(versions[module.ANNOTATION + slug + "-credential-resource-version"], "43")
            patch_payload = [json.loads(args[-1]) for args, _ in self.calls if "patch" in args][-1]
            environment = patch_payload["spec"]["template"]["spec"]["containers"][0]["env"]
            self.assertEqual({item["name"]: item["value"] for item in environment}, {
                **{manager.contract(slug)[0].wgcf_implementation_ref_env: "a" * 40 for slug in module.READINESS_WORKFLOWS},
                "WGCF_PRODUCT_PUBLICATION_IMPLEMENTATION_REF": "a" * 40,
                "WGCF_WORKSPACE_INTAKE_IMPLEMENTATION_REF": "a" * 40})
            self.calls.clear()
            manager.renew()
            self.assertFalse(any("apply" in args for args, _ in self.calls))
            unchanged = [json.loads(args[-1])["spec"]["template"]["metadata"]["annotations"]
                         for args, _ in self.calls if "patch" in args][-1]
            self.assertEqual(versions, unchanged)  # Same pod template, no restart.
            self.assertNotIn(manager.readiness_source.return_value[0], json.dumps(result))
            for args, _ in self.calls:
                self.assertNotIn(manager.readiness_source.return_value[0], json.dumps(args))

    def test_caller_replacement_loss_recovers_without_rotating_provider_tokens(self):
        module = runtime.workflow_credentials
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp))
            manager.readiness_source.return_value = ("current-synthetic-caller-credential-123456", "http://current-wgcf:8080")
            self.consume_ok = False
            with patch.object(module.intake_identity, "validated_token") as issue:
                with self.assertRaisesRegex(module.CredentialError, "actual OOS"):
                    manager.renew()
                self.consume_ok = True
                self.calls.clear()
                manager.renew()
                issue.assert_not_called()
            self.assertFalse(any("apply" in args for args, _ in self.calls))
            self.assertEqual(len([args for args, _ in self.calls if "rollout" in args]), 1)

    def test_missing_or_wrong_readiness_source_denies_before_any_write(self):
        module = runtime.workflow_credentials
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp))
            manager.readiness_source.side_effect = module.CredentialError("issuer consumption unavailable")
            with self.assertRaises(module.CredentialError):
                manager.renew()
            self.assertFalse(any("apply" in args or "patch" in args for args, _ in self.calls))

    def test_partial_caller_reconciliation_retains_completed_write_and_retry_finishes_remaining(self):
        module = runtime.workflow_credentials
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp))
            manager.readiness_source.return_value = ("current-synthetic-caller-credential-123456", "http://current-wgcf:8080")
            project = manager._project_binding
            count = 0
            def interrupted(*args):
                nonlocal count
                count += 1
                if count == 2:
                    raise module.CredentialError("synthetic CAS conflict")
                project(*args)
            with patch.object(manager, "_project_binding", side_effect=interrupted):
                with self.assertRaises(module.CredentialError): manager.renew()
            self.calls.clear()
            with patch.object(module.intake_identity, "validated_token") as issue:
                manager.renew()
                issue.assert_not_called()
            self.assertEqual(len([args for args, _ in self.calls if "apply" in args]), 2)

    def test_actual_generated_probe_checks_caller_consumption_and_readiness_authentication(self):
        module = runtime.workflow_credentials
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp))
            bindings = {slug: manager.binding(slug) for slug in module.WORKFLOWS}
            caller_bad, issuer_stale, publication_stale, server_status = False, False, False, 404
            def execute(args, **kwargs):
                program = args[-1]
                marker = "const specs="
                specs = json.loads(program.split(marker, 1)[1].split(";\n", 1)[0])
                environment = {"PATH": os.defpath}
                environment.update({"OOS_PRODUCT_PUBLICATION_ENABLED": "true", "OOS_WORKSPACE_INTAKE_ENABLED": "true",
                    "WGCF_PRODUCT_PUBLICATION_IMPLEMENTATION_REF": ("b" if publication_stale else "a") * 40,
                    "WGCF_WORKSPACE_INTAKE_IMPLEMENTATION_REF": "a" * 40})
                files, repositories = {}, {}
                for spec in specs:
                    environment.update(spec["required"])
                    files[environment[spec["file_env"]]] = base64.b64decode(bindings[spec["slug"]][2]["data"][manager.contract(spec["slug"])[0].runtime_secret_key]).decode()
                    repositories[files[environment[spec["file_env"]]]] = {"id": spec["id"], "full_name": spec["repository"]}
                    if "readiness" in spec:
                        environment[spec["readiness"]["secret_env"]] = "wrong-caller" if caller_bad else "synthetic-preserved-caller"
                        contract, _ = manager.contract(spec["slug"])
                        if issuer_stale:
                            environment[contract.wgcf_implementation_ref_env] = "b" * 40
                shim = "require('node:fs').readFileSync=(file)=>(" + json.dumps(files) + ")[file];\n"
                shim += ("globalThis.fetch=async(url,options)=>url.startsWith('https://api.github.com/')?"
                    "{status:200,json:async()=>({total_count:1,repositories:[" + json.dumps(repositories)
                    + "[options.headers.Authorization.slice(7)]]})}:{status:" + str(server_status) + "};\n")
                return runtime.subprocess.run([runtime.shutil.which("node"), "-e", shim + program], env=environment, text=True, capture_output=True)
            manager.run = execute
            result = manager.probe(bindings)
            self.assertTrue(all(result[slug]["readiness_authenticated"] for slug in module.READINESS_WORKFLOWS))
            issuer_stale = True
            self.assertTrue(all(value["configured"] for value in manager.probe(bindings, provider=False).values()))
            with self.assertRaises(module.CredentialError): manager.probe(bindings)
            issuer_stale = False
            publication_stale = True
            self.assertTrue(all(value["configured"] for value in manager.probe(bindings, provider=False).values()))
            with self.assertRaises(module.CredentialError): manager.probe(bindings)
            publication_stale = False
            caller_bad = True
            with self.assertRaises(module.CredentialError): manager.probe(bindings)
            caller_bad = False
            for status in (200, 401, 403, 503):
                server_status = status
                with self.subTest(status=status), self.assertRaises(module.CredentialError): manager.probe(bindings)

    def test_actual_readiness_source_rejects_wrong_principal_namespace_activation_and_unconsumed_issuer(self):
        module = runtime.workflow_credentials
        with tempfile.TemporaryDirectory() as temp:
            manager = self.manager(Path(temp))
            bindings = {slug: manager.binding(slug) for slug in module.WORKFLOWS}
            namespace = "devint-governance-control-fabric-test"
            caller = "synthetic-authoritative-readiness-caller-123456"
            environment = [
                {"name": "WGCF_ARTIFACT_REGISTRY_OOS_CALLER_ID", "value": "operator-orchestration-service"},
                {"name": "WGCF_ARTIFACT_REGISTRY_OOS_CALLER_SECRET", "valueFrom": {"secretKeyRef": {
                    "name": module.READINESS_SECRET, "key": "oos-caller-secret"}}},
                *[{"name": "WGCF_" + slug.upper().replace("-", "_") + "_READINESS_ENABLED", "value": "true"}
                  for slug in module.READINESS_WORKFLOWS],
            ]
            deployment = {"spec": {"template": {"spec": {"containers": [{"name": "api", "env": environment}]}}}}
            secret = {"metadata": {"name": module.READINESS_SECRET, "namespace": namespace,
                "labels": {"devint.profile": "governance-control-fabric", "app.kubernetes.io/component": "artifact-registry-auth"}},
                "data": {"oos-caller-secret": base64.b64encode(caller.encode()).decode()}}
            consumed = {"consumed": True}
            def execute(args, **kwargs):
                value = consumed if "exec" in args else secret if "secret" in args else deployment
                self.assertNotIn(caller, json.dumps(args))
                return SimpleNamespace(returncode=0, stdout=json.dumps(value))
            manager.run = execute
            source = lambda: module.Credentials.readiness_source(manager, bindings)
            with patch.object(module.prototype_identity, "runner_owned_readiness_namespace", return_value=namespace):
                self.assertEqual(source(), (caller, f"http://{module.READINESS_DEPLOYMENT}.{namespace}.svc.cluster.local:8080"))
                environment[0]["value"] = "another-principal"
                with self.assertRaises(module.CredentialError): source()
                environment[0]["value"] = "operator-orchestration-service"
                secret["metadata"]["namespace"] = "other-namespace"
                with self.assertRaises(module.CredentialError): source()
                secret["metadata"]["namespace"] = namespace
                environment[-1]["value"] = "false"
                with self.assertRaises(module.CredentialError): source()
                environment[-1]["value"] = "true"
                consumed["consumed"] = False
                with self.assertRaises(module.CredentialError): source()

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
            self.assertFalse(any("apply" in args for args, _ in self.calls))
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
                if "apply" in args:
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
            self.assertFalse(any("apply" in args for args, _ in self.calls))
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


@unittest.skipUnless(os.environ.get("CONSOLE_NATIVE_KUBE_PROOF_NAMESPACE"), "native local-cluster proof is opt-in")
class NativeWorkflowCredentialOwnershipTests(unittest.TestCase):
    """Exercise the actual adapter without provider issuance or real Secrets."""

    def setUp(self):
        self.manager = runtime.workflow_credential_manager(runtime.validate_policy())
        self.contract, _ = self.manager.contract("proposal-target")
        self.target = self.manager.target(self.contract)  # Existing local-cluster/session guard.
        self.assertEqual(self.target.namespace, os.environ["CONSOLE_NATIVE_KUBE_PROOF_NAMESPACE"])
        self.names = []
        self.addCleanup(self.remove_objects)

    def remove_objects(self):
        for kind, name in self.names:
            runtime.run(["k3s", "kubectl", "-n", self.target.namespace, "delete", kind, name, "--ignore-not-found=true"])

    def kubectl(self, args, payload=None, *, check=True):
        return runtime.run(["k3s", "kubectl", "-n", self.target.namespace, *args],
                           input_value=json.dumps(payload) if payload is not None else None, check=check)

    def test_actual_readiness_issuer_must_match_current_security_review(self):
        # Read-only check of the real issuer. The candidate source is not
        # commissioned, and no credential or deployment is changed here.
        decision = runtime.yaml.safe_load((runtime.WORKSPACE_ROOT / "security-architecture" /
            "docs/reviews/components/2026-10-15-governance-console-platform-operation.yaml").read_text())
        self.assertEqual(decision["status"], "accepted")
        self.manager.readiness_revision = decision["reviewed_revisions"]["workspace-governance-control-fabric"]
        bindings = {slug: self.manager.binding(slug) for slug in runtime.workflow_credentials.WORKFLOWS}
        caller, url = self.manager.readiness_source(bindings)
        self.assertGreaterEqual(len(caller), 32)
        self.assertIn("devint-governance-control-fabric-", url)
        self.manager.readiness_revision = "0" * 40
        with self.assertRaises(runtime.workflow_credentials.CredentialError):
            self.manager.readiness_source(bindings)

    def create(self, field_manager):
        name = "console-credential-ownership-proof-" + uuid.uuid4().hex[:12]
        payload = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": name, "namespace": self.target.namespace},
                   "data": {"token": "synthetic-one", "unrelated": "retained"}}
        self.names.append(("configmap", name))
        self.kubectl(["apply", "--server-side", "--field-manager=" + field_manager, "-f", "-"], payload)
        current = json.loads(self.kubectl(["get", "configmap", name, "-o", "json"]).stdout)
        return payload, current

    def test_legacy_replace_reproduces_original_owner_recovery_conflict(self):
        field_manager = "platform-" + self.contract.workflow_slug
        original, current = self.create(field_manager)
        current["data"]["token"] = "synthetic-two"
        self.kubectl(["replace", "-f", "-"], current)
        original["data"]["token"] = "synthetic-three"
        denied = self.kubectl(["apply", "--server-side", "--field-manager=" + field_manager,
                               "--dry-run=server", "-f", "-"], original, check=False)
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("conflict", denied.stderr.lower())

    def test_actual_adapter_preserves_each_owner_recovery_and_cas(self):
        for slug in runtime.workflow_credentials.WORKFLOWS:
            with self.subTest(slug=slug):
                contract, _ = self.manager.contract(slug)
                field_manager = "platform-workspace-intake" if slug == "workspace-intake" else "platform-" + contract.workflow_slug
                original, current = self.create(field_manager)
                stale = json.loads(json.dumps(current))
                current["data"]["token"] = "synthetic-two"
                self.manager._project_binding(slug, contract, self.target, current)
                stale["data"]["token"] = "synthetic-stale"
                with self.assertRaises(runtime.RuntimeError):
                    self.manager._project_binding(slug, contract, self.target, stale)
                original["data"]["token"] = "synthetic-three"
                self.kubectl(["apply", "--server-side", "--field-manager=" + field_manager, "-f", "-"], original)
                recovered = json.loads(self.kubectl(["get", "configmap", original["metadata"]["name"], "-o", "json"]).stdout)
                self.assertEqual(recovered["data"], {"token": "synthetic-three", "unrelated": "retained"})

    def test_actual_secret_producer_manifests_survive_renewal_and_recovery(self):
        module = runtime.workflow_credentials
        for slug in module.WORKFLOWS:
            with self.subTest(slug=slug):
                contract, _ = self.manager.contract(slug)
                field_manager = "platform-workspace-intake" if slug == "workspace-intake" else "platform-" + contract.workflow_slug
                token = SimpleNamespace(token="synthetic-original", expires_at="2026-10-16T10:00:00Z")
                if slug == "workspace-intake":
                    manifest = module.intake_identity.secret_manifest(contract, token, "synthetic-binding", self.target)
                else:
                    manifest = module.prototype_identity.secret_manifest(contract, token,
                        module.ProviderRepository(contract.repository, contract.repository_id),
                        "synthetic-binding", "synthetic-runtime", self.target, "synthetic-caller")
                original = module.yaml.safe_load(manifest)
                name = "console-credential-secret-proof-" + uuid.uuid4().hex[:12]
                original["metadata"]["name"] = name
                self.names.append(("secret", name))
                self.kubectl(["apply", "--server-side", "--field-manager=" + field_manager, "-f", "-"], original)
                current = json.loads(self.kubectl(["get", "secret", name, "-o", "json"]).stdout)
                stale = json.loads(json.dumps(current))
                current["data"][contract.runtime_secret_key] = base64.b64encode(b"synthetic-renewed").decode()
                if getattr(contract, "wgcf_secret_key", None):
                    current["data"][contract.wgcf_secret_key] = base64.b64encode(b"synthetic-current-wgcf-caller").decode()
                current["metadata"]["annotations"][module.ANNOTATION + "token-expires-at"] = "2026-10-16T11:00:00Z"
                self.manager._project_binding(slug, contract, self.target, current)
                projected = json.loads(self.kubectl(["get", "secret", name, "-o", "json"]).stdout)
                self.assertEqual(projected["data"], current["data"])
                with self.assertRaises(runtime.RuntimeError):
                    self.manager._project_binding(slug, contract, self.target, stale)
                original["stringData"][contract.runtime_secret_key] = "synthetic-recovered"
                original["metadata"]["annotations"][module.ANNOTATION + "token-expires-at"] = "2026-10-16T12:00:00Z"
                self.kubectl(["apply", "--server-side", "--field-manager=" + field_manager, "-f", "-"], original)
                recovered = json.loads(self.kubectl(["get", "secret", name, "-o", "json"]).stdout)
                self.assertEqual(recovered["data"], {key: base64.b64encode(value.encode()).decode()
                                 for key, value in original["stringData"].items()})


if __name__ == "__main__":
    unittest.main()
