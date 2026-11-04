#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("platform_operation_provider.py")
SPEC = importlib.util.spec_from_file_location("platform_operation_provider", SCRIPT)
assert SPEC and SPEC.loader
provider = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provider)
from test_agent_source_intent import source_input
from test_agent_source_intent import admission_snapshot
from test_console_instance_source import native as native_source_proof, POLICY as INSTANCE_POLICY, OWNER as INSTANCE_OWNER
import yaml


SOURCE = "a" * 40


def accepted_policy(root: Path) -> dict:
    value = provider.load_policy()
    # Exercise the disabled transport separately from the installation's
    # selected route. Enabling alone never replaces composed Security acceptance.
    value["instance_records"] = {"enabled": False}
    # Stable synthetic actor, independent of the installed human principal.
    value["platform_operation_provider"]["operator_id"] = "operator:workspace-owner"
    value["workspace_root"] = str(root)
    value["runtime_state_root"] = str(root / "runtime")
    value["security"].update({
        "status": "accepted",
        "decision_uri": "security-architecture://decisions/platform-operation-v1",
        "decision_digest": "sha256:" + "b" * 64,
        "platform_revision": SOURCE,
        "platform_tree": provider.git_tree(),
    })
    return value


def command(policy: dict, *, action: str = "dev-integration.status", input_value: dict | None = None) -> dict:
    profile = policy["platform_operation_provider"]["profile_id"]
    if action in provider.source_credentials.ACTION_SET and input_value is None:
        input_value = source_input()
        input_value["source_intent"]["caller_id"] = policy["platform_operation_provider"]["caller_id"]
    value = {
        "schema_version": 1,
        "command_id": f"command:{profile}:{action.rsplit('.', 1)[1]}:1",
        "idempotency_key": f"idempotency:{profile}:{action.rsplit('.', 1)[1]}:1",
        "correlation_id": f"correlation:{profile}:1",
        "causation_id": None,
        "actor_ref": "operator:workspace-owner",
        "subject": {
            "kind": "dev-integration-profile",
            "ref": f"profile:{profile}",
            "expected_source_version": SOURCE,
        },
        "capability_id": action if action in provider.source_credentials.ACTION_SET else f"dev-integration.{profile}.{action.rsplit('.', 1)[1]}",
        "action": action,
        "input": input_value if input_value is not None else {},
        "requested_at": "2026-10-15T00:00:00Z",
    }
    value["intent_digest"] = provider.canonical_digest(provider.command_intent(value))
    value["approval"] = {
        "decision": "approved",
        "operator_id": "operator:workspace-owner",
        "decision_ref": "approval:platform-operation:1",
        "decided_at": "2026-10-15T00:00:01Z",
        "intent_digest": value["intent_digest"],
    }
    return value


