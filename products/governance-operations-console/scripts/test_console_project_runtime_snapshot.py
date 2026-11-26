"""Check Platform staging and refusal paths using isolated source volumes."""

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from platform_operation_provider import OperationStore  # Loads shared Platform modules.
from agent_source_instance import digest
from console_project_runtime_snapshot import ProjectSnapshotError, stage_project_snapshot


class ProjectSnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.snapshots = root / "snapshots"
        self.snapshots.mkdir(mode=0o700)
        self.staging = OperationStore(root / "private").root / "staging"
        self.staging.mkdir(mode=0o700)
        self.scope = {"installation_id": "test", "project_custody_ref": "project:test", "repository_id": 1234,
                      "app_root": "app", "dependency_paths": ["shared"], "environment_ref": "devint:local"}
        self.manifest = {
            "schema_version": 1, "scope": self.scope,
            "source": {"kind": "saved-draft", "base_commit": "a" * 40, "session_id": "session:test",
                       "revision": "saved:1", "change_set_digest": "sha256:" + "b" * 64},
            "setup": {"recipe_id": "static", "configuration_revision": "setup:1"},
            "command_id": "run:1", "total_bytes": 0, "files": [],
        }
        self.blobs = {}
        self.add_file("app/index.html", b"<main>Saved revision</main>", "100644")
        self.add_file("shared/illustration.bin", b"\x00\xff\x15\x90", "100755")

    def add_file(self, path, content, mode):
        identity = hashlib.sha256(content).hexdigest()
        self.blobs[identity] = content
        self.manifest["total_bytes"] += len(content)
        self.manifest["files"].append({
            "path": path, "type": "file", "mode": mode, "size": len(content), "blob_digest": "sha256:" + identity,
        })

    def publish(self):
        identity = digest(self.manifest)
        folder = self.snapshots / identity[7:]
        folder.mkdir(mode=0o700, exist_ok=True)
        blob_dir = folder / "blobs"
        blob_dir.mkdir(mode=0o700, exist_ok=True)
        for name, content in self.blobs.items():
            (blob_dir / name).write_bytes(content)
        (folder / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        return folder, {**{key: self.manifest[key] for key in ("scope", "source", "setup", "command_id")},
                        "scope_digest": digest({key: self.scope[key] for key in ("installation_id", "project_custody_ref", "app_root", "environment_ref")}), "snapshot": {
                            "snapshot_id": "project-source:" + identity[7:], "manifest_digest": identity}}

    def stage(self, binding, file_limit=8):
        return stage_project_snapshot(self.snapshots, self.staging, binding,
                                      max_manifest_bytes=8192, max_files=file_limit, max_bytes=4096)

    @contextmanager
    def refusal(self, message):
        with self.assertRaisesRegex(ProjectSnapshotError, message):
            yield
        self.assertEqual(list(self.staging.iterdir()), [], "Do not leave partially verified source visible.")

    def test_staging_preserves_exact_binary_bytes_and_modes(self):
        _, binding = self.publish()
        output = self.stage(binding)
        self.assertEqual((output / "app/index.html").read_bytes(), self.blobs[self.manifest["files"][0]["blob_digest"][7:]])
        self.assertEqual((output / "shared/illustration.bin").read_bytes(), b"\x00\xff\x15\x90")
        self.assertEqual((output / "shared/illustration.bin").stat().st_mode & 0o777, 0o755)
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)

    def test_wrong_configuration_and_oversized_manifest_are_refused(self):
        _, binding = self.publish()
        with self.refusal("differs from the acknowledged command"):
            self.stage({**binding, "setup": {**binding["setup"], "configuration_revision": "setup:2"}})
        with self.refusal("exceeds its limits"):
            self.stage(binding, file_limit=1)

    def test_invalid_paths_fail_before_source_is_copied(self):
        for path in ("app/INDEX.HTML", "app/index.html/subfile", "outside/secret", "app/..", "app/.Git/config"):
            with self.subTest(path=path):
                self.add_file(path, b"", "100644")
                _, binding = self.publish()
                with self.refusal("collide|conflicts|outside"):
                    self.stage(binding)
                self.manifest["files"].pop()

    def test_changed_blob_and_symlink_leave_no_staged_source(self):
        folder, binding = self.publish()
        blob = folder / "blobs" / self.manifest["files"][1]["blob_digest"][7:]
        blob.write_bytes(b"bad!")
        with self.refusal("content digest"):
            self.stage(binding)
        blob.unlink()
        target = self.snapshots / "unowned-file"
        target.write_bytes(b"\x00\xff\x15\x90")
        blob.symlink_to(target)
        with self.refusal("could not be verified"):
            self.stage(binding)
        self.assertEqual(target.read_bytes(), b"\x00\xff\x15\x90")


if __name__ == "__main__":
    unittest.main()
