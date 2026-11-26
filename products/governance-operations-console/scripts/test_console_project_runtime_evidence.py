"""Exercise the receipt checks used by the named operating cases."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import console_project_runtime_evidence as evidence


class ProjectRuntimeEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = evidence.source_identity("a" * 40, "b" * 40)
        self.results = {}
        for required_scenarios in evidence.OBSERVATIONS.values():
            for scenario, expected in required_scenarios.items():
                self.results.setdefault(scenario, {"disposableNamespacesRemoved": True}).update(expected)

    def test_accepts_the_named_results_for_exact_owner_revisions(self):
        target = evidence.record_rehearsal(self.root, self.source, self.results)
        digest = json.loads(target.read_text())["content_digest"]
        for case in evidence.OBSERVATIONS:
            with self.subTest(case=case):
                self.assertEqual(evidence.verify_case(self.root, self.source, case), digest)

    def test_green_general_checks_do_not_create_a_case_receipt(self):
        with self.assertRaisesRegex(evidence.EvidenceError, "Run the isolated rehearsal"):
            evidence.verify_case(self.root, self.source, "retained-data")

    def test_receipt_from_a_different_revision_is_rejected(self):
        target = evidence.record_rehearsal(self.root, self.source, self.results)
        for platform_head, broker_head in (("c" * 40, "b" * 40), ("a" * 40, "c" * 40)):
            with self.subTest(platform_head=platform_head, broker_head=broker_head):
                mismatched_source = evidence.source_identity(platform_head, broker_head)
                wrong_target = self.root / evidence.receipt_name(mismatched_source)
                wrong_target.write_bytes(target.read_bytes())
                wrong_target.chmod(0o600)
                with self.assertRaisesRegex(evidence.EvidenceError, "different source revisions"):
                    evidence.verify_case(self.root, mismatched_source, "retained-data")

    def test_denies_tampering_and_incomplete_observations(self):
        without_data = deepcopy(self.results)
        without_data["retained_data"]["pairedApiReadSameData"] = False
        with self.assertRaisesRegex(evidence.EvidenceError, "pairedApiReadSameData"):
            evidence.record_rehearsal(self.root, self.source, without_data)
        target = evidence.record_rehearsal(self.root, self.source, self.results)
        receipt = json.loads(target.read_text())
        receipt["scenarios"]["retained_data"]["pairedApiReadSameData"] = False
        target.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(evidence.EvidenceError, "receipt has changed"):
            evidence.verify_case(self.root, self.source, "retained-data")

    def test_a_running_or_failed_rerun_replaces_the_preceding_pass(self):
        for state in ("running", "failed"):
            evidence.record_rehearsal(self.root, self.source, self.results)
            evidence.write_rehearsal(self.root, self.source, state, self.results)
            with self.assertRaisesRegex(evidence.EvidenceError, "has not completed"):
                evidence.verify_case(self.root, self.source, "retained-data")

    def test_reads_only_private_receipts(self):
        target = evidence.record_rehearsal(self.root, self.source, self.results)
        target.chmod(0o644)
        with self.assertRaisesRegex(evidence.EvidenceError, "private receipt custody"):
            evidence.verify_case(self.root, self.source, "retained-data")


if __name__ == "__main__":
    unittest.main()
