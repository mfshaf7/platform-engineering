#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("generation_retirement.py")


def digest(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def timestamp(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class GenerationRetirementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        now = datetime.now(timezone.utc)
        self.issued_at = now - timedelta(seconds=30)
        self.expires_at = now + timedelta(minutes=10)
        self.activation_path = self.root / "activation.json"
        activation_raw = (
            json.dumps(self.activation_manifest(), indent=2, sort_keys=True) + "\n"
        ).encode()
        self.activation_path.write_bytes(activation_raw)
        self.activation_digest = digest(activation_raw)
        self.retirement_path = self.root / "retirement.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def activation_manifest(self) -> dict:
        return {
            "schema_version": 1,
            "manifest_id": "platform-engineering://activation/validation-readiness-run/v1/dev-integration",
            "definition_id": "validation-readiness-run",
            "definition_version": 1,
            "environment": "dev-integration",
            "profile_id": "temporal",
            "profile_lifecycle": "active",
            "issued_at": "2026-07-31T00:00:00.000Z",
            "expires_at": "2026-08-31T00:00:00.000Z",
            "issued_by": "platform-engineering",
            "decision": "accepted",
            "decision_ref": "platform-engineering://decisions/temporal-dev-integration-activation",
            "temporal_target": {
                "address": "temporal-frontend.temporal.svc:7233",
                "namespace": "default",
                "identities": {
                    "api": "operator-orchestration-service-api",
                    "workflow_worker": "oos-workflow-worker",
                },
            },
            "evidence": {
                gate: {
                    "artifact_path": f"records/{gate}.json",
                    "artifact_digest": f"sha256:{'a' * 64}",
                }
                for gate in (
                    "activity-idempotency-tested",
                    "contract-valid",
                    "deterministic-replay-tested",
                    "dev-integration-profile-active",
                    "failure-and-control-tested",
                    "implementation-reviewed",
                    "platform-runtime-accepted",
                    "rollback-and-suspension-proven",
                    "security-review-accepted",
                    "source-projection-verified",
                )
            },
        }

    def issue_command(self, *extra: str) -> list[str]:
        return [
            sys.executable,
            str(SCRIPT),
            "issue",
            "--activation-manifest",
            str(self.activation_path),
            "--activation-digest",
            self.activation_digest,
            "--retirement-id",
            "platform-engineering://retirement/validation-readiness-run/v1/dev-integration/test",
            "--reason-ref",
            "platform-engineering://decisions/temporal-generation-retirement/test",
            "--issued-at",
            timestamp(self.issued_at),
            "--expires-at",
            timestamp(self.expires_at),
            "--start-ingress-active-replicas",
            "0",
            "--in-flight-starts",
            "0",
            "--start-ingress-observed-at",
            timestamp(self.issued_at - timedelta(seconds=20)),
            "--start-ingress-evidence-ref",
            "platform-engineering://evidence/oos-start-ingress-drained/test",
            "--workflow-poller-active-replicas",
            "0",
            "--workflow-poller-observed-at",
            timestamp(self.issued_at - timedelta(seconds=10)),
            "--workflow-poller-evidence-ref",
            "platform-engineering://evidence/oos-workflow-poller-drained/test",
            "--output",
            str(self.retirement_path),
            *extra,
        ]

    def issue(self) -> tuple[dict, str]:
        result = subprocess.run(
            self.issue_command(), check=True, capture_output=True, text=True
        )
        summary = json.loads(result.stdout)
        manifest = json.loads(self.retirement_path.read_text(encoding="utf-8"))
        return manifest, summary["retirement_evidence_digest"]

    def receipt(self, manifest: dict, retirement_digest: str) -> dict:
        return {
            "schema_version": 1,
            "receipt_id": "receipt:generation-retirement:test",
            "retirement_id": manifest["retirement_id"],
            "retirement_evidence_digest": retirement_digest,
            "activation_evidence_digest": manifest["activation_evidence_digest"],
            "activation_manifest_ref": manifest["activation_manifest_ref"],
            "definition_id": manifest["definition_id"],
            "definition_version": manifest["definition_version"],
            "environment": manifest["environment"],
            "workflow_task_queue": manifest["workflow_task_queue"],
            "temporal_target": {
                "address": manifest["temporal_target"]["address"],
                "namespace": manifest["temporal_target"]["namespace"],
            },
            "start_ingress_evidence_ref": manifest["start_ingress"]["evidence_ref"],
            "poller_evidence_ref": manifest["workflow_poller"]["evidence_ref"],
            "ordinary_poller_stopped": True,
            "drain_cycle_count": 1,
            "cancel_signal_target_count": 2,
            "terminal_projection_count": 2,
            "post_stop_empty_scans": 7,
            "outcome": "retired",
            "recorded_at": timestamp(datetime.now(timezone.utc)),
        }

    def verify(self, receipt: dict, retirement_digest: str) -> subprocess.CompletedProcess[str]:
        receipt_path = self.root / "receipt.json"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "verify-receipt",
                "--retirement-manifest",
                str(self.retirement_path),
                "--retirement-digest",
                retirement_digest,
                "--receipt",
                str(receipt_path),
            ],
            capture_output=True,
            text=True,
        )

    def test_issue_and_verify_exact_retirement_evidence(self) -> None:
        manifest, retirement_digest = self.issue()
        self.assertEqual(
            manifest["workflow_task_queue"],
            f"oos.validation-readiness-run.v1.{self.activation_digest.removeprefix('sha256:')}",
        )
        self.assertEqual(stat.S_IMODE(self.retirement_path.stat().st_mode), 0o600)
        result = self.verify(self.receipt(manifest, retirement_digest), retirement_digest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["decision"], "accepted")

    def test_issue_rejects_nonzero_ingress_or_poller(self) -> None:
        replacements = [
            ("--start-ingress-active-replicas", "1"),
            ("--in-flight-starts", "1"),
            ("--workflow-poller-active-replicas", "1"),
        ]
        for option, value in replacements:
            with self.subTest(option=option):
                command = self.issue_command()
                command[command.index(option) + 1] = value
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("must be zero", result.stderr)

    def test_verify_rejects_tampered_or_incomplete_receipt(self) -> None:
        manifest, retirement_digest = self.issue()
        receipt = self.receipt(manifest, retirement_digest)
        receipt["terminal_projection_count"] = 1
        mismatch = self.verify(receipt, retirement_digest)
        self.assertEqual(mismatch.returncode, 2)
        self.assertIn("terminal projection", mismatch.stderr)

        receipt = self.receipt(manifest, retirement_digest)
        receipt["post_stop_empty_scans"] = 6
        incomplete = self.verify(receipt, retirement_digest)
        self.assertEqual(incomplete.returncode, 2)
        self.assertIn("post_stop_empty_scans", incomplete.stderr)

        receipt = self.receipt(manifest, retirement_digest)
        receipt["ordinary_poller_stopped"] = 1
        wrong_type = self.verify(receipt, retirement_digest)
        self.assertEqual(wrong_type.returncode, 2)
        self.assertIn("ordinary_poller_stopped", wrong_type.stderr)

        receipt = self.receipt(manifest, retirement_digest)
        receipt["recorded_at"] = timestamp(self.issued_at - timedelta(seconds=1))
        stale = self.verify(receipt, retirement_digest)
        self.assertEqual(stale.returncode, 2)
        self.assertIn("must not precede", stale.stderr)

    def test_issue_refuses_to_overwrite_activation_evidence(self) -> None:
        command = self.issue_command()
        command[command.index("--output") + 1] = str(self.activation_path)
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("must not overwrite", result.stderr)

    def test_issue_rejects_stale_drain_evidence_or_long_authorization(self) -> None:
        stale = self.issue_command()
        stale[stale.index("--start-ingress-observed-at") + 1] = timestamp(
            self.issued_at - timedelta(seconds=301)
        )
        stale_result = subprocess.run(stale, capture_output=True, text=True)
        self.assertEqual(stale_result.returncode, 2)
        self.assertIn("no more than 300 seconds old", stale_result.stderr)

        long_lived = self.issue_command()
        long_lived[long_lived.index("--expires-at") + 1] = timestamp(
            self.issued_at + timedelta(seconds=901)
        )
        lifetime_result = subprocess.run(long_lived, capture_output=True, text=True)
        self.assertEqual(lifetime_result.returncode, 2)
        self.assertIn("must not exceed 900 seconds", lifetime_result.stderr)

    def test_verify_rejects_future_receipt_time(self) -> None:
        manifest, retirement_digest = self.issue()
        receipt = self.receipt(manifest, retirement_digest)
        receipt["recorded_at"] = timestamp(
            datetime.now(timezone.utc) + timedelta(minutes=1)
        )
        result = self.verify(receipt, retirement_digest)
        self.assertEqual(result.returncode, 2)
        self.assertIn("must not be in the future", result.stderr)


if __name__ == "__main__":
    unittest.main()