class PlatformOperationProviderTests(unittest.TestCase):
    def test_selected_internal_registration_still_requires_composed_security_acceptance(self):
        policy = provider.load_policy()
        with self.assertRaises(provider.ProviderError) as denied:
            provider.require_security_activation(policy, SOURCE)
        self.assertEqual(denied.exception.code, "platform_provider_security_gate_required")

    def test_private_checkout_has_strict_authenticated_default_off_transport_and_no_command_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); policy = accepted_policy(root)
            policy["security"]["reviewed_revisions"]["workspace-governance"] = INSTANCE_POLICY["revision"]
            store = provider.OperationStore(root / "state")
            service = provider.ProviderService(policy, root / "policy.yaml", store, SOURCE)
            lookup = {"schema_version": 1, "owner_repo": INSTANCE_OWNER, "operation": "bootstrap", "action": "clone", "branch": "main", "expected_base": "a" * 40,
                "authority_ref": {key: native_source_proof()["source_authority"][key] for key in ("canonical_authority", "record_ref", "policy_ref")}}
            handler = provider.handler_for(service, "oos", "synthetic-owner-secret")
            with provider.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
                target = f"http://127.0.0.1:{server.server_port}/v1/console-operations/source-checkout"
                def request(value=lookup, secret="synthetic-owner-secret", suffix=""):
                    return Request(target + suffix, data=json.dumps(value).encode(), headers={"x-platform-caller-id": "oos", "x-platform-caller-secret": secret})
                try:
                    with patch.object(provider, "activation_is_current", return_value=True), \
                         patch.object(provider.private_checkout, "checkout", return_value={"synthetic": "checkout-receipt"}) as effect, \
                         patch.object(provider, "spawn_worker") as worker:
                        for req, code in ((request(secret="wrong"), 403), (request(), 503)):
                            with self.assertRaises(HTTPError) as denied: urlopen(req, timeout=2)
                            self.assertEqual(denied.exception.code, code); denied.exception.close()
                        effect.assert_not_called(); policy["instance_records"] = {"enabled": True}
                        for req in (request({**lookup, "destination": "/arbitrary/source"}), request(suffix="?token=forged")):
                            with self.assertRaises(HTTPError) as denied: urlopen(req, timeout=2)
                            self.assertEqual(denied.exception.code, 400); denied.exception.close()
                        with urlopen(request(), timeout=2) as response: self.assertEqual(json.load(response), {"synthetic": "checkout-receipt"})
                        self.assertEqual(effect.call_args.kwargs["workspace_root"], root)
                        self.assertEqual(list(store.operations.glob("*.json")), []); worker.assert_not_called()
                finally:
                    server.shutdown(); thread.join()

    def test_host_source_authority_read_is_authenticated_current_default_off_and_has_no_source_effect(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = accepted_policy(root)
            policy["security"]["reviewed_revisions"]["workspace-governance"] = INSTANCE_POLICY["revision"]
            store = provider.OperationStore(root / "state")
            service = provider.ProviderService(policy, root / "policy.yaml", store, SOURCE)
            lookup = {"schema_version": 1, "owner_repo": INSTANCE_OWNER, "operation": "ordinary-source"}
            native = native_source_proof("ordinary-source")
            reader = unittest.mock.Mock()
            reader.read.return_value = SimpleNamespace(source_authority=native["source_authority"])
            with patch.object(provider, "activation_is_current", return_value=True), \
                 patch.object(provider.record_authority, "read_instance_source_policy", return_value=INSTANCE_POLICY), \
                 patch.object(provider, "instance_source_connection", return_value=reader), \
                 patch.object(provider.private_source, "inspect_owner_controls") as source_files, \
                 patch.object(provider, "spawn_worker") as worker:
                handler = provider.handler_for(service, "oos", "synthetic-owner-secret")
                with provider.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
                    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
                    target = f"http://127.0.0.1:{server.server_port}/v1/console-operations/source-authority/inspect"
                    def request(value=lookup, secret="synthetic-owner-secret", suffix=""):
                        return Request(target + suffix, data=json.dumps(value).encode(),
                            headers={"x-platform-caller-id": "oos", "x-platform-caller-secret": secret})
                    try:
                        for req, code in ((request(secret="wrong"), 403), (request(), 503)):
                            with self.assertRaises(HTTPError) as denied: urlopen(req, timeout=2)
                            self.assertEqual(denied.exception.code, code); denied.exception.close()
                        reader.read.assert_not_called()
                        policy["instance_records"] = {"enabled": True}
                        for req in (request({**lookup, "operation": []}), request({**lookup, "caller_secret": "forged"}), request(suffix="?instance_id=other")):
                            with self.assertRaises(HTTPError) as denied: urlopen(req, timeout=2)
                            self.assertEqual(denied.exception.code, 400); denied.exception.close()
                        with urlopen(request(), timeout=2) as response: self.assertEqual(json.load(response), native)
                        reader.read.assert_called_once_with(INSTANCE_OWNER, "ordinary-source")
                        reader.read.return_value = None
                        with urlopen(request(), timeout=2) as response:
                            legacy = json.load(response)
                        self.assertEqual(legacy["canonical_authority"], {"kind": "legacy-git", "repo": "workspace-governance", "revision": INSTANCE_POLICY["revision"]})
                        reader.read.side_effect = provider.instance_source.InstanceSourceError("private dependency detail")
                        with self.assertRaises(HTTPError) as denied: urlopen(request(), timeout=2)
                        self.assertEqual(denied.exception.code, 503)
                        self.assertNotIn("private dependency detail", denied.exception.read().decode()); denied.exception.close()
                        source_files.assert_not_called(); worker.assert_not_called()
                        self.assertEqual(list(store.operations.glob("*.json")), [])
                    finally:
                        server.shutdown(); thread.join()

    def test_private_control_inspection_is_authenticated_default_off_strict_and_never_a_generic_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = accepted_policy(root)
            store = provider.OperationStore(root / "state")
            service = provider.ProviderService(policy, root / "policy.yaml", store, SOURCE)
            lookup = {"schema_version": 1, "owner_repo": INSTANCE_OWNER, "operation": "bootstrap", "paths": ["AGENTS.md"],
                "authority_ref": {key: native_source_proof()["source_authority"][key] for key in ("canonical_authority", "record_ref", "policy_ref")}}
            handler = provider.handler_for(service, "oos", "synthetic-owner-secret")
            with provider.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
                target = f"http://127.0.0.1:{server.server_port}/v1/console-operations/source-controls/inspect"
                def request(raw=None, secret="synthetic-owner-secret", suffix=""):
                    return Request(target + suffix, data=json.dumps(lookup).encode() if raw is None else raw,
                        headers={"x-platform-caller-id": "oos", "x-platform-caller-secret": secret})
                try:
                    with patch.object(provider, "activation_is_current", return_value=True), \
                         patch.object(provider.private_source, "inspect_owner_controls", return_value={"synthetic": "private-owner-files"}) as inspect, \
                         patch.object(provider, "spawn_worker") as worker:
                        for req, code in ((request(secret="wrong"), 403), (request(), 503)):
                            with self.assertRaises(HTTPError) as denied: urlopen(req, timeout=2)
                            self.assertEqual(denied.exception.code, code)
                            denied.exception.close()
                        inspect.assert_not_called()
                        policy["instance_records"] = {"enabled": True}
                        policy["security"]["reviewed_revisions"]["workspace-governance"] = INSTANCE_POLICY["revision"]
                        for req in (request(b'{"owner_repo":"one","owner_repo":"two"}'), request(suffix="?instance_id=other"), request(b"x" * 16385)):
                            with self.assertRaises(HTTPError) as denied: urlopen(req, timeout=2)
                            self.assertIn(denied.exception.code, (400, 413))
                            denied.exception.close()
                        inspect.assert_not_called()
                        with urlopen(request(), timeout=2) as response: self.assertEqual(json.load(response), {"synthetic": "private-owner-files"})
                        inspect.assert_called_once()
                        self.assertEqual(inspect.call_args.args[0], lookup)
                        self.assertEqual(list(store.operations.glob("*.json")), [])
                        worker.assert_not_called()
                finally:
                    server.shutdown(); thread.join()

    def test_native_source_uses_a_fresh_independent_reader_and_resolves_actual_alias_by_provider_id(self):
        from dataclasses import replace
        legacy = admission_snapshot()
        legacy = replace(legacy, inventory=yaml.safe_dump({"schema_version": 2, "repos": {}, "retired_repos": {}}).encode())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "private").mkdir(mode=0o700)
            binding = root / "private/instance-source-reader.json"
            binding.write_text(json.dumps({"schema_version": 1, "instance_id": "synthetic-installation", "base_url": "http://127.0.0.1:8080",
                "caller_id": "platform-engineering-source-reader", "caller_secret": "p" * 32}))
            binding.chmod(0o600)
            policy = provider.load_policy()
            policy.update(runtime_state_root=str(root), instance_records={"enabled": True})
            policy["security"]["reviewed_revisions"]["workspace-governance"] = INSTANCE_POLICY["revision"]
            intent = source_input()["source_intent"]
            intent.update(repository="example-org/different-physical-name", repository_id=123)
            with patch.object(provider.record_authority, "read_repository_admission", return_value=vars(legacy)), \
                 patch.object(provider.record_authority, "read_instance_source_policy", return_value=INSTANCE_POLICY), \
                 patch.object(provider.instance_source.InstanceSourceReader, "_fetch", return_value=native_source_proof("ordinary-source")) as read:
                result = provider.source_inventory_snapshot(policy, intent)
                self.assertEqual(result.owner_repo, INSTANCE_OWNER)
                self.assertIn("/provider-repositories/github/123/source-authority?operation=ordinary-source", read.call_args.args[0].full_url)
                self.assertEqual(read.call_args.args[0].get_header("X-wgcf-caller-id"), "platform-engineering-source-reader")
                binding.chmod(0o644)
                with self.assertRaises(provider.source_credentials.SourceIntentError) as failure:
                    provider.source_inventory_snapshot(policy, intent)
                self.assertEqual(failure.exception.code, "platform_source_authority_unavailable")
                self.assertEqual(read.call_count, 1)

    def test_unconfigured_native_reader_does_not_revoke_legacy_admission_or_fake_a_new_native_owner(self):
        legacy = admission_snapshot()
        with tempfile.TemporaryDirectory() as directory:
            policy = provider.load_policy()
            policy["runtime_state_root"] = directory
            policy["security"]["reviewed_revisions"]["workspace-governance"] = "e" * 40
            intent = source_input()["source_intent"]
            intent.update(repository="mfshaf7-workspace/sample-owner", repository_id=123456789)
            with patch.object(provider.record_authority, "read_repository_admission", return_value=vars(legacy)):
                self.assertEqual(provider.source_inventory_snapshot(policy, intent), legacy)
                policy["instance_records"] = {"enabled": True}
                self.assertEqual(provider.source_inventory_snapshot(policy, intent), legacy)
                intent.update(repository="example-org/new-private-owner", repository_id=321)
                with self.assertRaises(provider.source_credentials.SourceIntentError): provider.source_inventory_snapshot(policy, intent)

    def test_case_1291_positive_catalog_is_exact_and_finite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = accepted_policy(Path(temp_dir))
            catalog = provider.capability_catalog(policy, SOURCE, activated=True)
        self.assertEqual(catalog["freshness"], "current")
        self.assertEqual(catalog["subjects"][0]["ref"], "profile:accepted-idea-delivery")
        actions = {item["action"] for item in catalog["subjects"][0]["capabilities"]}
        self.assertEqual(actions, provider.ALLOWED_ACTIONS)
        self.assertTrue(all(item["approval_required"] for item in catalog["subjects"][0]["capabilities"]))
        self.assertEqual(
            [item["action"] for item in catalog["subjects"][0]["capabilities"] if item["destructive"]],
            ["agent-source.revoke", "dev-integration.stop"],
        )

    def test_case_1291_negative_pending_or_stale_security_blocks_provider(self) -> None:
        policy = provider.load_policy()
        with self.assertRaisesRegex(provider.ProviderError, "not accepted"):
            provider.require_security_activation(policy, SOURCE)
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = accepted_policy(Path(temp_dir))
            policy["security"]["platform_tree"] = "c" * 40
            with self.assertRaisesRegex(provider.ProviderError, "not the Security-accepted"):
                provider.ProviderService(
                    policy,
                    Path("policy.yaml"),
                    provider.OperationStore(Path(temp_dir) / "state"),
                    SOURCE,
                )

    def test_command_rejects_stale_source_extra_input_and_wrong_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = accepted_policy(Path(temp_dir))
            stale = command(policy)
            stale["subject"]["expected_source_version"] = "d" * 40
            stale["intent_digest"] = provider.canonical_digest(provider.command_intent(stale))
            stale["approval"]["intent_digest"] = stale["intent_digest"]
            with self.assertRaisesRegex(provider.ProviderError, "stale or invalid"):
                provider.validate_command(stale, policy, SOURCE)
            with self.assertRaisesRegex(provider.ProviderError, "no caller-selected input"):
                provider.validate_command(command(policy, input_value={"shell": "id"}), policy, SOURCE)
            invalid = command(policy)
            invalid["approval"]["operator_id"] = "operator:other"
            with self.assertRaisesRegex(provider.ProviderError, "exact operator approval"):
                provider.validate_command(invalid, policy, SOURCE)

    def test_submit_replays_exact_command_and_rejects_conflicting_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy = accepted_policy(root)
            policy_path = root / "policy.yaml"
            policy_path.write_text("schema_version: 1\n", encoding="utf-8")
            service = provider.ProviderService(
                policy,
                policy_path,
                provider.OperationStore(root / "state"),
                SOURCE,
            )
            exact = command(policy)
            with patch.object(provider, "spawn_worker"):
                first_status, first = service.submit({"command": exact})
                replay_status, replay = service.submit({"command": exact})
                conflict = json.loads(json.dumps(exact))
                conflict["requested_at"] = "2026-10-15T00:00:02Z"
                conflict["intent_digest"] = provider.canonical_digest(provider.command_intent(conflict))
                conflict["approval"]["intent_digest"] = conflict["intent_digest"]
                with self.assertRaisesRegex(provider.ProviderError, "another intent"):
                    service.submit({"command": conflict})
            self.assertEqual(first_status, 202)
            self.assertEqual(replay_status, 200)
            self.assertEqual(first["operation_id"], replay["operation_id"])

    def test_worker_records_truthful_success_and_failure_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy = accepted_policy(root)
            store = provider.OperationStore(root / "state")
            for index, return_code in enumerate((0, 7), start=1):
                exact = command(policy)
                exact["command_id"] = f"command:accepted-idea-delivery:status:{index}"
                exact["idempotency_key"] = f"idempotency:accepted-idea-delivery:status:{index}"
                exact["intent_digest"] = provider.canonical_digest(provider.command_intent(exact))
                exact["approval"]["intent_digest"] = exact["intent_digest"]
                record = provider.new_record(exact, SOURCE)
                store.write(record)
                completed = provider.subprocess.CompletedProcess([], return_code)
                with patch.object(provider.subprocess, "run", return_value=completed):
                    provider.execute_worker(store, policy, exact["command_id"])
                result = store.read(exact["command_id"])
                assert result
                expected = "succeeded" if return_code == 0 else "failed"
                self.assertEqual(result["state"], expected)
                self.assertEqual(result["receipt"]["outcome"], expected)
                self.assertEqual(result["receipt"]["effect"], "verified" if return_code == 0 else "none")

    def test_runner_mapping_has_no_caller_selected_command_or_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = accepted_policy(Path(temp_dir))
            start = provider.runner_command("dev-integration.start", policy)
            smoke = provider.runner_command("dev-integration.smoke", policy)
        self.assertTrue(start[1].endswith("console_complete_runtime.py"))
        self.assertEqual(start[2:], ["activate"])
        self.assertIn("accepted-idea-delivery", smoke)
        self.assertNotIn("shell", " ".join(start + smoke))

    def test_control_contract_rejects_wrong_operator_and_extra_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy = accepted_policy(root)
            store = provider.OperationStore(root / "state")
            service = provider.ProviderService(policy, root / "policy.yaml", store, SOURCE)
            exact = command(policy)
            record = provider.new_record(exact, SOURCE)
            record["state"] = "failed"
            record["retryable"] = True
            record["cancel_available"] = False
            record["failure"] = {"code": "failed", "detail": "failed", "owner": "platform-engineering"}
            record["receipt"] = provider.terminal_receipt(record, "failed", "none")
            provider.event(record, "failed", "failed")
            store.write(record)
            control = {
                "schema_version": 1,
                "control_id": "control:retry:1",
                "idempotency_key": "idempotency:retry:1",
                "action": "retry",
                "operator_id": "operator:other",
                "reason": "Retry after recovery.",
                "requested_at": "2026-10-15T00:00:00Z",
            }
            with self.assertRaisesRegex(provider.ProviderError, "binding is invalid"):
                service.control(record["operation_id"], {"control": control})
            control["operator_id"] = "operator:workspace-owner"
            control["extra"] = True
            with self.assertRaisesRegex(provider.ProviderError, "control is invalid"):
                service.control(record["operation_id"], {"control": control})

    def test_lost_worker_blocks_and_retries_without_killing_reused_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy = accepted_policy(root)
            store = provider.OperationStore(root / "state")
            service = provider.ProviderService(policy, root / "policy.yaml", store, SOURCE)
            exact = command(policy)
            record = provider.new_record(exact, SOURCE)
            record["worker"] = {
                "pid": 999999,
                "boot_id": "lost",
                "start_ticks": 1,
                "started_at": "2026-10-15T00:00:00Z",
            }
            provider.event(record, "running", "running")
            store.write(record)
            blocked = service.read(exact["command_id"])
            self.assertEqual(blocked["state"], "blocked")
            self.assertTrue(blocked["retryable"])
            self.assertEqual(blocked["blocker"]["code"], "platform_owner_worker_lost")
            control = {
                "schema_version": 1,
                "control_id": "control:retry:lost:1",
                "idempotency_key": "idempotency:retry:lost:1",
                "action": "retry",
                "operator_id": "operator:workspace-owner",
                "reason": "Retry after exact worker loss.",
                "requested_at": "2026-10-15T00:00:00Z",
            }
            with patch.object(provider, "spawn_worker"):
                retried = service.control(record["operation_id"], {"control": control})
            self.assertEqual(retried["state"], "queued")
            self.assertEqual(retried["attempt"], 2)

    def test_stale_activation_marker_withholds_effect_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy = accepted_policy(root)
            marker = Path(policy["runtime_state_root"]) / "active.json"
            marker.parent.mkdir(parents=True)
            marker.write_text(json.dumps({
                "schema_version": 1,
                "platform_revision": SOURCE,
                "platform_tree": provider.git_tree(),
                "security_decision_digest": "sha256:" + "0" * 64,
                "security_decision_uri": policy["security"]["decision_uri"],
                "activated_at": "2026-10-15T00:00:00Z",
            }), encoding="utf-8")
            service = provider.ProviderService(policy, root / "policy.yaml", provider.OperationStore(root / "state"), SOURCE)
            catalog = service.catalog()
            capabilities = {item["action"]: item for item in catalog["subjects"][0]["capabilities"]}
            self.assertTrue(capabilities["dev-integration.status"]["available"])
            self.assertFalse(capabilities["dev-integration.smoke"]["available"])
            self.assertFalse(capabilities["agent-source.issue"]["available"])

    def test_source_actions_never_execute_through_generic_shell_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = accepted_policy(Path(temp_dir))
            for action in provider.source_credentials.ACTION_SET:
                with self.assertRaises(provider.ProviderError):
                    provider.runner_command(action, policy)

    def test_source_worker_suppresses_sensitive_error_and_never_claims_no_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy = accepted_policy(root)
            store = provider.OperationStore(root / "state")
            exact = command(policy, action="agent-source.issue")
            record = provider.new_record(exact, SOURCE)
            store.write(record)
            with patch.object(provider, "git_head", return_value=SOURCE), patch.object(provider, "activation_is_current", return_value=True), patch.object(provider.source_credentials, "operate", side_effect=RuntimeError("synthetic-token-must-not-leak")) as issuer:
                self.assertEqual(provider.execute_worker(store, policy, exact["command_id"]), 1)
                issuer.assert_called_once()
            failed = store.read(exact["command_id"])
            self.assertEqual(failed["state"], "failed")
            self.assertEqual(failed["receipt"]["effect"], "partial")
            self.assertFalse(failed["cancel_available"])
            self.assertNotIn("synthetic-token-must-not-leak", json.dumps(failed))
            self.assertNotIn("synthetic-token-must-not-leak", "".join(p.read_text() for p in store.logs.glob("*.log")))

    def test_credential_commands_need_closed_input_and_digest_bound_approval(self) -> None:
        # Actual valid commands/HTTP/issuer are covered by test_agent_source_intent.
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = accepted_policy(Path(temp_dir))
            missing = command(policy, action="agent-source.issue", input_value={})
            missing["capability_id"] = "agent-source.issue"
            missing["intent_digest"] = provider.canonical_digest(provider.command_intent(missing))
            missing["approval"]["intent_digest"] = missing["intent_digest"]
            with self.assertRaisesRegex(provider.ProviderError, "intent binding is invalid"):
                provider.validate_command(missing, policy, SOURCE)

    def test_queued_source_revalidates_current_security_head_and_runtime_before_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy = accepted_policy(root)
            store = provider.OperationStore(root / "state")
            for index, mode in enumerate(("head", "security", "runtime")):
                exact = command(policy, action="agent-source.issue")
                exact["command_id"] = f"command:source:stale:{index}"
                exact["intent_digest"] = provider.canonical_digest(provider.command_intent(exact))
                exact["approval"]["intent_digest"] = exact["intent_digest"]
                record = provider.new_record(exact, SOURCE)
                store.write(record)
                candidate_policy = json.loads(json.dumps(policy))
                if mode == "security":
                    candidate_policy["security"]["status"] = "pending"
                with patch.object(provider, "git_head", return_value="c" * 40 if mode == "head" else SOURCE), patch.object(provider.source_credentials, "operate") as issuer:
                    self.assertEqual(provider.execute_worker(store, candidate_policy, exact["command_id"]), 1)
                    issuer.assert_not_called()
                self.assertEqual(store.read(exact["command_id"])["receipt"]["effect"], "none")


