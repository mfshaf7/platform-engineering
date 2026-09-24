#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("lifecycle.py")
SPEC = importlib.util.spec_from_file_location("lifecycle_context_composition", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class LifecycleContextCompositionTest(unittest.TestCase):
    def test_definition_preserves_approved_boundary(self) -> None:
        definition = MODULE.load_definition()
        self.assertEqual("platform-engineering", definition["owner_repo"])
        self.assertEqual("packet", definition["runtime_boundary"]["default_mode"])
        self.assertTrue(definition["runtime_boundary"]["console_calls_oos_only"])
        self.assertFalse(definition["runtime_boundary"]["stage_or_production_authority"])
        self.assertEqual("1167", definition["commissioning_proof"]["work_item_id"])

    def test_private_state_and_receipt_never_embed_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = {
                "operator": "mfshaf7",
                "generation": 1,
                "lifecycle": "active",
                "source_revisions": {"oos": "a" * 40, "cgg": "b" * 40},
                "secret_digest": "sha256:" + "c" * 64,
            }
            receipt = MODULE.record_receipt(root, "up", state, {"active": True})
            payload = json.loads(receipt.read_text())
            self.assertFalse(payload["secret_values_embedded"])
            self.assertNotIn("secret", json.dumps(payload["evidence"]).casefold())
            self.assertEqual(0o600, receipt.stat().st_mode & 0o777)

    def test_context_request_requires_explicit_raw_reason(self) -> None:
        packet = MODULE.context_request("packet-1")
        raw = MODULE.context_request("raw-1", mode="raw-fallback", reason="Controlled proof only.")
        self.assertEqual("packet", packet["mode"])
        self.assertIsNone(packet["fallback_reason"])
        self.assertEqual("raw-fallback", raw["mode"])
        self.assertEqual("Controlled proof only.", raw["fallback_reason"])

    def test_environment_sets_are_exact_and_separate(self) -> None:
        self.assertEqual(
            {"CGG_LIFECYCLE_BASE_URL", "CGG_LIFECYCLE_CALLER_ID", "CGG_LIFECYCLE_CALLER_SECRET"},
            MODULE.LIFECYCLE_ENVIRONMENTS["oos"],
        )
        self.assertEqual(
            {"CGG_LIFECYCLE_ALLOWED_CALLERS", "CGG_LIFECYCLE_CALLER_SHARED_SECRET"},
            MODULE.LIFECYCLE_ENVIRONMENTS["cgg"],
        )


if __name__ == "__main__":
    unittest.main()
