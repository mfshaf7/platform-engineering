"""Controlled native-protocol proof. No provider account/entitlement is claimed."""
from contextlib import contextmanager
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import itertools
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dev-integration/profiles/governed-ai-gateway/runtime"))
from api_provider_adapter import ApiBackend, ApiAccessDenied, ApiOutputInvalid, ApiRejected, PRESETS, claude_grammar, glm_efforts
from governed_ai_test_support import fixture_selections
from model_configuration import ConfigurationError, ModelConfiguration, digest, locked
from model_management import ModelManagement, PROBE_SCHEMA
from ollama_adapter import ProviderBusy, ProviderCompletionUnknown, ProviderIntegrityError, ProviderUnavailable
from provider_connections import ProviderConnections, VaultApiCredentials
from gateway_app import Handler


class Vault:
    def __init__(self):
        self.versions = {}
        self.fail_after_write = False
        self.fail_before_write = False

    def read(self, connection_id, version=None):
        versions = self.versions.get(connection_id, [])
        number = len(versions) if version is None else version
        return {"version": number, "data": copy.deepcopy(versions[number - 1]) if number else {}}

    def write(self, connection_id, *, previous_version, data):
        if self.fail_before_write:
            raise ProviderUnavailable("Controlled failure before write")
        versions = self.versions.setdefault(connection_id, [])
        if len(versions) != previous_version:
            raise ProviderUnavailable("Controlled CAS rejection")
        versions.append(copy.deepcopy(data))
        if self.fail_after_write:
            self.fail_after_write = False
            raise ProviderUnavailable("Controlled lost response after durable write")


