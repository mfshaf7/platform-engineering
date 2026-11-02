from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import console_dev_integration_profiles as profiles


class ProfileReads(unittest.TestCase):
    def setUp(self):
        self.policy = {"workspace_root": "/synthetic", "runtime_state_root": "/synthetic/runtime",
                       "security": {"decision_digest": "sha256:" + "a" * 64},
                       "platform_operation_provider": {"profile_id": "alpha", "operator_id": "operator:reviewer"}}
        self.entry = {"owner_repo": "owner", "lifecycle": "active", "lane_class": "integration-devint",
                      "profile_path": "dev-integration/profiles/alpha/profile.yaml", "summary": "Real registered profile",
                      "source_repos": ["owner"], "security_owner": "security-architecture",
                      "stage_handoff": {"required_checks": ["One owner check"]}}
        self.definition = {"profile_id": "alpha", "runtime": {"platform": "local-k3s", "state_model": "persistent"},
                           "commands": {"up": "secret-host-command"}, "private_key": "must-not-project"}
        self.calls = []

    def reader(self, root, owner, path):
        self.calls.append((owner, path))
        if path.endswith("developer-integration-profiles.yaml"):
            return {"profiles": {"alpha": deepcopy(self.entry), "beta": {**self.entry, "profile_path": "beta.yaml"}}}, "a" * 40
        if path.endswith("repos.yaml"):
            return {"repos": {"owner": {"lifecycle": "active"}, "retired": {"lifecycle": "retired"}}}, "a" * 40
        return {**self.definition, "profile_id": "beta" if path == "beta.yaml" else "alpha"}, "b" * 40

    def test_registry_pages_do_not_execute_runtime_and_missing_support_stays_unknown(self):
        with patch.object(profiles.subprocess, "run", side_effect=AssertionError("no runtime command")):
            result = profiles.read_profiles(self.policy, query={"limit": "1"}, reader=self.reader)
        self.assertEqual(result["page"], {"offset": 0, "limit": 1, "total": 2, "next_offset": 1})
        row = result["profiles"][0]
        self.assertEqual(row["runtime"]["observation"]["state"], "unknown")
        self.assertIsNone(row["persistence"])
        self.assertIsNone(row["expected_writes"])
        self.assertIsNone(row["security_triggers"])
        self.assertEqual(row["stage_handoff"]["result"], "unknown")
        self.assertEqual(result["request_options"]["owner_repos"], ["owner"])
        encoded = json.dumps(result)
        self.assertNotIn("must-not-project", encoded)
        self.assertNotIn("secret-host-command", encoded)
        self.assertNotIn("/synthetic", encoded)
        self.assertEqual(len(self.calls), 3)

    def test_filtered_detail_reads_only_selected_owner(self):
        result = profiles.read_profiles(self.policy, query={"profile_id": "beta"}, reader=self.reader)
        self.assertEqual([x["profile_id"] for x in result["profiles"]], ["beta"])
        self.assertEqual(len(self.calls), 3)

    def test_pagination_and_unknown_query_are_rejected_before_owner_read(self):
        for query in ({"limit": "1000"}, {"offset": "-1"}, {"shell": "id"}, {"q": "x" * 201}):
            with self.assertRaises(profiles.ProfileReadError):
                profiles.read_profiles(self.policy, query=query, reader=self.reader)
        self.assertEqual(self.calls, [])

    def test_wrong_owner_identity_never_adopts_another_profile(self):
        self.definition["profile_id"] = "other"
        def reader(root, owner, path):
            if owner == "owner":
                return self.definition, "b" * 40
            return self.reader(root, owner, path)
        row = profiles.read_profiles(self.policy, query={"profile_id": "alpha"}, reader=reader)["profiles"][0]
        self.assertIsNone(row["runtime"]["platform"])
        self.assertIn("Owner profile definition is unavailable.", row["gaps"])

    def test_registry_change_during_read_fails_closed(self):
        def reader(root, owner, path):
            doc, revision = self.reader(root, owner, path)
            return doc, "c" * 40 if path.endswith("repos.yaml") else revision
        with self.assertRaisesRegex(profiles.ProfileReadError, "changed during"):
            profiles.read_profiles(self.policy, reader=reader)

    def test_runtime_observation_requires_current_boot_receipt_and_security_binding(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "receipts").mkdir()
            receipt = root / "receipts/status.json"
            digest = self.policy["security"]["decision_digest"]
            value = {"artifact_type": "governance-console-complete-runtime-receipt", "security": {"decision_digest": digest},
                     "recorded_at": now.isoformat(), "proof": {"core_online": True, "secret": "not-public"}}
            value["content_digest"] = "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            receipt.write_text(json.dumps(value))
            marker = {"boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                      "core_receipt": str(receipt), "security_decision_digest": digest}
            (root / "core-online.json").write_text(json.dumps(marker))
            policy = {**self.policy, "runtime_state_root": str(root)}
            self.assertEqual(profiles._runtime_observation(policy, "alpha", now)["state"], "running")
            self.assertEqual(profiles._runtime_observation(policy, "alpha", now + timedelta(minutes=3))["state"], "unknown")
            self.assertEqual(profiles._runtime_observation(policy, "beta", now)["state"], "unknown")
            marker["boot_id"] = "old-boot"
            (root / "core-online.json").write_text(json.dumps(marker))
            self.assertEqual(profiles._runtime_observation(policy, "alpha", now)["state"], "unknown")


if __name__ == "__main__":
    unittest.main()