class ClosureDispositionProtocolTests(unittest.TestCase):
    def test_authenticated_owner_lookup_records_existing_proof_without_a_runtime_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = accepted_policy(root)
            service = provider.ProviderService(policy, root / "policy.yaml",
                provider.OperationStore(root / "state"), SOURCE)
            evidence = root / "platform-evidence.json"
            evidence.write_text(json.dumps({"schema_version": 1, "records": []}))
            evidence.chmod(0o600)
            lookup = {"prototype_id": "sample-tool", "merged_source_revision": "d" * 40,
                "source_event_ref": "prototype-closure:sample-tool:0002"}
            observed = {key: lookup[key] for key in ("prototype_id", "merged_source_revision")}
            observed["disposition"] = "absent"
            handler = provider.handler_for(service, "oos", "synthetic-owner-secret")
            with provider.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    target = f"http://127.0.0.1:{server.server_port}/v1/console-operations/prototype-closure-dispositions"
                    request = lambda secret: Request(target, data=json.dumps(lookup).encode(),
                        headers={"x-platform-caller-id": "oos", "x-platform-caller-secret": secret})
                    with patch.object(provider, "activation_is_current", return_value=True), \
                         patch.object(provider, "closure_evidence_path", return_value=evidence), \
                         patch.object(provider.closure_disposition, "absent", return_value=observed) as reader, \
                         patch.object(provider, "spawn_worker") as worker:
                        with self.assertRaises(HTTPError) as denied:
                            urlopen(request("wrong"), timeout=2)
                        self.assertEqual(denied.exception.code, 403)
                        reader.assert_not_called()
                        with urlopen(request("synthetic-owner-secret"), timeout=2) as response:
                            proof = json.load(response)
                        reader.assert_called_once_with(policy, lookup)
                        self.assertEqual(json.loads(evidence.read_text())["records"], [proof])
                        self.assertEqual(proof["disposition"], "absent")
                        self.assertEqual(proof["field"], "post_merge_runtime_disposition")
                        worker.assert_not_called()
                finally:
                    server.shutdown()
                    thread.join()

    def test_stale_activation_or_failed_owner_observation_never_records_a_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = accepted_policy(root)
            service = provider.ProviderService(policy, root / "policy.yaml",
                provider.OperationStore(root / "state"), SOURCE)
            with patch.object(provider, "activation_is_current", return_value=False), \
                 patch.object(provider.closure_disposition, "absent") as reader:
                with self.assertRaises(provider.ProviderError):
                    service.closure_disposition({})
                reader.assert_not_called()
            with patch.object(provider, "activation_is_current", return_value=True), \
                 patch.object(provider.closure_disposition, "absent", side_effect=ValueError("unproven")), \
                 patch.object(provider.closure_evidence, "record") as record:
                with self.assertRaises(provider.ProviderError):
                    service.closure_disposition({})
                record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
