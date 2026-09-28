#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("console_cross_domain_activation.py")
SPEC = importlib.util.spec_from_file_location("console_cross_domain_activation", SCRIPT)
assert SPEC and SPEC.loader
activation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(activation)


class CrossDomainActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = activation.load_policy()

    def test_policy_pins_two_distinct_owner_sources(self) -> None:
        owners = self.policy["owners"]
        self.assertEqual(owners["oos"]["repo"], "operator-orchestration-service")
        self.assertEqual(owners["wgcf"]["repo"], "workspace-governance-control-fabric")
        self.assertNotEqual(owners["oos"]["local_port"], owners["wgcf"]["local_port"])
        self.assertEqual(len(owners["oos"]["revision"]), 40)
        self.assertEqual(len(owners["wgcf"]["revision"]), 40)

    def test_units_keep_credentials_in_private_environment_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            units = root / "units"
            console = root / "console"
            console.mkdir()
            env_file = root / "private" / "console.env"
            env_file.parent.mkdir()
            env_file.write_text("OOS_CALLER_SECRET=secret\n", encoding="utf-8")
            with (
                patch.object(activation, "UNIT_ROOT", units),
                patch.object(activation, "repo_path", return_value=console),
                patch.object(activation, "run"),
                patch.object(activation, "operator", return_value="operator"),
                patch.object(
                    activation.shutil,
                    "which",
                    side_effect=lambda command: f"/tools/{command}",
                ),
            ):
                activation.write_units(self.policy, env_file)
            console_unit = (units / activation.unit_name("console")).read_text(encoding="utf-8")
            self.assertIn(f"EnvironmentFile={env_file}", console_unit)
            self.assertIn("ExecStart=/tools/npm run dev", console_unit)
            self.assertNotIn("secret", console_unit)
            self.assertIn("Wants=governance-console-cross-domain-oos.service", console_unit)

    def test_receipt_contains_source_proof_but_no_credentials(self) -> None:
        activity = {
            "mode": "live",
            "status": "current",
            "sources": [
                {"owner": "operator-orchestration-service", "state": "current"},
                {"owner": "workspace-governance-control-fabric", "state": "current"},
            ],
            "events": [{"eventId": "one"}],
            "observedAt": "2026-09-28T00:00:00Z",
            "truncated": False,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(activation, "RECEIPT_ROOT", Path(temp_dir)),
                patch.object(activation, "operator", return_value="operator"),
            ):
                path = activation.receipt("status", self.policy, activity)
            value = json.loads(path.read_text(encoding="utf-8"))
            serialized = json.dumps(value).casefold()
            self.assertEqual(value["result"], "succeeded")
            self.assertEqual(value["live_proof"]["event_count"], 1)
            self.assertNotIn("caller_secret", serialized)
            self.assertNotIn("token_urlsafe", serialized)

    def test_live_proof_rejects_fixture_authority(self) -> None:
        fixture = {
            "mode": "live",
            "status": "current",
            "sources": [
                {"owner": "operator-orchestration-service", "state": "current"},
                {"owner": "workspace-governance-control-fabric", "state": "current"},
            ],
            "events": [{"source": {"mode": "prototype-local"}}],
        }
        with (
            patch.object(activation, "http_json", return_value=fixture),
            patch.object(activation.time, "sleep"),
            patch.object(activation.time, "monotonic", side_effect=[0, 1, 181]),
        ):
            with self.assertRaisesRegex(activation.ActivationError, "fixture authority"):
                activation.wait_for_activity(self.policy)


if __name__ == "__main__":
    unittest.main()
