"""Current source eligibility proof without provider tokens or live services."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from console_instance_source import InstanceSourceError, InstanceSourceReader, MAX_BYTES, validated_snapshot


POLICY = {"repo": "workspace-governance", "revision": "a" * 40, "contract_digest": "sha256:" + "b" * 64}
AUTHORITY = {"kind": "internal-instance-record", "instance_id": "synthetic-installation", "record_id": "repo:canonical-project-key"}
OWNER = "canonical-project-key"


def native(operation="bootstrap"):
    reference = {"version": 3, "digest": "sha256:" + "c" * 64}
    proof = {"schema_version": 1, "owner_repo": OWNER, "classification": "proposed", "inventory_posture": None,
        "intake_entry_ref": {"id": AUTHORITY["record_id"], **reference},
        "provider_repository": {"provider": "github", "provider_repository_id": "123", "full_name": "example-org/different-physical-name"},
        "owner_purpose": "Synthetic source-only project", "source_bootstrap_eligible": True, "ordinary_source_eligible": False,
        "model_writes_allowed": False, "canonical_mutation": False, "runtime_activation": False,
        "canonical_authority": AUTHORITY.copy(), "record_ref": reference, "policy_ref": POLICY.copy(),
        "validation_behavior": {"posture": "covered-by-owner-repo", "wgcf_graph_role": "product-runtime-source"}}
    if operation != "bootstrap":
        del proof["validation_behavior"]
        proof.update(classification="active", inventory_posture="active", intake_entry_ref=None,
            inventory_entry_ref={"id": AUTHORITY["record_id"], **reference}, source_bootstrap_eligible=False,
            ordinary_source_eligible=True, verification_setup_eligible=True)
    return {"schema_version": 1, "canonical_authority": AUTHORITY.copy(), "source_authority": proof}


def project(value, operation="bootstrap"):
    return validated_snapshot(value, instance_id=AUTHORITY["instance_id"], owner=OWNER, operation=operation, policy_ref=POLICY)


class InstanceSourceReaderTests(unittest.TestCase):
    def reader(self, fetch_json, **overrides):
        return InstanceSourceReader(**{**dict(base_url="http://127.0.0.1:8080", caller_id="platform-engineering-source-reader",
            caller_secret="p" * 32, instance_id=AUTHORITY["instance_id"], policy_reader=lambda: copy.deepcopy(POLICY), fetch_json=fetch_json), **overrides})

    def test_exact_namespace_policy_operation_and_provider_identity_are_retained(self):
        calls = []
        def fetch(request):
            calls.append(request)
            return native()
        reader = self.reader(fetch)
        snapshot = reader.read(OWNER, "bootstrap")
        self.assertEqual(snapshot.source_authority["provider_repository"]["full_name"], "example-org/different-physical-name")
        self.assertEqual(snapshot.owner_repo, OWNER)
        self.assertEqual(snapshot.source_authority["record_ref"]["version"], 3)
        self.assertEqual(calls[0].get_method(), "GET")
        self.assertEqual(calls[0].full_url, f"http://127.0.0.1:8080/v1/instance-records/repositories/{OWNER}/source-authority?operation=bootstrap")
        self.assertEqual(calls[0].get_header("X-wgcf-caller-id"), "platform-engineering-source-reader")
        self.assertEqual(calls[0].get_header("X-wgcf-caller-secret"), "p" * 32)
        reader.read(OWNER, "bootstrap")
        self.assertEqual(len(calls), 2)  # A previous response cannot become a permanent local authority.
        for operation in ("configure-verification", "ordinary-source"):
            self.assertEqual(project(native(operation), operation).operation, operation)

    def test_foreign_stale_malformed_or_privileged_source_proofs_fail_closed(self):
        mutations = [lambda v: v["canonical_authority"].update(instance_id="another-installation"),
            lambda v: v["source_authority"]["policy_ref"].update(revision="d" * 40),
            lambda v: v["source_authority"]["record_ref"].update(version=4),
            lambda v: v["source_authority"].update(ordinary_source_eligible=True),
            lambda v: v["source_authority"].update(model_writes_allowed=True),
            lambda v: v["source_authority"].update(runtime_activation=True),
            lambda v: v["source_authority"].update(owner_purpose="x" * 8193),
            lambda v: v["source_authority"].update(owner_purpose="invalid-\ud800"),
            lambda v: v["source_authority"]["provider_repository"].update(provider_repository_id="0"),
            lambda v: v.update(unexpected="caller-controlled")]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                value = native(); mutate(value)
                with self.assertRaises(InstanceSourceError): project(value)
        with self.assertRaises(InstanceSourceError): project(native("ordinary-source"))
        with self.assertRaises(InstanceSourceError): project(native(), "ordinary-source")

    def test_provider_lookup_uses_the_immutable_id_and_keeps_the_authenticated_canonical_alias(self):
        calls = []
        def fetch(request):
            calls.append(request.full_url)
            return native("ordinary-source")
        reader = self.reader(fetch)
        result = reader.read_provider("123", "example-org/different-physical-name", "ordinary-source")
        self.assertEqual(result.owner_repo, OWNER)
        self.assertIn("/provider-repositories/github/123/source-authority?operation=ordinary-source", calls[0])
        for identifier, name in (("456", "example-org/different-physical-name"), ("123", "example-org/renamed-or-substituted")):
            with self.assertRaises(InstanceSourceError): reader.read_provider(identifier, name, "ordinary-source")

    def test_only_positive_current_legacy_proof_selects_the_existing_git_reader(self):
        legacy = {"schema_version": 1, "canonical_authority": {"kind": "legacy-git", "repo": "workspace-governance", "revision": POLICY["revision"]}, "record_id": AUTHORITY["record_id"]}
        self.assertIsNone(project(legacy))
        legacy["canonical_authority"]["revision"] = "d" * 40
        with self.assertRaises(InstanceSourceError): project(legacy)
        def unavailable(_request): raise RuntimeError("Synthetic connection detail must stay private")
        with self.assertRaisesRegex(InstanceSourceError, "no alternate authority") as captured:
            self.reader(unavailable).read(OWNER, "bootstrap")
        self.assertNotIn("connection detail", str(captured.exception))

    def test_owner_paths_bad_configuration_and_policy_changes_never_select_another_authority(self):
        calls = []
        for owner in ("../escape", "repo:key", "", "x" * 187):
            with self.assertRaises(InstanceSourceError): self.reader(lambda request: calls.append(request)).read(owner, "bootstrap")
        self.assertEqual(calls, [])
        for url in ("http://example.invalid:8080", "https://127.0.0.1:8080", "http://127.0.0.1:bad", "http://127.0.0.1:8080/path", "http://user:password@127.0.0.1:8080"):
            with self.assertRaises(InstanceSourceError): self.reader(lambda _: native(), base_url=url)
        policies = iter([POLICY, {**POLICY, "revision": "d" * 40}])
        with self.assertRaisesRegex(InstanceSourceError, "changed during"):
            self.reader(lambda _: native(), policy_reader=lambda: next(policies)).read(OWNER, "bootstrap")

    def test_native_http_reader_bounds_bytes_rejects_redirects_and_never_exposes_error_bodies(self):
        response = {"status": 200, "body": json.dumps(native()).encode(), "headers": {}}
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                self.send_response(response["status"])
                for name, value in response["headers"].items(): self.send_header(name, value)
                self.end_headers()
                self.wfile.write(response["body"])
            def log_message(self, *_args): pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        reader = self.reader(None, base_url=f"http://127.0.0.1:{server.server_port}")
        self.assertEqual(reader.read(OWNER, "bootstrap").owner_repo, OWNER)
        for status, body, headers in [(503, b"synthetic-private-error-body", {}), (200, b"x" * (MAX_BYTES + 1), {}),
                                      (200, b'{"duplicate":1,"duplicate":2}', {}),
                                      (302, b"", {"Location": "http://example.invalid/untrusted"})]:
            response.update(status=status, body=body, headers=headers)
            with self.assertRaises(InstanceSourceError) as captured: reader.read(OWNER, "bootstrap")
            self.assertNotIn("synthetic-private-error-body", str(captured.exception))
        self.assertEqual(len(requests), 5)


if __name__ == "__main__": unittest.main()
