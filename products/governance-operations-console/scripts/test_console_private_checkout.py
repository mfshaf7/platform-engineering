"""Real local Git checkout with isolated Source App scope/revocation proof."""
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_console_private_source import PrivateSourceTests
from console_private_source import PrivateSourceError, authority_ref
import console_private_checkout as checkout


class PrivateCheckoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): PrivateSourceTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls): PrivateSourceTests.tearDownClass.__func__(cls)

    def setUp(self):
        PrivateSourceTests.setUp(self)
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.workspace = root / "workspace"; self.workspace.mkdir()
        self.private = root / "private"; self.private.mkdir(mode=0o700)
        self.origin = root / "source"; self.origin.mkdir()
        def git(*args): return subprocess.run(["git", "-C", str(self.origin), *args], check=True, capture_output=True).stdout.decode().strip()
        self.git = git
        git("init", "-b", "main"); git("config", "user.name", "Synthetic Author"); git("config", "user.email", "synthetic@example.test")
        (self.origin / "README.md").write_text("# Private fixture project\n")
        git("add", "README.md"); git("commit", "-m", "Synthetic base")
        self.head = git("rev-parse", "HEAD")
        self.server.git_head, self.server.git_tree = self.head, git("rev-parse", "HEAD^{tree}")
        self.value = {"schema_version": 1, "owner_repo": self.snapshot.owner_repo, "operation": "bootstrap", "action": "clone", "branch": "main",
            "expected_base": self.head, "authority_ref": authority_ref(self.snapshot)}
        self.calls = []
        self.temporary_credentials = []

    def execute(self, command, **kwargs):
        self.calls.append(command)
        self.assertEqual(kwargs["env"]["GIT_ALLOW_PROTOCOL"], "https")
        self.assertEqual(kwargs["env"]["GIT_CONFIG_GLOBAL"], "/dev/null")
        self.assertNotIn("GH_TOKEN", kwargs["env"])
        askpass = Path(kwargs["env"]["GIT_ASKPASS"])
        self.temporary_credentials.append(askpass.parent)
        self.assertTrue(askpass.is_file()); self.assertEqual(askpass.stat().st_mode & 0o777, 0o700)
        self.assertNotIn("agent-source-secret", " ".join(command))
        # Replace only the exact approved GitHub URL at this test boundary.
        # All real Git clone/fetch/ref and filesystem checks still execute.
        url = "https://github.com/mfshaf7-workspace/sample-owner.git"
        command = [str(self.origin) if value == url else value for value in command]
        kwargs["env"] = {**kwargs["env"], "GIT_ALLOW_PROTOCOL": "file"}
        return subprocess.run(command, **kwargs)

    def run_checkout(self, *, value=None, reader=None):
        return checkout.checkout(value or self.value, workspace_root=self.workspace, private_root=self.private,
            snapshot_reader=reader or (lambda: self.snapshot), args=self.args, client=self.client, execute=self.execute)

    def test_clone_fetch_and_ref_use_private_derived_source_and_read_only_revoked_tokens(self):
        result = self.run_checkout()
        target = checkout.source_location(self.workspace, self.snapshot)
        self.assertTrue(result["read_credential_revoked"])
        self.assertEqual(result["remote_commit"], self.head)
        self.assertEqual((target / "README.md").read_text(), "# Private fixture project\n")
        self.assertFalse((self.workspace / self.snapshot.owner_repo).exists())
        self.assertEqual(target.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.state.issued_permissions, [{"metadata": "read", "contents": "read"}])
        self.assertEqual(self.state.revoked, ["agent-source-secret-1"])
        self.assertTrue(all(not directory.exists() for directory in self.temporary_credentials))
        (target / "unique.txt").write_text("Preserve this local work\n")
        for action, branch in (("fetch", "main"), ("ref", "feature/not-created")):
            value = {**self.value, "action": action, "branch": branch, "expected_base": self.head if action == "fetch" else None}
            observed = self.run_checkout(value=value)
            self.assertEqual(observed["remote_commit"], self.head if action == "fetch" else None)
        self.assertEqual((target / "unique.txt").read_text(), "Preserve this local work\n")
        self.assertEqual(len(self.state.revoked), 3)
        self.assertNotIn("agent-source-secret", str(result))

    def test_stale_authority_arbitrary_paths_and_linked_source_fail_before_token_issuance(self):
        for mutate in (lambda v: v.update(destination="/another/path"), lambda v: v.update(action="delete"),
                       lambda v: v.update(branch="../escape"), lambda v: v["authority_ref"]["record_ref"].update(version=4)):
            value = copy.deepcopy(self.value); mutate(value)
            with self.assertRaises(PrivateSourceError): self.run_checkout(value=value)
        self.assertEqual(self.state.issued, [])
        (self.workspace / ".worktrees").symlink_to(self.private, target_is_directory=True)
        with self.assertRaises(PrivateSourceError): self.run_checkout()
        self.assertEqual(self.state.issued, []); self.assertEqual(self.calls, [])

    def test_changed_registration_and_failed_revoke_withhold_completion_and_preserve_existing_source(self):
        changed = copy.deepcopy(self.snapshot); changed.source_authority["record_ref"]["version"] += 1
        states = iter((self.snapshot, changed))
        with self.assertRaises(PrivateSourceError): self.run_checkout(reader=lambda: next(states))
        target = checkout.source_location(self.workspace, self.snapshot)
        self.assertTrue((target / "README.md").is_file())
        self.assertEqual(len(self.state.revoked), 1)
        # Resume via fetch; never reclone over retained source.
        self.state.mode = "revoke-failure"
        with self.assertRaisesRegex(PrivateSourceError, "could not be confirmed revoked"):
            self.run_checkout(value={**self.value, "action": "fetch"})
        self.assertTrue((target / "README.md").is_file())
        self.assertTrue(all(not directory.exists() for directory in self.temporary_credentials))

    def test_an_original_running_read_blocks_a_retry_before_any_token_or_git_effect(self):
        locks = self.private / "source-checkout-locks"; locks.mkdir(mode=0o700)
        key = hashlib.sha256(json.dumps([self.value["authority_ref"]["canonical_authority"], self.value["owner_repo"]], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        descriptor = os.open(locks / key, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            with self.assertRaisesRegex(PrivateSourceError, "original checkout read is still running"): self.run_checkout()
            self.assertEqual(self.state.issued, []); self.assertEqual(self.calls, [])
        finally: os.close(descriptor)

    def test_git_failure_revokes_credential_and_never_replaces_existing_checkout(self):
        self.run_checkout()
        before = len(self.state.issued)
        with self.assertRaises(PrivateSourceError): self.run_checkout()
        self.assertEqual(len(self.state.issued), before)
        original = self.execute
        def failed(*args, **kwargs): raise subprocess.CalledProcessError(1, "git", stderr=b"private source failure")
        self.execute = failed
        with self.assertRaisesRegex(PrivateSourceError, "exact authenticated Git read"):
            self.run_checkout(value={**self.value, "action": "fetch"})
        self.execute = original
        self.assertEqual(len(self.state.revoked), len(self.state.issued))
        self.assertTrue(all(not directory.exists() for directory in self.temporary_credentials))


if __name__ == "__main__": unittest.main()
