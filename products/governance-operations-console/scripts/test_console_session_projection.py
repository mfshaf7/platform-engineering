#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import pwd
import sys
import tempfile
import unittest

import yaml


MODULE_PATH = Path(__file__).with_name("console_session_projection.py")
SPEC = importlib.util.spec_from_file_location("console_session_projection", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
POLICY_PATH = MODULE_PATH.parents[1] / "session-projection-policy.yaml"


class ConsoleSessionProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="console-session-")
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.now = datetime(2026, 9, 27, 8, 0, tzinfo=timezone.utc)
        self.operator = pwd.getpwuid(os.geteuid()).pw_name
        source = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
        source["principals"] = {
            self.operator: {
                "kind": "human",
                "reference": "operator:workspace-owner",
                "display_name": self.operator,
                "roles": ["Operator"],
                "authorities": ["Workspace owner"],
            }
        }
        self.policy_path = self.root / "policy.yaml"
        self.policy_path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
        self.policy = MODULE.load_policy(self.policy_path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def manifest(self, *, session_id: str = "accepted-idea-delivery-operator-20260927T080000Z") -> Path:
        path = self.root / "current-session.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "lane": "dev-integration",
                    "profile_id": "accepted-idea-delivery",
                    "profile_lifecycle": "active",
                    "action": "up",
                    "operator": self.operator,
                    "session_id": session_id,
                    "session_started_at": "2026-09-27T08:00:00Z",
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        path.chmod(0o600)
        return path

    def test_policy_and_issue_publish_private_secret_free_projection(self) -> None:
        projection = self.root / "runtime" / "identity.json"
        receipt = self.root / "runtime" / "receipt.json"

        result = MODULE.issue(
            self.policy,
            self.manifest(),
            projection,
            receipt,
            now=self.now + timedelta(minutes=1),
        )

        value = json.loads(projection.read_text())
        MODULE.validate_projection(value)
        self.assertEqual(value["session"]["authenticationState"], "authenticated")
        self.assertEqual(value["source"]["mode"], "live")
        self.assertEqual(value["access"]["roles"], ["Operator"])
        self.assertEqual(projection.stat().st_mode & 0o777, 0o600)
        self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
        self.assertFalse(result["secret_values_embedded"])
        self.assertNotIn("token", json.dumps(value).lower())

    def test_same_session_is_idempotent_but_conflicting_session_is_denied(self) -> None:
        projection = self.root / "runtime" / "identity.json"
        first_receipt = self.root / "runtime" / "first.json"
        manifest = self.manifest()
        MODULE.issue(self.policy, manifest, projection, first_receipt, now=self.now)
        first = projection.read_bytes()
        MODULE.issue(
            self.policy,
            manifest,
            projection,
            self.root / "runtime" / "second.json",
            now=self.now + timedelta(minutes=5),
        )
        self.assertEqual(first, projection.read_bytes())

        conflicting = self.manifest(
            session_id="accepted-idea-delivery-operator-20260927T090000Z"
        )
        conflicting.write_text(
            conflicting.read_text().replace(
                "2026-09-27T08:00:00Z", "2026-09-27T09:00:00Z"
            )
        )
        conflicting.chmod(0o600)
        with self.assertRaisesRegex(MODULE.ProjectionError, "must be revoked"):
            MODULE.issue(
                self.policy,
                conflicting,
                projection,
                self.root / "runtime" / "third.json",
                now=self.now + timedelta(hours=1, minutes=1),
            )

    def test_revoke_removes_authority_and_allows_replacement(self) -> None:
        projection = self.root / "runtime" / "identity.json"
        MODULE.issue(
            self.policy,
            self.manifest(),
            projection,
            self.root / "runtime" / "issue.json",
            now=self.now,
        )
        result = MODULE.revoke(
            self.policy,
            projection,
            self.root / "runtime" / "revoke.json",
            now=self.now + timedelta(minutes=10),
        )
        value = json.loads(projection.read_text())
        self.assertEqual(value["session"]["authenticationState"], "unavailable")
        self.assertEqual(value["access"]["roles"], [])
        self.assertEqual(value["access"]["authorities"], [])
        self.assertIsNone(result["session_reference"])

        replacement = self.manifest(
            session_id="accepted-idea-delivery-operator-20260927T090000Z"
        )
        replacement.write_text(
            replacement.read_text().replace(
                "2026-09-27T08:00:00Z", "2026-09-27T09:00:00Z"
            )
        )
        replacement.chmod(0o600)
        MODULE.issue(
            self.policy,
            replacement,
            projection,
            self.root / "runtime" / "replacement.json",
            now=self.now + timedelta(hours=1, minutes=1),
        )
        self.assertEqual(
            json.loads(projection.read_text())["session"]["authenticationState"],
            "authenticated",
        )

    def test_expired_session_and_broad_manifest_permissions_fail_closed(self) -> None:
        manifest = self.manifest()
        with self.assertRaisesRegex(MODULE.ProjectionError, "expired"):
            MODULE.issue(
                self.policy,
                manifest,
                self.root / "runtime" / "identity.json",
                self.root / "runtime" / "receipt.json",
                now=self.now + timedelta(hours=9),
            )

        manifest.chmod(0o644)
        with self.assertRaisesRegex(MODULE.ProjectionError, "0600"):
            MODULE.load_session_manifest(manifest, self.policy)

    def test_current_projection_validation_rejects_later_expiry(self) -> None:
        manifest = MODULE.load_session_manifest(self.manifest(), self.policy)
        projection = MODULE.build_projection(self.policy, manifest, now=self.now)
        MODULE.validate_current_projection(
            projection,
            now=self.now + timedelta(hours=7),
        )
        with self.assertRaisesRegex(MODULE.ProjectionError, "has expired"):
            MODULE.validate_current_projection(
                projection,
                now=self.now + timedelta(hours=9),
            )

    def test_operator_profile_and_stopped_session_must_be_admitted(self) -> None:
        manifest = self.manifest()
        value = yaml.safe_load(manifest.read_text())
        value["operator"] = "someone-else"
        manifest.write_text(yaml.safe_dump(value), encoding="utf-8")
        manifest.chmod(0o600)
        with self.assertRaisesRegex(MODULE.ProjectionError, "not admitted"):
            MODULE.load_session_manifest(manifest, self.policy)

        value["operator"] = self.operator
        value["profile_id"] = "unreviewed-profile"
        manifest.write_text(yaml.safe_dump(value), encoding="utf-8")
        manifest.chmod(0o600)
        with self.assertRaisesRegex(MODULE.ProjectionError, "profile is not admitted"):
            MODULE.load_session_manifest(manifest, self.policy)

        value["profile_id"] = "accepted-idea-delivery"
        value["action"] = "down"
        manifest.write_text(yaml.safe_dump(value), encoding="utf-8")
        manifest.chmod(0o600)
        with self.assertRaisesRegex(MODULE.ProjectionError, "stopped"):
            MODULE.load_session_manifest(manifest, self.policy)


if __name__ == "__main__":
    unittest.main()
