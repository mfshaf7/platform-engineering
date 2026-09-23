#!/usr/bin/env python3
"""Tests for Platform-owned Prototype Closure runtime evidence."""

from __future__ import annotations

import json
import io
from pathlib import Path
import stat
import tempfile
import unittest
from contextlib import redirect_stdout

import prototype_closure_evidence as module


class PrototypeClosureEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "platform-evidence.json"
        self.path.write_text('{"schema_version":1,"records":[]}\n')
        self.path.chmod(0o600)

    def run_command(self, arguments: list[str]) -> int:
        with redirect_stdout(io.StringIO()):
            return module.main(arguments)

    def test_records_owner_and_post_merge_evidence_idempotently(self) -> None:
        revision = "a" * 40
        owner_args = [
            "--evidence-file", str(self.path),
            "record-owner-evidence",
            "--field", "runtime_disposition_proof_ref",
            "--prototype-id", "sample-tool",
            "--subject-ref", "plan://runtime/sample-tool",
            "--source-revision", revision,
        ]
        self.assertEqual(0, self.run_command(owner_args))
        first = json.loads(self.path.read_text())["records"][0]
        self.assertEqual(
            "sha256:67e1ea12fe8e69762591dd3f3f5dfcbf84511a72d122b9d0ff7b43cf35c2cf0e",
            first["digest"],
        )
        self.assertTrue(first["ref"].endswith(first["digest"][7:]))
        self.assertEqual(
            first["digest"],
            module.canonical_digest(
                {key: value for key, value in first.items() if key not in {"ref", "digest"}}
            ),
        )
        self.assertEqual(0, self.run_command(owner_args))
        self.assertEqual(1, len(json.loads(self.path.read_text())["records"]))

        self.assertEqual(
            0,
            self.run_command(
                [
                    "--evidence-file", str(self.path),
                    "record-post-merge-disposition",
                    "--prototype-id", "sample-tool",
                    "--merged-source-revision", revision,
                    "--disposition", "absent",
                ]
            ),
        )
        value = json.loads(self.path.read_text())
        self.assertEqual(2, len(value["records"]))
        self.assertEqual(0, stat.S_IMODE(self.path.stat().st_mode) & 0o077)

    def test_rejects_unsafe_file_and_unbounded_input(self) -> None:
        self.path.chmod(0o644)
        self.assertEqual(
            1,
            self.run_command(
                [
                    "--evidence-file", str(self.path),
                    "record-post-merge-disposition",
                    "--prototype-id", "sample-tool",
                    "--merged-source-revision", "a" * 40,
                    "--disposition", "absent",
                ]
            ),
        )
        self.path.chmod(0o600)
        self.assertEqual(
            1,
            self.run_command(
                [
                    "--evidence-file", str(self.path),
                    "record-owner-evidence",
                    "--field", "runtime_disposition_plan_ref",
                    "--prototype-id", "INVALID",
                    "--subject-ref", "plan://runtime/sample-tool",
                    "--source-revision", "a" * 40,
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
