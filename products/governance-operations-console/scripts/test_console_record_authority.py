"""Native Git producer proof; no provider, service or primary checkout writes."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import console_record_authority

from console_record_authority import (
    CHECKPOINT, TRUSTED_REF, RecordAuthorityError, admit_record_delta,
    data_path, git, provider_remote, refresh_snapshot,
    snapshot_status,
)


class ConsoleRecordAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        git(self.source, "init", "-b", "main")
        git(self.source, "config", "user.name", "Synthetic source author")
        git(self.source, "config", "user.email", "test@example.invalid")
        self.owner = "workspace-governance"
        self.cache = self.root / "cache"
        self.write("scripts/control.py", "reviewed control code")
        self.write("contracts/products.yaml", "products: {}")
        self.commit("reviewed source")
        self.reviewed = git(self.source, "rev-parse", "HEAD")
        self.now = datetime.now(timezone.utc)

    def write(self, path, value):
        target = self.source / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)

    def commit(self, message):
        git(self.source, "add", ".")
        git(self.source, "commit", "-m", message)
        return git(self.source, "rev-parse", "HEAD")

    def refresh(self):
        return refresh_snapshot(self.cache, self.source, self.owner, self.reviewed,
            now=self.now, remote_for_test=self.source)

    @property
    def clone(self):
        return self.cache / self.owner

    def test_native_record_merge_refreshes_data_not_reviewed_code_or_primary_checkout(self):
        first = self.refresh()
        self.assertEqual(first["record_revision"], self.reviewed)
        self.write("contracts/products.yaml", "products: {sample: {lifecycle: active}}")
        current = self.commit("approved inventory record")
        result = self.refresh()
        self.assertEqual(result["record_revision"], current)
        self.assertEqual(result["changed_path_count"], 1)
        self.assertEqual(git(self.clone, "rev-parse", TRUSTED_REF), current)
        self.assertEqual(git(self.clone, "show", "HEAD:scripts/control.py"), "reviewed control code")
        self.assertEqual(git(self.source, "rev-parse", "HEAD"), current)
        self.assertEqual(git(self.source, "status", "--porcelain"), "")
        checkpoint = json.loads((self.clone / ".git" / CHECKPOINT).read_text())
        self.assertEqual(checkpoint["reviewed_revision"], self.reviewed)
        self.assertEqual(checkpoint["record_revision"], current)
        # Unchanged ticks remain valid without another service or checkout edit.
        self.assertEqual(self.refresh()["record_revision"], current)

    def test_snapshot_status_rejects_expiry_and_private_clone_remains_readable_by_runtime_uid(self):
        previous = os.umask(0o077)
        try:
            self.refresh()
        finally:
            os.umask(previous)
        self.assertTrue(self.clone.stat().st_mode & 0o005)
        self.assertTrue((self.clone / ".git").stat().st_mode & 0o005)
        self.assertTrue((self.clone / "contracts/products.yaml").stat().st_mode & 0o004)
        self.assertEqual(snapshot_status(self.cache, self.owner, self.reviewed, now=self.now)["record_revision"], self.reviewed)
        from datetime import timedelta
        with self.assertRaises(RecordAuthorityError):
            snapshot_status(self.cache, self.owner, self.reviewed, now=self.now + timedelta(minutes=6))

    def admission_source(self):
        self.write("contracts/repos.yaml", "schema_version: 2\nrepos: {}\nretired_repos: {}\n")
        self.write("contracts/intake-register.yaml", "schema_version: 2\nrepos: {}\n")
        for name in ("repos", "intake-register"):
            self.write(f"contracts/schemas/{name}.schema.json", json.dumps({"type": "object"}))
        self.commit("reviewed admission control and initial data")
        self.reviewed = git(self.source, "rev-parse", "HEAD")

    def test_admission_reader_preserves_exact_git_bytes_and_pins_schemas_to_reviewed_code(self):
        self.admission_source()
        self.refresh()
        self.write("contracts/repos.yaml", "schema_version: 2\nrepos: {synthetic: {posture: active}}\nretired_repos: {}\n\n")
        current = self.commit("reviewed data-only inventory update")
        self.refresh()
        result = console_record_authority.read_repository_admission(self.cache, self.reviewed)
        self.assertEqual(result["revision"], current)
        self.assertEqual(result["reviewed_revision"], self.reviewed)
        self.assertEqual(result["inventory"], (self.source / "contracts/repos.yaml").read_bytes())
        self.assertEqual(result["inventory_schema"], {"type": "object"})
        # A control/schema delta cannot ride the data-only freshness lane.
        self.write("contracts/schemas/repos.schema.json", '{"type": "array"}')
        self.commit("unaccepted schema change")
        with self.assertRaises(RecordAuthorityError):
            self.refresh()
        with self.assertRaises(RecordAuthorityError):
            console_record_authority.read_repository_admission(self.cache, self.reviewed)

    def test_admission_reader_denies_missing_expired_dirty_and_midread_changed_authority(self):
        self.admission_source()
        with self.assertRaises(RecordAuthorityError):
            console_record_authority.read_repository_admission(self.cache, self.reviewed)
        self.refresh()
        checkpoint = self.clone / ".git" / CHECKPOINT
        saved = checkpoint.read_text()
        value = json.loads(saved)
        value["valid_until"] = "2020-01-01T00:00:00+00:00"
        checkpoint.write_text(json.dumps(value))
        with self.assertRaises(RecordAuthorityError):
            console_record_authority.read_repository_admission(self.cache, self.reviewed)
        checkpoint.write_text(saved)
        (self.clone / "contracts/repos.yaml").write_text("unproven local inventory")
        with self.assertRaises(RecordAuthorityError):
            console_record_authority.read_repository_admission(self.cache, self.reviewed)
        # Restore only this test's own disposable synthetic file.
        (self.clone / "contracts/repos.yaml").write_bytes((self.source / "contracts/repos.yaml").read_bytes())
        original = snapshot_status(self.cache, self.owner, self.reviewed)
        changed = {**original, "record_revision": "f" * 40}
        with patch.object(console_record_authority, "snapshot_status", side_effect=[original, changed]):
            with self.assertRaisesRegex(RecordAuthorityError, "changed during"):
                console_record_authority.read_repository_admission(self.cache, self.reviewed)

    def test_unchanged_refresh_keeps_prior_valid_checkpoint_readable_during_provider_fetch(self):
        self.refresh()
        original = console_record_authority.git
        observations = []
        def observe(root, *args, **kwargs):
            if args[0] in {"fetch", "checkout", "update-ref"}:
                observations.append(args[0])
                self.assertEqual(snapshot_status(self.cache, self.owner, self.reviewed,
                    now=self.now)["record_revision"], self.reviewed)
            return original(root, *args, **kwargs)
        with patch.object(console_record_authority, "git", side_effect=observe):
            self.refresh()
        self.assertEqual(observations, ["fetch"])

    def test_failure_never_unlinks_through_an_untrusted_clone_symlink(self):
        self.refresh()
        moved = self.cache / "retained"
        self.clone.rename(moved)
        self.clone.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(RecordAuthorityError):
            self.refresh()
        self.assertTrue((moved / ".git" / CHECKPOINT).is_file())

    def test_code_schema_policy_symlink_and_executable_advancement_never_become_authority(self):
        for name, kind in [("scripts/control.py", "code"), ("schemas/product.json", "schema"),
            ("contracts/intake-policy.yaml", "policy"), ("contracts/products.yaml", "symlink"),
            ("contracts/products.yaml", "executable")]:
            with self.subTest(kind=kind):
                accepted = self.refresh()["record_revision"]
                target = self.source / name
                if kind == "symlink":
                    target.unlink()
                    target.symlink_to("../scripts/control.py")
                else:
                    self.write(name, "changed")
                    if kind == "executable":
                        target.chmod(0o755)
                candidate = self.commit("unaccepted control delta")
                with self.assertRaises(RecordAuthorityError):
                    self.refresh()
                self.assertFalse((self.clone / ".git" / CHECKPOINT).exists())
                self.assertEqual(git(self.clone, "rev-parse", "HEAD"), accepted)
                # Rejection retained the source; only this isolated native
                # fixture removes its own synthetic commit for the next vector.
                git(self.source, "revert", "--no-edit", candidate)

    def test_missing_checkpoint_after_interruption_recovers_without_rewinding_history(self):
        self.refresh()
        self.write("contracts/products.yaml", "products: {sample: {lifecycle: active}}")
        latest = self.commit("new record")
        self.refresh()
        (self.clone / ".git" / CHECKPOINT).unlink()
        self.assertEqual(self.refresh()["record_revision"], latest)
        # Rewrite the synthetic provider ref without touching its working tree.
        git(self.source, "update-ref", "refs/heads/main", self.reviewed)
        with self.assertRaises(RecordAuthorityError):
            self.refresh()
        with self.assertRaises(RecordAuthorityError):
            self.refresh()  # No checkpoint is not permission to rewind next tick.
        self.assertEqual(git(self.clone, "rev-parse", "HEAD"), latest)

    def test_provider_failure_invalidates_freshness_without_rewriting_trusted_ref(self):
        self.refresh()
        git(self.source, "update-ref", "-d", "refs/heads/main")
        with self.assertRaises(RecordAuthorityError):
            self.refresh()
        self.assertFalse((self.clone / ".git" / CHECKPOINT).exists())
        self.assertEqual(git(self.clone, "rev-parse", TRUSTED_REF), self.reviewed)

    def test_dirty_cache_is_preserved_and_not_silently_reset(self):
        self.refresh()
        file = self.clone / "unproven.txt"
        file.write_text("preserve unique work")
        with self.assertRaises(RecordAuthorityError):
            self.refresh()
        self.assertEqual(file.read_text(), "preserve unique work")
        self.assertFalse((self.clone / ".git" / CHECKPOINT).exists())

    @unittest.skipUnless(os.environ.get("CONSOLE_NATIVE_RECORD_IMAGE_PROOF") == "1", "explicit local OOS/WGCF image proof")
    def test_platform_checkpoint_is_consumed_by_both_actual_read_only_images_at_distinct_uid(self):
        self.refresh()
        mount = f"type=bind,source={self.clone},target=/authority,readonly"
        consumers = [
            ["-e", "OOS_RECORD_AUTHORITY_FRESHNESS_REQUIRED=true", "oos-api:journey-1275-proof", "node", "--input-type=module", "-e",
             "import{execFileSync}from'node:child_process';import{requireRecordAuthorityFreshness}from'/app/src/record-authority-freshness.js';const git=async(root,...args)=>execFileSync('git',['-c','safe.directory='+root,'-C',root,...args],{encoding:'utf8'}).trim();await requireRecordAuthorityFreshness({authorityRoot:'/authority',ownerRepo:'workspace-governance',git});console.log('fresh checkpoint accepted');"],
            ["-e", "WGCF_RECORD_AUTHORITY_FRESHNESS_REQUIRED=true", "wgcf-api:journey-1275-proof", "python", "-c",
             "from pathlib import Path;from control_fabric_core.record_authority_freshness import require_record_authority_freshness;require_record_authority_freshness(Path('/authority'),'workspace-governance');print('fresh checkpoint accepted')"],
        ]
        def consume(command):
            return subprocess.run(["docker", "run", "--rm", "--network", "none", "--user", "10001:10001",
                "--mount", mount, *command], capture_output=True, text=True, timeout=30)
        for consumer in consumers:
            result = consume(consumer)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("fresh checkpoint accepted", result.stdout)
        file = self.clone / ".git" / CHECKPOINT
        value = json.loads(file.read_text())
        value["valid_until"] = "2020-01-01T00:00:00+00:00"
        file.write_text(json.dumps(value))
        for consumer in consumers:
            self.assertNotEqual(consume(consumer).returncode, 0)

    def test_only_fixed_provider_and_record_paths_are_admitted(self):
        git(self.source, "remote", "add", "origin", "https://github.com/mfshaf7/workspace-governance.git")
        self.assertEqual(provider_remote(self.source, self.owner), "https://github.com/mfshaf7/workspace-governance.git")
        git(self.source, "remote", "set-url", "origin", "https://github.com/other/workspace-governance.git")
        with self.assertRaises(RecordAuthorityError):
            provider_remote(self.source, self.owner)
        for path in ["scripts/run.py", "schemas/product.json", "contracts/intake-policy.yaml", "../products.yaml"]:
            self.assertFalse(data_path(self.owner, path))
        self.assertTrue(data_path("workspace-prototype-studio", "prototypes/todo/index.html"))
        self.assertTrue(data_path("workspace-prototype-studio", "records/prototype-preview-profiles/todo.yaml"))
        self.assertTrue(data_path(self.owner, "reviews/improvement-candidates/sample.yaml"))
        self.assertTrue(data_path(self.owner, "reviews/after-action/sample.yaml"))
        self.assertTrue(data_path(self.owner, "docs/records/change-records/sample.md"))
        self.assertFalse(data_path(self.owner, "reviews/delegations/authority.yaml"))
        for path in ["scripts/prototype_preview.py", "packages/prototype_preview/runtime.py", "prototypes/todo/.git/config", "prototypes/todo/.gitattributes"]:
            self.assertFalse(data_path("workspace-prototype-studio", path))

    def test_complete_landing_output_advances_records_and_fixture_changes_without_code(self):
        self.owner = "workspace-prototype-studio"
        self.refresh()
        # All twelve outputs from the real Landing producer, not only the
        # previously missing .gitkeep. Owner schemas validate their contents;
        # this boundary proves data classification and real Git causality.
        outputs = [
            "prototypes.yaml",
            *[f"docs/prototypes/todo/{name}.md" for name in
              ["backlog", "brief", "change-log", "decision-log", "design-profile"]],
            "fixtures/prototypes/todo/.gitkeep",
            "prototypes/todo/README.md",
            "records/prototype-landings/todo/history/apply.json",
            "records/prototype-landings/todo/record.json",
            "records/prototype-landings/todo/validation-plan.yaml",
            "records/prototype-preview-profiles/todo.yaml",
        ]
        for name in outputs:
            self.write(name, "" if name.endswith(".gitkeep") else "synthetic owner record\n")
        landed = self.commit("owner Landing output")
        proof = self.refresh()
        self.assertEqual(proof["record_revision"], landed)
        self.assertEqual(proof["changed_path_count"], len(outputs))
        self.assertEqual(git(self.clone, "show", "HEAD:scripts/control.py"), "reviewed control code")
        self.write("fixtures/prototypes/todo/nested/tasks.json", "[]\n")
        fixture = self.commit("add bounded synthetic fixture")
        self.assertEqual(self.refresh()["record_revision"], fixture)
        self.write("fixtures/prototypes/todo/nested/tasks.json", '[{"done": true}]\n')
        updated = self.commit("update bounded synthetic fixture")
        self.assertEqual(self.refresh()["record_revision"], updated)
        (self.source / "fixtures/prototypes/todo/nested/tasks.json").unlink()
        deleted = self.commit("delete bounded synthetic fixture")
        self.assertEqual(self.refresh()["record_revision"], deleted)
        self.assertEqual(git(self.source, "status", "--porcelain"), "")

    def test_fixture_admission_does_not_admit_control_paths_modes_or_links(self):
        self.owner = "workspace-prototype-studio"
        for name in ["fixtures/control.json", "fixtures/prototypes/control.json",
                     "fixtures/other/todo/input.json", "fixtures/prototypes/todo/.git/config",
                     "fixtures/prototypes/todo/.gitattributes", "fixtures/prototypes/todo/.gitmodules",
                     "fixtures/prototypes/todo/../control.json"]:
            self.assertFalse(data_path(self.owner, name), name)
        for kind in ["executable", "symlink", "control-cochange"]:
            with self.subTest(kind=kind):
                accepted = self.refresh()["record_revision"]
                name = "fixtures/prototypes/todo/input.json"
                self.write(name, "[]\n")
                target = self.source / name
                if kind == "executable":
                    target.chmod(0o755)
                elif kind == "symlink":
                    target.unlink()
                    target.symlink_to("../../../scripts/control.py")
                else:
                    self.write("scripts/control.py", "unreviewed control change")
                rejected = self.commit("unaccepted fixture boundary delta")
                with self.assertRaises(RecordAuthorityError):
                    self.refresh()
                self.assertFalse((self.clone / ".git" / CHECKPOINT).exists())
                self.assertEqual(git(self.clone, "rev-parse", "HEAD"), accepted)
                git(self.source, "revert", "--no-edit", rejected)


if __name__ == "__main__":
    unittest.main()