def sample(schema):
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema["type"]
    kind = kind[0] if isinstance(kind, list) else kind
    if kind == "object":
        return {k: sample(schema["properties"][k]) for k in schema.get("required", [])}
    if kind == "array":
        return [sample(schema["items"]) for _ in range(schema.get("minItems", 0))]
    return {"string": "x" * max(1, schema.get("minLength", 0)), "integer": 1,
            "number": 1, "boolean": True, "null": None}[kind]


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.configuration = ModelConfiguration(self.root, tasks={"test/task"}, backends={})
        self.vault = Vault()
        self.connections = ProviderConnections(self.root, vault=self.vault, configuration=self.configuration, allowed_tasks={"test/task"})
        self.counter = itertools.count()
        self.actor = "operator:test"

    def command(self, action, payload, *, command_id=None, revision=None):
        return self.connections.command({"command_id": command_id or "command:" + str(next(self.counter)),
            "expected_revision": self.connections.snapshot()["revision"] if revision is None else revision,
            "action": action, "input": payload}, actor=self.actor)

    def create(self, provider="deepseek-api"):
        return self.command("connection.create", {"provider": provider, "name": "My API"})["connection_id"]

    def credentials(self, connection_id, command_id="key:1", key="controlled-secret-key"):
        return self.connections.credentials(command_id=command_id, expected_revision=self.connections.snapshot()["revision"],
            connection_id=connection_id, api_key=key, actor=self.actor)

    def test_named_connections_replay_revision_actor_and_presets(self):
        first = self.command("connection.create", {"provider": "claude-api", "name": "First"}, command_id="create:1", revision=0)
        self.assertEqual(first, self.command("connection.create", {"provider": "claude-api", "name": "First"}, command_id="create:1", revision=0))
        second = self.create("claude-api")
        self.assertNotEqual(first["connection_id"], second)
        snapshot = self.connections.snapshot()
        self.assertEqual(len(snapshot["presets"]), 3)
        self.assertTrue(all(x["experimental"] for x in snapshot["connections"] + snapshot["presets"]))
        self.assertTrue(all(x["qualification"] == "real-account-verification-pending" for x in snapshot["connections"]))
        with self.assertRaises(ConfigurationError):
            self.command("connection.create", {"provider": "http://caller.example", "name": "Forbidden"})
        with self.assertRaises(ConfigurationError):
            self.command("connection.create", {"provider": "claude-api", "name": "Changed"}, command_id="create:1", revision=0)
        with self.assertRaises(ConfigurationError):
            self.connections.operation("create:1", actor="operator:someone-else")
        with self.assertRaises(ConfigurationError):
            self.command("connection.create", {"provider": "glm-api", "name": "Stale"}, revision=0)

    def test_secret_write_reconciliation_after_restart_and_no_local_secret(self):
        connection_id = self.create()
        self.vault.fail_after_write = True
        revision = self.connections.snapshot()["revision"]
        with self.assertRaises(ProviderUnavailable):
            self.credentials(connection_id)
        restarted = ProviderConnections(self.root, vault=self.vault, configuration=self.configuration, allowed_tasks={"test/task"})
        with self.assertRaises(ProviderUnavailable):
            with restarted.credential(connection_id):
                self.fail("Pending credentials must not be consumed")
        result = restarted.operation("key:1", actor=self.actor, reconcile=True)
        self.assertEqual(result["state"], "finished")
        self.assertEqual(len(self.vault.versions[connection_id]), 1)
        replay = restarted.credentials(command_id="key:1", expected_revision=revision, connection_id=connection_id,
            api_key="controlled-secret-key", actor=self.actor)
        self.assertEqual(replay, result["receipt"])
        with self.assertRaises(ConfigurationError):
            restarted.credentials(command_id="key:1", expected_revision=revision, connection_id=connection_id,
                api_key="different-secret-key", actor=self.actor)
        with restarted.credential(connection_id) as (key, generation):
            self.assertEqual(key, "controlled-secret-key")
            self.assertTrue(generation.startswith("sha256:"))
        for path in self.root.rglob("*.json"):
            self.assertNotIn("controlled-secret-key", path.read_text())
            self.assertNotIn("api_key", path.read_text())

    def test_explicit_disconnect_fences_uncertain_write_and_cannot_be_undone_by_history(self):
        connection_id = self.create()
        self.vault.fail_before_write = True
        with self.assertRaises(ProviderUnavailable):
            self.credentials(connection_id)
        self.vault.fail_before_write = False
        self.command("connection.disconnect", {"connection_id": connection_id})
        self.assertEqual(self.connections.operation("key:1", actor=self.actor, reconcile=True)["state"], "cancelled")
        with self.assertRaises(ProviderUnavailable):
            self.vault.write(connection_id, previous_version=0, data={"api_key": "late-secret"})
        self.command("connection.reconnect", {"connection_id": connection_id})
        with self.assertRaises(ProviderUnavailable):
            with self.connections.credential(connection_id):
                self.fail("Reconnect must not restore a revoked key")
        self.credentials(connection_id, "key:2")
        self.configuration.command({"command_id": "rollback", "expected_revision": 0, "action": "routing.rollback", "input": {"revision": 0}}, actor=self.actor)
        self.command("connection.remove", {"connection_id": connection_id})
        self.assertEqual(self.connections.snapshot()["connections"], [])
        self.assertIsNone(self.vault.read(connection_id)["data"]["api_key"])

    def test_connection_use_blocks_rotation_but_does_not_block_status(self):
        connection_id = self.create()
        self.credentials(connection_id)
        with self.connections.credential(connection_id):
            self.assertEqual(len(self.connections.snapshot()["connections"]), 1)
            with self.assertRaises(BlockingIOError):
                self.credentials(connection_id, "key:2")
            with self.assertRaises(BlockingIOError):
                self.command("connection.disconnect", {"connection_id": connection_id})

    def test_saved_settings_cannot_restore_a_removed_connection_reference(self):
        connection_id = self.create()
        manager = ModelManagement(configuration=self.configuration, backends={}, connections=self.connections)
        self.configuration.command({"command_id": "history:register", "expected_revision": 0,
            "action": "backend.register", "input": {"backend_id": connection_id}}, actor=self.actor)
        manager.connection_command({"command_id": "history:remove", "expected_revision": 1,
            "action": "connection.remove", "input": {"connection_id": connection_id}}, actor=self.actor)
        before = self.configuration.snapshot()
        with self.assertRaises(ConfigurationError) as failure:
            self.configuration.command({"command_id": "history:restore", "expected_revision": before["revision"],
                "action": "routing.rollback", "input": {"revision": 1}}, actor=self.actor)
        self.assertEqual(failure.exception.code, "backend-not-admitted")
        self.assertEqual(self.configuration.snapshot(), before)
        self.assertIn(connection_id, self.configuration.snapshot(1)["configuration"]["backends"])
        self.assertEqual(self.connections.snapshot()["connections"], [])

    def test_native_vault_versions_cas_and_private_token_projection(self):
        token = self.root / "vault-token"; token.write_text("controlled-vault-token"); token.chmod(0o600)
        calls = []
        def opener(request, timeout):
            calls.append(request)
            self.assertEqual(request.get_header("X-vault-token"), "controlled-vault-token")
            self.assertEqual(timeout, 8)
            if request.data:
                return io.BytesIO(b'{"data":{"version":3}}')
            return io.BytesIO(b'{"data":{"metadata":{"version":2},"data":{"api_key":"controlled-native-key"}}}')
        vault = VaultApiCredentials(address="http://127.0.0.1:8200", mount="kv", prefix="approved/api", token_file=token, opener=opener)
        connection_id = "api-" + "a" * 32
        self.assertEqual(vault.read(connection_id, version=2)["version"], 2)
        self.assertTrue(calls[-1].full_url.endswith(connection_id + "?version=2"))
        vault.write(connection_id, previous_version=2, data={"operation_id": "key:test", "api_key": "controlled-native-key"})
        self.assertEqual(json.loads(calls[-1].data)["options"], {"cas": 2})
        self.assertNotIn("controlled-native-key", calls[-1].full_url)
        token.chmod(0o644)
        with self.assertRaises(ProviderUnavailable):
            vault.read(connection_id)
        token.chmod(0o600)
        def denied(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 307, "private error body", {}, io.BytesIO(b'controlled-native-key'))
        vault.opener = denied
        with self.assertRaises(ProviderUnavailable) as failure:
            vault.read(connection_id)
        self.assertNotIn("controlled-native-key", str(failure.exception))

    def test_verification_generation_and_health_are_separate_from_experimental(self):
        connection_id = self.create("glm-api")
        manager = ModelManagement(configuration=self.configuration, backends={}, connections=self.connections)
        self.credentials(connection_id)
        backend = manager.backends[connection_id]
        backend.opener = lambda request, timeout: io.BytesIO(json.dumps({"model": "glm-5.3", "choices": [{"finish_reason": "stop",
            "message": {"role": "assistant", "content": '{"ok":true}'}}]}).encode())
        def model_command(action, payload):
            return manager.command({"command_id": "model:" + str(next(self.counter)), "expected_revision": self.configuration.snapshot()["revision"],
                "action": action, "input": payload}, actor=self.actor)
        model_command("backend.register", {"backend_id": connection_id})
        model_command("model.register", {"backend_id": connection_id, "model": "glm-5.3"})
        model = next(iter(self.configuration.snapshot()["configuration"]["models"].values()))
        limits = {"timeout_seconds": 2, "max_output_tokens": 100, "max_output_bytes": 4096}
        invoke = lambda: manager.adapter(model, "low", limits).invoke(input_payload={}, output_schema=PROBE_SCHEMA,
            system_prompt="Return JSON", prompt_version="test")
        invoke()
        self.assertEqual(manager.refresh_health()["models"][0]["code"], "recent-model-success")
        self.credentials(connection_id, "key:2", "replacement-secret-key")
        self.assertIsNone(manager.health(self.configuration.snapshot()))
        with self.assertRaises(ProviderIntegrityError):
            invoke()
        with self.assertRaises(ConfigurationError):
            manager.connection_command({"command_id": "remove-in-use", "expected_revision": self.connections.snapshot()["revision"],
                "action": "connection.remove", "input": {"connection_id": connection_id}}, actor=self.actor)
        model_command("model.register", {"backend_id": connection_id, "model": "glm-5.3"})
        model = next(iter(self.configuration.snapshot()["configuration"]["models"].values()))
        invoke()
        self.assertTrue(manager.describe_backends()["backends"][0]["experimental"])

    def test_protected_http_credential_ingress_and_retained_metadata_readback(self):
        token = self.root / "management-token"; token.write_text("controlled-management-token")
        manager = ModelManagement(configuration=self.configuration, backends={}, connections=self.connections,
            authority={"token_file": str(token), "caller_id": "test-owner", "operator_id": self.actor})
        class BoundHandler(Handler):
            runtime = SimpleNamespace(management=manager, max_request_bytes=16384)
        server = ThreadingHTTPServer(("127.0.0.1", 0), BoundHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(thread.join, 2); self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        def request(path, payload=None, headers=True):
            values = {"Content-Type": "application/json"}
            if headers:
                values.update(Authorization="Bearer controlled-management-token",
                    **{"X-Platform-Caller": "test-owner", "X-Platform-Operator": self.actor})
            req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/v1/model-management/" + path,
                data=json.dumps(payload).encode() if payload is not None else None, headers=values)
            try:
                with urllib.request.urlopen(req, timeout=2) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)
        self.assertEqual(request("connections", headers=False)[0], 403)
        status, receipt = request("connection-commands", {"command_id": "http:create", "expected_revision": 0,
            "action": "connection.create", "input": {"provider": "deepseek-api", "name": "HTTP test"}})
        self.assertEqual(status, 200)
        connection_id = receipt["connection_id"]
        payload = {"command_id": "http:key", "expected_revision": 1, "connection_id": connection_id, "api_key": "controlled-http-secret"}
        self.assertEqual(request("connection-credentials", payload, headers=False)[0], 403)
        self.assertNotIn(connection_id, self.vault.versions)
        status, receipt = request("connection-credentials", payload)
        self.assertEqual(status, 200)
        self.assertNotIn("controlled-http-secret", json.dumps(receipt))
        status, operation = request("connection-operation?command_id=http%3Akey")
        self.assertEqual(status, 200); self.assertEqual(operation["receipt"], receipt)
        self.assertEqual(request("connection-reconcile", {"command_id": "http:key"})[1], operation)
        self.assertTrue(request("connections")[1]["connections"][0]["experimental"])
        self.assertEqual(request("connection-credentials", {**payload, "extra": "forbidden"})[0], 409)
        for path in self.root.rglob("*.json"):
            self.assertNotIn("controlled-http-secret", path.read_text())


class NativeProtocolTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.output = {"ok": True}
        self.status = 200
        self.finish = "stop"
        owner = self
        class Native(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                owner.requests.append((self.path, dict(self.headers), None))
                data = {"data": [{"id": "native-test", "effort": {"supported_levels": ["low", "high"]},
                    "capabilities": {"effort": {"high": {"supported": True}}}}]}
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(data).encode())

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.requests.append((self.path, dict(self.headers), payload))
                value = {"model": payload["model"], "usage": {"input_tokens": 10, "output_tokens": 3},
                    "stop_reason": "end_turn" if owner.finish == "stop" else owner.finish,
                    "content": [{"type": "thinking", "thinking": "private-reasoning-must-not-escape"},
                                {"type": "text", "text": json.dumps(owner.output)}],
                    "choices": [{"finish_reason": owner.finish, "message": {"role": "assistant", "content": json.dumps(owner.output),
                        "reasoning_content": "private-reasoning-must-not-escape"}}]}
                self.send_response(owner.status)
                if owner.status == 302:
                    self.send_header("Location", "http://127.0.0.1:1/credential-exfiltration")
                self.end_headers()
                self.wfile.write(json.dumps(value).encode())
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Native)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True); thread.start()
        self.addCleanup(thread.join, 2); self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)

    @contextmanager
    def credential(self):
        yield "controlled-test-key", "opaque-test-generation"

    def opener(self, request, timeout):
        # Only this controlled test transport rewrites the reviewed origin.
        # Production never accepts a caller-supplied endpoint.
        from urllib.parse import urlsplit
        from api_provider_adapter import NoApiRedirect
        parts = urlsplit(request.full_url)
        self.assertIn(parts.scheme + "://" + parts.netloc, [x["origin"] for x in PRESETS.values()])
        local = urllib.request.Request(f"http://127.0.0.1:{self.server.server_port}" + parts.path + ("?" + parts.query if parts.query else ""),
            data=request.data, headers=dict(request.headers))
        return urllib.request.build_opener(NoApiRedirect()).open(local, timeout=timeout)

    def invoke(self, provider, schema=PROBE_SCHEMA, effort=None, opener=None):
        backend = ApiBackend(provider, self.credential, opener=opener or self.opener)
        model = {"model": "native-test", "supported_efforts": [effort], "model_digest": None, "runtime_version": None}
        return backend.adapter(model, effort, {"timeout_seconds": 2, "max_output_tokens": 4096, "max_output_bytes": 65536}).invoke(
            input_payload={"operator_request": "Return the task result"}, output_schema=schema, prompt_version="conformance", system_prompt="Bounded task")

    def test_all_seven_task_schemas_complete_on_each_native_protocol(self):
        selections = fixture_selections()
        schemas = [task["provider_output_schema_document"] for profile in selections["profiles"].values() for task in profile["task_contracts"].values()]
        self.assertEqual(len(schemas), 7)
        for provider in PRESETS:
            for index, schema in enumerate(schemas):
                with self.subTest(provider=provider, task=index):
                    self.output = sample(schema)
                    result = self.invoke(provider, schema, "high")
                    self.assertEqual(result.output, self.output)
                    self.assertIsNone(result.runtime_version)
                    self.assertIsNone(result.model_digest)
                    self.assertNotIn("private-reasoning", repr(result))
                    path, headers, payload = self.requests[-1]
                    self.assertEqual(path, PRESETS[provider]["path"])
                    self.assertEqual(headers["Authorization"], "Bearer controlled-test-key")
                    self.assertNotIn("tools", payload)
                    self.assertFalse(payload["stream"])
                    if provider == "claude-api":
                        self.assertEqual(headers["Anthropic-Version"], "2026-10-21")
                        self.assertEqual(payload["output_config"]["effort"], "high")
                    else:
                        self.assertEqual(payload["reasoning_effort"], "high")

    def test_catalogue_is_native_and_glm_is_explicitly_manual(self):
        for provider in ("claude-api", "deepseek-api"):
            models = ApiBackend(provider, self.credential, opener=self.opener).discover()
            self.assertEqual(models[0]["model"], "native-test")
            self.assertIn("high", models[0]["supported_efforts"])
        backend = ApiBackend("glm-api", self.credential, opener=lambda *a, **k: self.fail("GLM has no admitted catalogue API"))
        with self.assertRaises(ConfigurationError):
            backend.discover()
        self.assertEqual(backend.metadata("unknown-model")["supported_efforts"], [None])
        self.assertEqual(glm_efforts("glm-5.3"), ["low", "high", "max"])
        self.assertEqual(glm_efforts("glm-5.2"), ["none", "high", "max"])
        self.invoke("glm-api", effort=False)
        self.assertEqual(self.requests[-1][2]["thinking"], {"type": "disabled"})

    def test_errors_truncation_schema_and_uncertain_submission_do_not_retry(self):
        for provider in PRESETS:
            for status, expected in ((401, ApiAccessDenied), (403, ApiAccessDenied), (429, ProviderBusy),
                                     (400, ApiRejected), (302, ApiRejected), (500, ProviderCompletionUnknown)):
                with self.subTest(provider=provider, status=status):
                    self.status = status
                    before = len(self.requests)
                    with self.assertRaises(expected):
                        self.invoke(provider)
                    self.assertEqual(len(self.requests), before + 1)
            self.status = 200
            self.finish = "max_tokens" if provider == "claude-api" else "length"
            with self.assertRaises(ApiOutputInvalid):
                self.invoke(provider)
            self.finish = "stop"
            self.output = {"ok": False}
            with self.assertRaises(ApiOutputInvalid):
                self.invoke(provider)
            self.output = {"ok": True}
            calls = []
            def lost_response(request, timeout):
                calls.append(request)
                raise TimeoutError("controlled private transport detail")
            with self.assertRaises(ProviderCompletionUnknown) as failure:
                self.invoke(provider, opener=lost_response)
            self.assertEqual(len(calls), 1)
            self.assertNotIn("private transport", str(failure.exception))

    def test_claude_grammar_projection_does_not_weaken_final_task_validation(self):
        schema = {"type": "object", "properties": {"text": {"type": "string", "maxLength": 3}},
            "required": ["text"], "additionalProperties": False}
        self.assertNotIn("maxLength", claude_grammar(schema)["properties"]["text"])
        self.output = {"text": "too long"}
        with self.assertRaises(ApiOutputInvalid):
            self.invoke("claude-api", schema)


if __name__ == "__main__":
    unittest.main()
