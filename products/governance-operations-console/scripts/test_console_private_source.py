"""Reduced Source App inspection against an actual isolated HTTP provider."""
import argparse
import base64
import copy
from http.server import ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

import agent_source_identity as identity
from agent_source_instance import validated_snapshot
import test_agent_source_identity as source_fixture
from test_console_instance_source import native, POLICY, OWNER
from console_private_source import InspectionClient, PrivateSourceError, authority_ref, inspect_owner_controls

FILES = {"AGENTS.md": b"# Synthetic private owner controls\n", "README.md": b"# Synthetic private project\n",
         "private-application.py": b"PRIVATE APPLICATION CONTENT MUST NOT BE READ"}
BLOBS = {path: hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() for path, raw in FILES.items()}


class SourceHandler(source_fixture.ProviderHandler):
    def do_GET(self):
        self.server.reads.append(self.path)
        state = self.server.state
        if self.path == "/repositories/123456789":
            return self._json(200, {"id": 123456789, "full_name": "mfshaf7-workspace/sample-owner", "private": True,
                "visibility": "private", "archived": False, "disabled": False, "default_branch": "main"})
        prefix = "/repos/mfshaf7-workspace/sample-owner"
        if self.path == prefix + "/commits/main":
            self.server.main_reads += 1
            sha = "c" * 40 if state.mode == "changed-main" and self.server.main_reads > 1 else getattr(self.server, "git_head", "a" * 40)
            return self._json(200, {"sha": sha, "commit": {"tree": {"sha": getattr(self.server, "git_tree", "b" * 40)}}})
        if self.path == prefix + "/git/trees/" + "b" * 40 + "?recursive=1":
            tree = [{"path": path, "mode": "120000" if state.mode == "symlink" and path == "README.md" else "100644", "type": "blob", "sha": BLOBS[path], "size": len(raw)} for path, raw in FILES.items()]
            return self._json(200, {"sha": "b" * 40, "truncated": state.mode == "truncated", "tree": tree})
        if self.path.startswith(prefix + "/git/blobs/"):
            sha = self.path.rsplit("/", 1)[1]
            path = next((name for name, digest in BLOBS.items() if digest == sha), None)
            if path is None: return self._json(404, {})
            raw = FILES[path]
            payload = b"x" * len(raw) if state.mode == "wrong-blob" else raw
            return self._json(200, {"sha": sha, "encoding": "base64", "size": len(raw), "content": base64.b64encode(payload).decode()})
        return super().do_GET()


class PrivateSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.key = Path(cls.temp.name) / "synthetic-key.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(cls.key)], capture_output=True, check=True)
        cls.key.chmod(0o600)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        self.state = source_fixture.ProviderState()
        self.state.installation_id = 172173010
        self.state.account_login, self.state.account_id, self.state.account_type = "mfshaf7-workspace", 322605984, "Organization"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), SourceHandler)
        self.server.state, self.server.reads, self.server.main_reads = self.state, [], 0
        thread = threading.Thread(target=self.server.serve_forever, daemon=True); thread.start()
        self.addCleanup(thread.join, 2); self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)
        self.client = InspectionClient(f"http://127.0.0.1:{self.server.server_port}", sandbox=True)
        self.args = argparse.Namespace(contract=identity.DEFAULT_CONTRACT, vault_command="vault", sandbox=True, private_key_file=self.key)
        value = native()
        value["source_authority"]["provider_repository"] = {"provider": "github", "provider_repository_id": "123456789", "full_name": "mfshaf7-workspace/sample-owner"}
        self.snapshot = validated_snapshot(value, instance_id="synthetic-installation", owner=OWNER, operation="bootstrap", policy_ref=POLICY)
        self.input = {"schema_version": 1, "owner_repo": OWNER, "operation": "bootstrap", "paths": ["AGENTS.md", "README.md"], "authority_ref": authority_ref(self.snapshot)}

    def inspect(self, *, reader=None, value=None):
        return inspect_owner_controls(value or self.input, snapshot_reader=reader or (lambda: self.snapshot), args=self.args, client=self.client)

    def test_full_source_app_verification_precedes_a_one_repository_read_token_and_only_controls_are_returned(self):
        result = self.inspect()
        self.assertEqual(self.state.issued, [("sample-owner",)])
        self.assertEqual(self.state.issued_permissions, [{"metadata": "read", "contents": "read"}])
        self.assertEqual(self.state.revoked, ["agent-source-secret-1"])
        self.assertEqual(result["visibility"], "private")
        self.assertEqual(result["owner_repo"], OWNER)
        self.assertEqual(result["fetched_base"], "a" * 40)
        self.assertEqual(result["observed_files"], {path: FILES[path].decode() for path in self.input["paths"]})
        self.assertNotIn(BLOBS["private-application.py"], " ".join(self.server.reads))
        serialized = json.dumps(result)
        self.assertNotIn("PRIVATE APPLICATION CONTENT", serialized)
        self.assertNotIn("agent-source-secret", serialized)
        self.assertNotIn("private-application.py", serialized)

    def test_arbitrary_files_and_stale_review_fail_before_key_or_token_access(self):
        for change in (lambda v: v.update(paths=["private-application.py"]),
                       lambda v: v["authority_ref"]["record_ref"].update(version=4),
                       lambda v: v.update(paths=["README.md", "AGENTS.md"])):
            value = copy.deepcopy(self.input); change(value)
            with self.assertRaises((PrivateSourceError, ValueError)): self.inspect(value=value)
        self.assertEqual(self.server.reads, [])
        self.assertEqual(self.state.issued, [])

    def test_source_app_permission_mismatch_is_denied_before_mint(self):
        self.state.mode = "overprivileged"
        with self.assertRaises(PrivateSourceError): self.inspect()
        self.assertEqual(self.state.issued, [])

    def test_changed_main_wrong_blob_symlink_and_incomplete_tree_withhold_source_and_revoke(self):
        for mode in ("changed-main", "wrong-blob", "symlink", "truncated"):
            with self.subTest(mode=mode):
                self.state.mode, self.server.main_reads = mode, 0
                with self.assertRaises(PrivateSourceError): self.inspect()
                self.assertEqual(len(self.state.revoked), len(self.state.issued))

    def test_changed_registration_after_source_read_is_not_a_success(self):
        changed = copy.deepcopy(self.snapshot)
        changed.source_authority["record_ref"]["version"] += 1
        states = iter((self.snapshot, changed))
        with self.assertRaises(PrivateSourceError): self.inspect(reader=lambda: next(states))
        self.assertEqual(len(self.state.revoked), 1)

    def test_revocation_failure_withholds_all_source_contents(self):
        self.state.mode = "revoke-failure"
        with self.assertRaisesRegex(PrivateSourceError, "could not be confirmed revoked"): self.inspect()
        self.assertEqual(len(self.state.issued), 1)
        self.assertEqual(self.state.revoked, [])


if __name__ == "__main__": unittest.main()
