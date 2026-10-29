"""Sandbox owner proof for revisioned model management and routed invocation.

These tests exercise private persistence, the actual HTTP handler and native
app-server subprocess transport. Synthetic providers do not claim live account
entitlement or commissioned Console operation.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone, timedelta
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import itertools
import io
import queue
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from contextlib import contextmanager
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dev-integration/profiles/governed-ai-gateway/runtime"))
from codex_adapter import CodexAdapter
from gateway_app import GatewayRuntime, Handler
from governed_ai_test_support import fixture_selections
from model_configuration import ConfigurationError, InvocationJournal, ModelConfiguration, digest
from model_management import CodexBackend, ModelManagement, OllamaBackend, PROBE_SCHEMA
from model_login import ModelLogin
from provider_accounts import VaultCodexAccount
from ollama_adapter import (ProviderCompletionUnknown, ProviderIntegrityError, ProviderOutputInvalid,
                            ProviderBusy, ProviderResult, ProviderUnavailable)


class Backend:
    def __init__(self, name, output):
        self.name, self.output, self.failure = name, output, None
        self.calls = []

    def discover(self):
        return [{"model": self.name, "supported_efforts": ["low", "high"],
                 "model_digest": None, "runtime_version": "sandbox-v1"}]

    def adapter(self, model, effort, limits):
        owner = self
        class Adapter:
            def invoke(self, **kwargs):
                owner.calls.append({"model": model["model"], "effort": effort, **kwargs})
                if owner.failure:
                    raise owner.failure("Synthetic provider outcome")
                output = {"ok": True} if kwargs["prompt_version"] == "model-registration-probe-v1" else owner.output
                return ProviderResult(output, None, "sandbox-v1", 1, {}, kwargs["prompt_version"])
        return Adapter()


class TaskRoutingTests(unittest.TestCase):
    def test_post_start_health_detects_drift_without_inference_or_configuration_mutation(self):
        class Local(OllamaBackend):
            calls = []
            def discover(inner):
                return [{"model": "local", "supported_efforts": ["low", "high"], "runtime_version": "changed-v2", "model_digest": None}]
            def metadata(inner, name): return inner.discover()[0]
            def adapter(inner, *args): raise AssertionError("health must not infer")
        self.manager.backends["local"] = Local("http://unused.invalid")
        before = self.configuration.snapshot()
        result = self.manager.refresh_health()
        local = next(row for row in result["models"] if row["model_id"] == self.ids["local"])
        self.assertEqual(local["state"], "verification-needed")
        self.assertEqual(local["observed_runtime_version"], "changed-v2")
        self.assertEqual(self.configuration.snapshot(), before)

        self.assertEqual(self.manager.describe_backends()["health"], result)
        self.assertTrue(all(not backend.calls for backend in self.backends.values()))
        self.command("routing.save", {"default": {"primary": {"model_id": self.ids["cloud"], "effort": "high"}, "fallbacks": [], "on_exhausted": "fail-closed"}, "overrides": {}})
        self.assertIsNone(self.manager.describe_backends()["health"])

    def test_new_outcome_invalidates_cache_and_rejects_an_in_progress_old_collector(self):
        result = self.manager.refresh_health()
        retained = self.configuration.outcomes()
        model = self.configuration.snapshot()["configuration"]["models"][self.ids["cloud"]]
        self.configuration.record_outcome(model, "provider-completion-unknown", "ai-routing-selection:" + "a" * 64)
        self.assertIsNone(self.manager.describe_backends()["health"])
        self.assertFalse(self.configuration.cache_health(result, retained))
        self.assertIsNone(self.manager.describe_backends()["health"])

    def test_provider_loss_is_health_evidence_not_a_management_failure(self):
        class Offline(OllamaBackend):
            calls = []
            def discover(inner): raise ProviderUnavailable("private error text")
        self.manager.backends["local"] = Offline("http://unused.invalid")
        result = self.manager.refresh_health()
        self.assertEqual(next(row for row in result["backends"] if row["backend_id"] == "local")["state"], "unavailable")
        self.assertNotIn("private error", json.dumps(result))
        self.assertEqual(self.manager.describe_backends()["health"], result)
        self.assertTrue(all(not backend.calls for backend in self.backends.values()))

    def test_post_start_native_connection_is_not_model_entitlement_and_never_infers(self):
        @contextmanager
        def projected(**kwargs):
            self.assertTrue(kwargs["allow_missing"])
            yield self.root, lambda raw: self.fail("routine check must not persist credentials")
        account = SimpleNamespace(project=projected)
        self.manager.backends["cloud"] = CodexBackend(executable=Path("/never-execute"), executable_digest="0"*64, account=account)
        class Protocol:
            account_path = self.root / "no-native-refresh"
            def __init__(inner, **kwargs): pass
            def initialize(inner, deadline): pass
            def connection(inner, deadline): pass
            def models(inner, deadline):
                return [{"model": "cloud", "supported_efforts": ["low", "high"],
                         "model_digest": None, "runtime_version": "sandbox-v1"}]
            def close(inner): pass
            def turn(inner, **kwargs): self.fail("health must not infer")
        with patch("model_management.CodexProtocol", Protocol):
            result = self.manager.refresh_health()
            self.assertEqual(next(row for row in result["backends"] if row["backend_id"] == "cloud")["code"], "account-sign-in-required")
            (self.root / "auth.json").write_text("synthetic presence")
            (self.configuration.root / "health.json").unlink()
            result = self.manager.refresh_health()
            self.assertEqual(next(row for row in result["backends"] if row["backend_id"] == "cloud")["code"], "connection-verified")
            # Existing timestamped registration is evidence, not the catalogue.
            model = next(row for row in result["models"] if row["model_id"] == self.ids["cloud"])
            self.assertEqual(model["code"], "recent-model-success")
            self.assertEqual(model["last_success"]["kind"], "verification")
            later = self.manager.refresh_health(now=datetime.now(timezone.utc) + timedelta(minutes=16))
            stale = next(row for row in later["models"] if row["model_id"] == self.ids["cloud"])
            self.assertEqual(stale["code"], "model-verification-required")
            self.assertIsNotNone(stale["last_success"])
            (self.configuration.root / "health.json").unlink()
            registered = self.configuration.snapshot()["configuration"]["models"][self.ids["cloud"]]
            self.configuration.record_outcome(registered, "provider-completion-unknown", "ai-routing-selection:" + "a" * 64)
            failed = self.manager.refresh_health()
            failed = next(row for row in failed["models"] if row["model_id"] == self.ids["cloud"])
            self.assertEqual(failed["code"], "last-request-failed")
            self.assertIsNotNone(failed["last_success"])
            state = json.loads(self.configuration.path.read_text())
            state.pop("provider_outcomes")
            self.configuration.path.write_text(json.dumps(state))
            (self.configuration.root / "health.json").unlink()
            result = self.manager.refresh_health()
            model = next(row for row in result["models"] if row["model_id"] == self.ids["cloud"])
            self.assertEqual(model["code"], "model-verification-required")
            self.assertIsNone(model["last_success"])

    def test_outcome_binding_freshness_and_failure_precedence_preserve_configuration(self):
        model_id = self.ids["cloud"]
        model = self.configuration.snapshot()["configuration"]["models"][model_id]
        before = self.configuration.snapshot()
        reference = "ai-routing-selection:" + "a" * 64
        self.configuration.record_outcome(model, "suggestion-produced", reference, "account-one")
        outcome = self.configuration.outcome(model_id, model, "account-one")
        self.assertEqual(outcome["last_success"]["reference"], reference)
        self.assertIsNone(self.configuration.outcome(model_id, model, "account-two"))
        self.configuration.record_outcome(model, "provider-completion-unknown", reference, "account-one")
        outcome = self.configuration.outcome(model_id, model, "account-one")
        self.assertEqual(outcome["code"], "provider-completion-unknown")
        self.assertEqual(outcome["last_success"]["reference"], reference)
        changed = {**model, "runtime_version": "changed"}
        self.assertIsNone(self.configuration.outcome(model_id, changed, "account-one"))
        self.assertEqual(self.configuration.snapshot(), before)

    def test_request_success_is_captured_once_from_actual_dispatch_not_replay(self):
        self.save(self.route("cloud"))
        request = self.request
        self.runtime.invoke(request)
        model = self.configuration.snapshot()["configuration"]["models"][self.ids["cloud"]]
        first = self.configuration.outcome(self.ids["cloud"], model)
        self.assertEqual(first["last_success"]["kind"], "request")
        self.runtime.invoke(request)
        self.assertEqual(self.configuration.outcome(self.ids["cloud"], model), first)

    def test_failed_verification_retains_registration_but_supersedes_old_success(self):
        before = self.configuration.snapshot()
        model = before["configuration"]["models"][self.ids["cloud"]]
        self.backends["cloud"].failure = ProviderUnavailable
        with self.assertRaises(ProviderUnavailable):
            self.command("model.register", {"backend_id": "cloud", "model": "cloud"})
        self.assertEqual(self.configuration.snapshot(), before)
        outcome = self.configuration.outcome(self.ids["cloud"], model)
        self.assertEqual(outcome["code"], "provider-unavailable")
        self.assertEqual(outcome["last_success"]["kind"], "verification")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.commands = itertools.count()
        self.selections = fixture_selections()
        self.tasks = {profile_id + "/" + kind for profile_id, profile in self.selections["profiles"].items()
                      for kind in profile["task_contracts"]}
        self.policy = {name: {"allowed_tasks": sorted(self.tasks)} for name in ["cloud", "local"]}
        output = {"suggested_decision": "proposed", "confidence": "low"}
        self.backends = {name: Backend(name, copy.deepcopy(output)) for name in self.policy}
        self.configuration = ModelConfiguration(self.root / "config", tasks=self.tasks, backends=self.policy)
        self.token = self.root / "management-token"
        self.token.write_text("synthetic-test-token")
        self.manager = ModelManagement(configuration=self.configuration, backends=self.backends,
                                       authority={"token_file": str(self.token), "caller_id": "owner", "operator_id": "operator:test"})
        self.ids = {}
        for name in self.backends:
            self.command("backend.register", {"backend_id": name})
            self.command("model.register", {"backend_id": name, "model": name})
            self.ids[name] = digest({"backend_id": name, "model": name})
        for backend in self.backends.values():
            backend.calls.clear()
        self.runtime = GatewayRuntime(selections=self.selections, audit_root=self.root / "audit",
                                       compatibility_profile_id="intake-classifier-v1", management=self.manager)
        profile_id, caller = "intake-classifier-v1", "workspace-governance/intake-assist"
        self.request = {"profile_id": profile_id,
                        "caller_identity": {"caller_id": caller, "caller_repo": "workspace-governance",
                                            "caller_workflow": "intake-assist", "decision_or_correlation_id": "invocation:1",
                                            "requested_profile_id": profile_id},
                        "operator_identity": {"operator_id": "operator:test"},
                        "provider_output_schema_ref": self.selections["profiles"][profile_id]["provider_output_schema_ref"],
                        "input": {"operator_supplied_intake_notes": "Synthetic entrant context"},
                        "selection_evidence_version": 1}

    def command(self, action, payload, command_id=None, expected=None, actor="operator:test"):
        revision = self.configuration.snapshot()["revision"]
        command = {"command_id": command_id or f"command:{next(self.commands)}:{action}",
                   "expected_revision": revision if expected is None else expected, "action": action, "input": payload}
        return self.manager.command(command, actor=actor)

    def route(self, primary="cloud", fallbacks=None, effort="high"):
        return {"primary": {"model_id": self.ids[primary], "effort": effort},
                "fallbacks": [{"model_id": self.ids[name], "effort": "low"} for name in (fallbacks or [])],
                "on_exhausted": "fail-closed"}

    def save(self, route):
        return self.command("routing.save", {"default": route, "overrides": {}})

    def test_compare_and_swap_and_receipt_replay_preserve_original_revision(self):
        original = self.configuration.snapshot()["revision"]
        payload = {"default": self.route(), "overrides": {}}
        first = self.command("routing.save", payload, command_id="original", expected=original)
        self.save(self.route("local"))
        self.assertEqual(first, self.command("routing.save", payload, command_id="original", expected=original))
        for actor, data in [("operator:other", payload), ("operator:test", {"default": None, "overrides": {}})]:
            with self.assertRaisesRegex(ConfigurationError, "identity"):
                self.command("routing.save", data, command_id="original", expected=original, actor=actor)
        with self.assertRaisesRegex(ConfigurationError, "Refresh"):
            self.command("routing.save", payload, command_id="stale", expected=original)

    def test_concurrent_edits_have_exactly_one_winner(self):
        revision = self.configuration.snapshot()["revision"]
        barrier, outcomes = threading.Barrier(2), []
        def edit(name):
            barrier.wait()
            try:
                outcomes.append(self.command("routing.save", {"default": self.route(name), "overrides": {}},
                                             command_id=name, expected=revision)["revision"])
            except ConfigurationError as error:
                outcomes.append(error.code)
        threads = [threading.Thread(target=edit, args=(name,)) for name in self.backends]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertCountEqual(outcomes, [revision + 1, "revision-conflict"])

    def test_registration_replay_does_not_probe_the_model_again(self):
        original = self.command("model.register", {"backend_id": "cloud", "model": "cloud"}, command_id="register-again")
        calls = len(self.backends["cloud"].calls)
        replay = self.command("model.register", {"backend_id": "cloud", "model": "cloud"}, command_id="register-again",
                              expected=original["previous_revision"])
        self.assertEqual(replay, original)
        self.assertEqual(len(self.backends["cloud"].calls), calls)

    def test_unsupported_effort_task_and_model_permissions_are_rejected(self):
        for mutate in [lambda x: x["primary"].update(effort="ultra"),
                       lambda x: x["primary"].update(model_id="unregistered")]:
            route = self.route(); mutate(route)
            with self.assertRaises(ConfigurationError): self.save(route)
        self.configuration.backends["cloud"]["allowed_tasks"] = []
        with self.assertRaisesRegex(ConfigurationError, "data scope"):
            self.save(self.route())
        self.assertFalse(self.backends["cloud"].calls)

    def test_default_override_and_ordered_availability_fallback(self):
        self.save(self.route("cloud", ["local"]))
        self.backends["cloud"].failure = ProviderUnavailable
        status, result = self.runtime.invoke(self.request)
        self.assertEqual(status, 200)
        evidence = result["effective_selection"]
        self.assertEqual([x["backend_id"] for x in evidence["attempts"]], ["cloud", "local"])
        self.assertEqual(self.backends["cloud"].calls[0]["effort"], "high")
        self.assertEqual(self.backends["local"].calls[0]["effort"], "low")
        self.assertEqual(result["suggested_decision"], "proposed")
        self.assertIsNone(self.runtime.latest_audit_event()["latest"]["upstream_model_digest"])

    def test_real_account_mutex_uses_explicit_fallback_and_preserves_original_result(self):
        self.token.chmod(0o600)
        retained = {"data": {"data": {"account": {
            "auth_mode": "chatgpt", "tokens": {"access_token": "synthetic-only"},
        }}, "metadata": {"version": 1}}}
        account = VaultCodexAccount(address="http://127.0.0.1:8200", mount="secret",
            path="synthetic/account", token_file=self.token,
            runtime_root=self.root / "native-account",
            opener=lambda *_args, **_kwargs: io.BytesIO(json.dumps(retained).encode()))
        self.backends["cloud"] = CodexBackend(executable=self.root / "must-not-start",
            executable_digest="0" * 64, account=account)
        self.save(self.route("cloud", ["local"]))
        # Exercise the actual account projection and flock, not an injected busy
        # response. The second invocation has its own free journal identity.
        with account.project():
            status, original = self.runtime.invoke(self.request)
            self.assertEqual(status, 200, original)
            self.assertEqual([a["outcome"] for a in original["effective_selection"]["attempts"]],
                             ["provider-busy", "suggestion-produced"])
            self.assertEqual(len(self.backends["local"].calls), 1)
            self.save({"primary": {"model_id": self.ids["cloud"], "effort": "high"}, "fallbacks": [], "on_exhausted": "fail-closed"})
            no_fallback = copy.deepcopy(self.request)
            no_fallback["caller_identity"]["decision_or_correlation_id"] = "invocation:no-fallback"
            status, denied = self.runtime.invoke(no_fallback)
            self.assertEqual(status, 503, denied)
            self.assertEqual(denied["reasons"], ["no-suitable-fallback"])
            self.assertEqual([a["outcome"] for a in denied["effective_selection"]["attempts"]],
                             ["provider-busy"])
        # Releasing the account and changing settings cannot dispatch the old
        # request again or replace its original frozen fallback result.
        status, replay = self.runtime.invoke(self.request)
        self.assertEqual((status, replay), (200, original))
        self.assertEqual(len(self.backends["local"].calls), 1)

    def test_two_actual_profile_contracts_use_default_and_task_override(self):
        self.command("routing.save", {"default": self.route("cloud", effort="high"), "overrides": {
            "agent-console-assistant-v1/assistant_response": self.route("local", effort="low")}})
        self.assertEqual(self.runtime.invoke(self.request)[0], 200)
        self.backends["local"].output = {"text": "Synthetic bounded agent response"}
        profile = self.selections["profiles"]["agent-console-assistant-v1"]
        task = profile["task_contracts"]["assistant_response"]
        request = {"profile_id": profile["profile_id"], "caller_identity": {
            "caller_id": "operator-orchestration-service/agent-console", "caller_repo": "operator-orchestration-service",
            "caller_workflow": "agent-console", "decision_or_correlation_id": "invocation:agent", "requested_profile_id": profile["profile_id"]},
            "operator_identity": {"operator_id": "operator:test"}, "task": {
                "kind": "assistant_response", "contract_ref": task["contract_ref"], "version": task["contract_version"]},
            "provider_output_schema_ref": task["provider_output_schema_ref"], "selection_evidence_version": 1,
            "input": {"interaction_mode": "reason", "operator_prompt": "Synthetic bounded prompt",
                      "task_instruction": "Return bounded advice without actions", "session_binding": {"session_id": "synthetic-agent-session"},
                      "model_safe_packet": {key: "synthetic-receipt-bound-value" for key in task["input_contract"]["model_safe_packet_required_fields"]}}}
        status, result = self.runtime.invoke(request)
        self.assertEqual(status, 200)
        self.assertEqual(result["output"], self.backends["local"].output)
        self.assertEqual(self.backends["cloud"].calls[0]["effort"], "high")
        self.assertEqual(self.backends["local"].calls[0]["effort"], "low")
        self.assertEqual(result["effective_selection"]["task"], "agent-console-assistant-v1/assistant_response")

    def test_registry_cleanup_and_history_are_available_without_source_changes(self):
        initial = self.configuration.snapshot()
        self.save(self.route())
        self.assertEqual(self.configuration.snapshot(initial["revision"])["configuration"], initial["configuration"])
        with self.assertRaises(ConfigurationError):
            self.command("backend.remove", {"backend_id": "cloud"})
        with self.assertRaises(ConfigurationError):
            self.command("model.remove", {"model_id": self.ids["cloud"]})
        self.save(None)
        self.command("model.remove", {"model_id": self.ids["cloud"]})
        self.command("backend.remove", {"backend_id": "cloud"})
        self.assertNotIn("cloud", self.configuration.snapshot()["configuration"]["backends"])
        for _ in range(4): self.save(None)
        revisions = [item["revision"] for item in self.configuration.snapshot()["history"]]
        self.assertEqual(revisions, sorted(revisions))

    def test_management_stays_reachable_without_claiming_provider_health(self):
        class Unavailable:
            def verify_binding(self): raise ProviderUnavailable("Synthetic outage")
        self.runtime.adapters = {key: Unavailable() for key in self.runtime.profiles}
        readiness = self.runtime.readiness()
        self.assertTrue(readiness["ready"])
        self.assertTrue(readiness["model_management"]["ready"])
        self.assertEqual(readiness["ready_profile_ids"], [])
        self.assertTrue(all(not backend.calls for backend in self.backends.values()))

    def test_policy_and_context_denial_never_reach_a_provider(self):
        self.save(self.route())
        for mutate in [lambda x: x["caller_identity"].update(caller_id="unknown/workflow"),
                       lambda x: x["input"].update(raw_context="unadmitted"),
                       lambda x: x.update(provider_output_schema_ref="wrong-schema")]:
            request = copy.deepcopy(self.request); mutate(request)
            self.assertEqual(self.runtime.invoke(request)[0], 403)
        self.assertTrue(all(not backend.calls for backend in self.backends.values()))

    def test_unknown_completion_invalid_output_and_integrity_do_not_fall_back(self):
        self.save(self.route("cloud", ["local"]))
        for index, failure in enumerate([ProviderCompletionUnknown, ProviderOutputInvalid, ProviderIntegrityError]):
            self.backends["cloud"].failure = failure
            request = copy.deepcopy(self.request)
            request["caller_identity"]["decision_or_correlation_id"] = f"invocation:{index}"
            self.assertEqual(self.runtime.invoke(request)[0], 503)
        self.assertFalse(self.backends["local"].calls)

    def test_actual_output_schema_is_revalidated_for_every_adapter(self):
        self.save(self.route("cloud", ["local"]))
        self.backends["cloud"].output = {"confidence": "high", "suggested_decision": "admitted", "authority": "forged"}
        status, result = self.runtime.invoke(self.request)
        self.assertEqual((status, result["reasons"]), (503, ["provider-output-invalid"]))
        self.assertFalse(self.backends["local"].calls)

    def test_result_replay_survives_restart_and_cleared_routing_without_inference(self):
        self.save(self.route())
        first = self.runtime.invoke(self.request)
        self.save(None)
        restarted = GatewayRuntime(selections=self.selections, audit_root=self.root / "audit",
                                    compatibility_profile_id="intake-classifier-v1", management=self.manager)
        self.assertEqual(tuple(restarted.invoke(self.request)), first)
        self.assertEqual(len(self.backends["cloud"].calls), 1)
        self.request["input"]["operator_supplied_intake_notes"] = "Changed content"
        self.assertEqual(restarted.invoke(self.request)[0], 409)

    def test_pending_after_process_loss_does_not_launch_another_attempt(self):
        self.save(self.route())
        profile = self.selections["profiles"]["intake-classifier-v1"]
        task = profile["task_contracts"]["intake_classification"]
        identity = {"caller": self.request["caller_identity"]["caller_id"], "operator": "operator:test",
                    "profile": profile["profile_id"], "task": task["task_kind"], "invocation": "invocation:1"}
        selection = self.configuration.selection(self.configuration.snapshot(), profile["profile_id"] + "/" + task["task_kind"])
        with InvocationJournal(self.root / "audit/invocations").invocation(identity, digest(self.request), selection):
            pass  # Simulated process exit after durable pending, before completion.
        status, result = self.runtime.invoke(self.request)
        self.assertEqual((status, result["reasons"]), (503, ["provider-completion-unknown"]))
        self.assertFalse(self.backends["cloud"].calls)

    def test_rollback_is_a_new_revision_and_rechecks_current_permissions(self):
        chosen = self.save(self.route())
        self.save(self.route("local"))
        rollback = self.command("routing.rollback", {"revision": chosen["revision"]})
        self.assertGreater(rollback["revision"], chosen["revision"])
        self.assertEqual(self.configuration.snapshot()["configuration"]["default"], self.route())
        self.configuration.backends["cloud"]["allowed_tasks"] = []
        with self.assertRaises(ConfigurationError):
            self.command("routing.rollback", {"revision": chosen["revision"]})
        # The current journal remains readable and a safe repair is possible.
        self.save(self.route("local"))

    def test_http_management_requires_owner_token_caller_and_operator(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.runtime = self.runtime
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_port}/v1/model-management/configuration"
        for headers in [{}, {"Authorization": "Bearer synthetic-test-token"},
                        {"Authorization": "Bearer synthetic-test-token", "X-Platform-Caller": "owner", "X-Platform-Operator": "operator:wrong"}]:
            with self.assertRaises(urllib.error.HTTPError) as failure:
                urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=2)
            self.assertEqual(failure.exception.code, 403)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": "Bearer synthetic-test-token",
                "X-Platform-Caller": "owner", "X-Platform-Operator": "operator:test"}), timeout=2) as response:
            self.assertEqual(json.load(response)["revision"], self.configuration.snapshot()["revision"])


class CodexTransportTests(unittest.TestCase):
    def test_account_entry_busy_mapping_never_catches_an_error_after_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for failure_phase in ("dispatch", "projection-exit"):
                calls = []
                @contextmanager
                def projection():
                    yield root, lambda _raw: None
                    if failure_phase == "projection-exit":
                        raise BlockingIOError("Synthetic account exit after dispatch")
                class Adapter:
                    def __init__(self, **_kwargs): pass
                    def invoke(self, **_kwargs):
                        calls.append("dispatched")
                        if failure_phase == "dispatch":
                            raise BlockingIOError("Synthetic failure after dispatch")
                        return ProviderResult({"ok": True}, None, "sandbox-v1", 1, {}, "test")
                backend = CodexBackend(executable=root / "unused", executable_digest="0" * 64,
                    account=SimpleNamespace(project=projection))
                with self.subTest(failure_phase=failure_phase), patch("model_management.CodexAdapter", Adapter):
                    with self.assertRaises(BlockingIOError):
                        backend.adapter({"model": "synthetic"}, "high", {"timeout_seconds": 1}).invoke(
                            input_payload={}, output_schema={}, prompt_version="synthetic", system_prompt="synthetic")
                    self.assertEqual(calls, ["dispatched"])

    def test_post_completion_account_failure_cannot_be_classified_as_fallback_availability(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            account = root / "auth.json"; account.write_text('{"synthetic":true}')
            turns = []
            class Protocol:
                def __init__(self, **kwargs): self.account_path = account
                def initialize(self, deadline): pass
                def models(self, deadline): return [{"model": "synthetic", "supported_efforts": ["low"], "runtime_version": "sandbox"}]
                def turn(self, **kwargs): turns.append(kwargs); return {"ok": True}
                def close(self): pass
            def fail_custody(raw): raise ProviderUnavailable("Synthetic post-completion Vault failure")
            adapter = CodexAdapter(executable=root / "unused", executable_digest="0" * 64,
                                   home=root, model="synthetic", effort="low", protocol_factory=Protocol, account_sink=fail_custody)
            with self.assertRaises(ProviderIntegrityError) as error:
                adapter.invoke(input_payload={}, output_schema=PROBE_SCHEMA, system_prompt="Synthetic", prompt_version="test")
            self.assertEqual(len(turns), 1)
            self.assertEqual(error.exception.code, "provider-integrity-failed")
            self.assertNotIsInstance(error.exception, ProviderUnavailable)

    def test_real_subprocess_uses_isolated_home_native_effort_and_strict_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); home = root / "account"; home.mkdir()
            executable = root / "sandbox-codex"
            executable.write_text('''#!/usr/bin/python3
import json, os, sys
def emit(x): print(json.dumps(x), flush=True)
for line in sys.stdin:
 x=json.loads(line); method=x.get('method'); p=x.get('params',{})
 if method=='initialize': emit({'id':x['id'],'result':{'userAgent':'sandbox-codex/1'}})
 elif method=='model/list': emit({'id':x['id'],'result':{'data':[{'model':'cloud','supportedReasoningEfforts':[{'reasoningEffort':'high'}]}],'nextCursor':None}})
 elif method=='thread/start':
  assert p['sandbox']=='read-only' and p['ephemeral'] and p['approvalPolicy']=='never'
  assert not p['config']['features.shell_tool'] and p['config']['web_search']=='disabled'
  assert os.environ['HOME'] != '/home/mfshaf7' and 'OPENAI_API_KEY' not in os.environ
  emit({'id':x['id'],'result':{'thread':{'id':'thread:synthetic'},'model':p['model'],'cwd':p['cwd'],'approvalPolicy':'never','modelProvider':'openai','sandbox':{'type':'readOnly','networkAccess':False}}})
 elif method=='turn/start':
  assert p['effort']=='high' and p['model']=='cloud' and p['outputSchema']['additionalProperties']==False
  mode=json.loads(p['input'][0]['text']).get('mode')
  if mode=='unknown': sys.exit(0)
  if mode=='tool':
   emit({'id':999,'method':'item/commandExecution/requestApproval','params':{}})
   continue
  emit({'id':x['id'],'result':{'turn':{'id':'turn:synthetic'}}})
  emit({'method':'item/completed','params':{'threadId':'thread:synthetic','turnId':'turn:synthetic','item':{'type':'agentMessage','text':'{"ok":false}' if mode=='invalid' else '{"ok":true}'}}})
  emit({'method':'turn/completed','params':{'threadId':'thread:other' if mode=='wrong-thread' else 'thread:synthetic','turn':{'id':'turn:synthetic','status':'completed'}}})
''')
            executable.chmod(0o700)
            adapter = CodexAdapter(executable=executable, executable_digest=hashlib.sha256(executable.read_bytes()).hexdigest(),
                                   home=home, model="cloud", effort="high", timeout_seconds=3)
            result = adapter.invoke(input_payload={"synthetic": True}, system_prompt="Synthetic transport test", prompt_version="test",
                                    output_schema={"type": "object", "properties": {"ok": {"type": "boolean", "const": True}},
                                                   "required": ["ok"], "additionalProperties": False})
            self.assertEqual(result.output, {"ok": True})
            self.assertIsNone(result.model_digest)
            self.assertEqual(result.runtime_version, "sandbox-codex/1")
            for mode, error in [("tool", ProviderIntegrityError), ("invalid", ProviderOutputInvalid),
                                ("wrong-thread", ProviderIntegrityError), ("unknown", ProviderCompletionUnknown)]:
                with self.subTest(mode=mode), self.assertRaises(error):
                    adapter.invoke(input_payload={"mode": mode}, system_prompt="Synthetic transport test", prompt_version="test",
                                   output_schema={"type": "object", "properties": {"ok": {"type": "boolean", "const": True}},
                                                  "required": ["ok"], "additionalProperties": False})
            with self.assertRaises(ProviderIntegrityError):
                bad = CodexAdapter(executable=executable, executable_digest="0" * 64, home=home, model="cloud", effort="high")
                bad.invoke(input_payload={}, output_schema={}, system_prompt="", prompt_version="test")


class ProviderAccountTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        token = self.root / "vault-token"; token.write_text("synthetic-vault-token"); token.chmod(0o600)
        self.version, self.value = 0, None
        def opener(request, timeout):
            self.assertEqual(request.get_header("X-vault-token"), "synthetic-vault-token")
            self.assertEqual(timeout, 8)
            if request.data is not None:
                payload = json.loads(request.data)
                if payload["options"]["cas"] != self.version:
                    raise urllib.error.HTTPError(request.full_url, 400, "CAS conflict", {}, io.BytesIO())
                self.version += 1; self.value = payload["data"]
                result = {"data": {"version": self.version}}
            elif self.value is None:
                raise urllib.error.HTTPError(request.full_url, 404, "Missing", {}, io.BytesIO())
            else:
                result = {"data": {"data": self.value, "metadata": {"version": self.version}}}
            return io.BytesIO(json.dumps(result).encode())
        self.account = VaultCodexAccount(address="http://127.0.0.1:8200", mount="secret", path="components/governed-ai-gateway/codex",
                                          token_file=token, runtime_root=self.root / "runtime", opener=opener)
        self.raw = json.dumps({"auth_mode": "chatgpt", "tokens": {"access_token": "synthetic-account-token"}}).encode()

    def test_account_is_private_ephemeral_vault_custodied_and_cas_bound(self):
        with self.account.project(allow_missing=True, login_command_id="login:original") as (home, persist):
            self.assertEqual(list(home.iterdir()), [])
            persist(self.raw)
            path = home
        self.assertFalse(path.exists())
        self.assertTrue(self.account.completed_login("login:original"))
        self.assertFalse(self.account.completed_login("login:other"))
        with self.account.project() as (home, persist):
            self.assertEqual((home / "auth.json").stat().st_mode & 0o777, 0o600)
            self.version += 1  # Another accepted owner update wins first.
            changed = json.dumps({"auth_mode": "chatgpt", "tokens": {"access_token": "different-synthetic-token"}}).encode()
            with self.assertRaises(ProviderUnavailable): persist(changed)
        self.assertEqual(self.value["account"]["tokens"]["access_token"], "synthetic-account-token")
        with self.assertRaises(ProviderIntegrityError):
            self.account.validate_account(b'{"auth_mode":"apikey","OPENAI_API_KEY":"synthetic"}')

    def login_service(self, complete=True):
        account, raw = self.account, self.raw
        class Protocol:
            def __init__(self, home, **kwargs):
                self.account_path = home / "native-auth.json"
                self.messages = queue.Queue(); self.next_id = 3
            def initialize(self, deadline): pass
            def request(self, method, params, deadline):
                if complete:
                    self.account_path.write_bytes(raw)
                    self.messages.put({"method": "account/login/completed", "params": {"loginId": "native-login", "success": True}})
                return {"type": "chatgptDeviceCode", "loginId": "native-login", "userCode": "SYNTHETIC-CODE",
                        "verificationUrl": "https://auth.openai.com/codex/device"}
            def send(self, request): pass
            def close(self): pass
        backend = SimpleNamespace(account=account, executable=Path("/synthetic/pinned/codex"), executable_digest="0" * 64)
        return ModelLogin(self.root / "logins", {"codex": backend}, protocol_factory=Protocol)

    def wait_login(self, service, target):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            result = service.read(command_id="login:original", actor="operator:test")
            if result["state"] == target and (target not in {"connected", "cancelled"} or not service.active):
                return result
            threading.Event().wait(0.01)
        self.fail(f"Login did not reach {target}")

    def test_native_login_receipt_has_no_provider_credentials_and_replays_once(self):
        service = self.login_service()
        service.start(command_id="login:original", backend_id="codex", actor="operator:test")
        result = self.wait_login(service, "connected")
        self.assertNotIn("synthetic-account-token", json.dumps(result))
        self.assertIsNone(result["user_code"])
        self.assertEqual(service.start(command_id="login:original", backend_id="codex", actor="operator:test"), result)
        self.assertEqual(self.version, 1)
        with self.assertRaises(ConfigurationError):
            service.read(command_id="login:original", actor="operator:other")

    def test_cancel_does_not_persist_account_or_restart_the_original_login(self):
        service = self.login_service(complete=False)
        service.start(command_id="login:original", backend_id="codex", actor="operator:test")
        self.wait_login(service, "waiting-for-operator")
        with self.assertRaises(ConfigurationError):
            service.start(command_id="login:second", backend_id="codex", actor="operator:test")
        service.cancel(command_id="login:original", actor="operator:test")
        result = self.wait_login(service, "cancelled")
        self.assertIsNone(self.value)
        self.assertEqual(service.start(command_id="login:original", backend_id="codex", actor="operator:test"), result)

    def test_interrupted_login_reconciles_only_matching_vault_provenance(self):
        service = self.login_service()
        path, _ = service._paths("login:original")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"command_id": "login:original", "backend_id": "codex", "actor": "operator:test",
                                    "state": "waiting-for-operator", "verification_url": "https://auth.openai.com/codex/device",
                                    "user_code": "OLD-CODE", "failure": None}))
        result = service.read(command_id="login:original", actor="operator:test")
        self.assertEqual(result["state"], "interrupted")
        self.assertIsNone(result["verification_url"])


class OllamaNativeControlsTests(unittest.TestCase):
    def test_real_http_registration_separates_inventory_and_output_budgets(self):
        state = {"inventory_padding": 5242, "output_padding": 0, "chats": 0}
        class Provider(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def send_json(self, value):
                raw = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                self.send_json({"version": "sandbox-runtime"} if self.path == "/api/version" else {
                    "models": [{"name": "synthetic", "digest": "synthetic-digest"}],
                    "synthetic_padding": "x" * state["inventory_padding"],
                })

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.path == "/api/show":
                    self.send_json({"thinking": {"values": [False, True]}})
                    return
                state["chats"] += 1
                assert self.path == "/api/chat" and body["think"] is False
                assert body["options"]["num_predict"] == 64 and body["keep_alive"] == 0
                self.send_json({"message": {"content": '{"ok":true}'},
                                "synthetic_padding": "x" * state["output_padding"]})

        server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            backend = OllamaBackend(f"http://127.0.0.1:{server.server_port}")
            with tempfile.TemporaryDirectory() as temporary:
                configuration = ModelConfiguration(Path(temporary), tasks={"synthetic/task"},
                    backends={"local": {"allowed_tasks": ["synthetic/task"]}})
                manager = ModelManagement(configuration=configuration, backends={"local": backend})
                manager.command({"command_id": "backend", "expected_revision": 0,
                    "action": "backend.register", "input": {"backend_id": "local"}}, actor="operator:test")
                command = {"command_id": "model", "expected_revision": 1,
                    "action": "model.register", "input": {"backend_id": "local", "model": "synthetic"}}
                registered = manager.command(command, actor="operator:test")
                self.assertEqual(configuration.snapshot()["revision"], 2)
                self.assertEqual(manager.command(command, actor="operator:test"), registered)
                self.assertEqual(state["chats"], 1, "Receipt replay must not repeat verification.")
                metadata = backend.metadata("synthetic")
                adapter = backend.adapter(metadata, False, {
                    "timeout_seconds": 2, "max_output_tokens": 64, "max_output_bytes": 4096})
                kwargs = {"input_payload": {"ok": True}, "output_schema": PROBE_SCHEMA,
                          "prompt_version": "test", "system_prompt": "Synthetic verification"}
                state["output_padding"] = 5000
                with self.assertRaisesRegex(ProviderOutputInvalid, "task byte limit"):
                    adapter.invoke(**kwargs)
                state["inventory_padding"] = 1_000_001
                with self.assertRaises(ProviderUnavailable):
                    backend.metadata("synthetic")
                self.assertEqual(state["chats"], 2, "Oversize metadata must fail before chat.")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_named_effort_is_discovered_revalidated_and_forwarded_without_trace_leak(self):
        entered, release = threading.Event(), threading.Event()
        chats = []
        def opener(request, timeout):
            if request.full_url.endswith("/api/version"):
                result = {"version": "sandbox-runtime"}
            elif request.full_url.endswith("/api/tags"):
                result = {"models": [{"name": name, "digest": name + "-digest"} for name in ["model-a", "model-b"]]}
            elif request.full_url.endswith("/api/show"):
                result = {"thinking": {"values": ["low", "high"], "default": "low"}}
            else:
                chats.append(json.loads(request.data)); entered.set()
                if not release.wait(3): raise TimeoutError()
                result = {"message": {"content": '{"ok":true}', "thinking": "Synthetic private reasoning"}}
            return io.BytesIO(json.dumps(result).encode())
        backend = OllamaBackend("http://synthetic-ollama.invalid", opener=opener)
        self.assertIsNone(backend.discover()[0]["supported_efforts"])
        a, b = backend.metadata("model-a"), backend.metadata("model-b")
        limits = {"timeout_seconds": 2, "max_output_tokens": 64}
        kwargs = {"input_payload": {"synthetic": True}, "output_schema": PROBE_SCHEMA,
                  "system_prompt": "Synthetic bounded verification", "prompt_version": "test"}
        with self.assertRaises(ProviderIntegrityError):
            backend.adapter(a, "unsupported-name", limits).invoke(**kwargs)
        result = []
        thread = threading.Thread(target=lambda: result.append(backend.adapter(a, "high", limits).invoke(**kwargs)))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaises(ProviderBusy):
                backend.adapter(b, "low", limits).invoke(**kwargs)
        finally:
            release.set(); thread.join(timeout=3)
        self.assertEqual(len(chats), 1)
        self.assertEqual(chats[0]["think"], "high")
        self.assertEqual(chats[0]["keep_alive"], 0)
        self.assertEqual(result[0].output, {"ok": True})
        self.assertNotIn("thinking", result[0].output)


if __name__ == "__main__":
    unittest.main()
