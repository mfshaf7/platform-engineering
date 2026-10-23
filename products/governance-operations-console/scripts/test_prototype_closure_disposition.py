from __future__ import annotations

import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml
import prototype_closure_disposition as disposition


class DispositionTests(unittest.TestCase):
    """Real Git causality; synthetic owner checkpoint and Preview adapter."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        self.root = self.state / "record-authority/workspace-prototype-studio"
        self.root.mkdir(parents=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Synthetic owner")
        self.git("config", "user.email", "owner@example.invalid")
        self.write("contracts/prototype-closure/prototype-closure-history-event.schema.json",
            json.dumps({"type": "object", "required": ["event_type", "prototype_id"]}))
        self.write("prototypes.yaml", "prototypes: []\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Accepted source")
        self.base = self.git("rev-parse", "HEAD")
        self.event_id = "prototype-closure:sample-tool:0002"
        self.event_path = "records/prototype-closure/sample-tool/history/0002.json"
        self.event = {"event_id": self.event_id, "prototype_id": "sample-tool",
            "event_type": "source-graduated", "observed_lifecycle": "graduated",
            "observed_source_custody": "dedicated-owner-repo", "expected_source_revision": self.base}
        ref = "record://prototype-closure/sample-tool/history/" + self.event_id
        self.item = {"id": "sample-tool", "lifecycle": "graduated",
            "source_custody": "dedicated-owner-repo", "closure_event_ref": ref, "graduation_ref": ref}
        self.write(self.event_path, json.dumps(self.event))
        self.write("prototypes.yaml", yaml.safe_dump({"prototypes": [self.item]}))
        self.commit("Merged graduation")
        self.merged = self.git("rev-parse", "HEAD")
        self.policy = {"runtime_state_root": str(self.state),
            "record_authority": {"enabled": True},
            "security": {"reviewed_revisions": {"workspace-prototype-studio": self.base}}}
        self.lookup = {"prototype_id": "sample-tool", "source_event_ref": self.event_id,
            "merged_source_revision": self.merged}
        checkpoint = patch.object(disposition.authority, "snapshot_status",
            side_effect=lambda *a, **k: {"record_revision": self.git("rev-parse", "HEAD")})
        self.checkpoint = checkpoint.start()
        self.addCleanup(checkpoint.stop)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
            capture_output=True, text=True).stdout.strip()

    def write(self, path, value):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(value)

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-qm", message)

    def test_actual_event_merge_survives_unrelated_later_metadata_commit(self):
        self.write("other-metadata.txt", "Unrelated source data")
        self.commit("Later metadata")
        self.assertEqual(disposition.absent(self.policy, self.lookup),
            {"prototype_id": "sample-tool", "merged_source_revision": self.merged, "disposition": "absent"})
        wrong = {**self.lookup, "merged_source_revision": self.git("rev-parse", "HEAD")}
        with self.assertRaisesRegex(disposition.DispositionError, "did not introduce"):
            disposition.absent(self.policy, wrong)

    def test_changed_event_or_current_custody_never_reuses_old_absence(self):
        self.event["observed_source_custody"] = "shared-owner-repo"
        self.write(self.event_path, json.dumps(self.event))
        self.commit("Changed event")
        with self.assertRaisesRegex(disposition.DispositionError, "event changed"):
            disposition.absent(self.policy, self.lookup)
        self.write(self.event_path, json.dumps({**self.event, "observed_source_custody": "dedicated-owner-repo"}))
        self.item["lifecycle"] = "exploring"
        self.write("prototypes.yaml", yaml.safe_dump({"prototypes": [self.item]}))
        self.commit("Reopened source")
        with self.assertRaisesRegex(disposition.DispositionError, "custody"):
            disposition.absent(self.policy, self.lookup)

    def test_normal_merge_commit_is_accepted_but_its_feature_head_is_not_the_main_merge(self):
        self.git("checkout", "-qb", "reviewed-source", self.base)
        self.write(self.event_path, json.dumps(self.event))
        self.write("prototypes.yaml", yaml.safe_dump({"prototypes": [self.item]}))
        self.commit("Reviewed graduation")
        source_head = self.git("rev-parse", "HEAD")
        self.git("checkout", "-qb", "canonical-main", self.base)
        self.git("merge", "--no-ff", "reviewed-source", "-m", "Merge reviewed source")
        merged = self.git("rev-parse", "HEAD")
        result = disposition.absent(self.policy, {**self.lookup, "merged_source_revision": merged})
        self.assertEqual(result["merged_source_revision"], merged)
        with self.assertRaisesRegex(disposition.DispositionError, "canonical main"):
            disposition.absent(self.policy, {**self.lookup, "merged_source_revision": source_head})

    def test_unavailable_checkpoint_and_caller_selected_disposition_fail_closed(self):
        for key, value in [("disposition", "absent"), ("profile_path", "/tmp/untrusted")]:
            with self.assertRaises(disposition.DispositionError):
                disposition.absent(self.policy, {**self.lookup, key: value})
        self.checkpoint.side_effect = disposition.authority.RecordAuthorityError("stale")
        with self.assertRaises(disposition.authority.RecordAuthorityError):
            disposition.absent(self.policy, self.lookup)

    def test_existing_owner_identifier_vocabulary_is_preserved(self):
        slug = "sample.tool_v2"
        event_id = f"prototype-closure:{slug}:0001"
        event = {**self.event, "event_id": event_id, "prototype_id": slug,
            "expected_source_revision": self.merged}
        ref = f"record://prototype-closure/{slug}/history/{event_id}"
        item = {**self.item, "id": slug, "closure_event_ref": ref, "graduation_ref": ref}
        self.write(f"records/prototype-closure/{slug}/history/0001.json", json.dumps(event))
        self.write("prototypes.yaml", yaml.safe_dump({"prototypes": [self.item, item]}))
        self.commit("Graduate existing owner identifier")
        lookup = {"prototype_id": slug, "source_event_ref": event_id,
            "merged_source_revision": self.git("rev-parse", "HEAD")}
        self.assertEqual(disposition.absent(self.policy, lookup)["prototype_id"], slug)

    def test_retained_unmanaged_or_stale_process_state_is_never_absence(self):
        path = self.state / "prototype-preview/older-profile/state.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"prototype_id": "prototype:sample-tool", "pid": 999999}))
        with self.assertRaisesRegex(disposition.DispositionError, "retains process state"):
            disposition.absent(self.policy, self.lookup)

    def test_native_preview_identity_and_orphan_listener_are_checked(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        profile = {"prototype_id": "prototype:sample-tool",
            "runtime": {"bind_host": "127.0.0.1", "port": port}}
        self.write("records/prototype-preview-profiles/sample-tool.yaml", yaml.safe_dump(profile))
        self.commit("Declare Preview")
        projection = {"prototype_id": "prototype:sample-tool",
            "source_revision": self.git("rev-parse", "HEAD"), "runtime_state": "stopped",
            "endpoint": None, "instance_id": None}
        real_run = subprocess.run
        def owner_read(command, **kwargs):
            if command[0] == "git":
                return real_run(command, **kwargs)
            self.assertEqual(command[-3:], ["status", "--profile", str(self.root / "records/prototype-preview-profiles/sample-tool.yaml")])
            return subprocess.CompletedProcess(command, 0, json.dumps(projection), "")
        with patch.object(disposition.subprocess, "run", side_effect=owner_read):
            self.assertEqual(disposition.absent(self.policy, self.lookup)["disposition"], "absent")
            projection["runtime_state"] = "running"
            with self.assertRaisesRegex(disposition.DispositionError, "stopped incubation"):
                disposition.absent(self.policy, self.lookup)
            projection["runtime_state"] = "stopped"
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", port))
                listener.listen()
                with self.assertRaisesRegex(disposition.DispositionError, "occupied"):
                    disposition.absent(self.policy, self.lookup)


if __name__ == "__main__":
    unittest.main()
