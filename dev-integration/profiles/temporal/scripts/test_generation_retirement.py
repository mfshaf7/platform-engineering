#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
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
        self.receipt_private_key = self.root / "receipt-private.pem"
        self.receipt_public_key = self.root / "receipt-public.pem"
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "ED25519",
                "-out",
                str(self.receipt_private_key),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "openssl",
                "pkey",
                "-in",
                str(self.receipt_private_key),
                "-pubout",
                "-out",
                str(self.receipt_public_key),
            ],
            check=True,
            capture_output=True,
        )

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
            "--receipt-key-id",
            "oos-retirement-receipt-test",
            "--receipt-public-key",
            str(self.receipt_public_key),
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
            "retirement_started_at": timestamp(self.issued_at + timedelta(seconds=1)),
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
            "start_registry": {
                **manifest["start_registry"],
                "seal_ref": manifest["retirement_id"],
                "seal_authorization_digest": retirement_digest,
                "sealed_at": timestamp(
                    self.issued_at + timedelta(milliseconds=500)
                ),
                "result_digest": f"sha256:{'c' * 64}",
                "registered_workflow_count": 3,
                "matched_execution_count": 2,
                "uncommitted_registration_count": 1,
            },
            "cancel_signal_target_count": 2,
            "terminal_projection_count": 2,
            "outcome": "retired",
            "recorded_at": timestamp(datetime.now(timezone.utc)),
        }

    def attest_receipt(self, receipt: dict) -> dict:
        payload = dict(receipt)
        payload.pop("attestation", None)
        payload_raw = json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode()
        payload_path = self.root / "receipt-payload.json"
        signature_path = self.root / "receipt-signature.bin"
        payload_path.write_bytes(payload_raw)
        subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-sign",
                "-inkey",
                str(self.receipt_private_key),
                "-rawin",
                "-in",
                str(payload_path),
                "-out",
                str(signature_path),
            ],
            check=True,
            capture_output=True,
        )
        return {
            **payload,
            "attestation": {
                "algorithm": "Ed25519",
                "issuer": "operator-orchestration-service",
                "key_id": "oos-retirement-receipt-test",
                "payload_digest": digest(payload_raw),
                "signature": base64.b64encode(signature_path.read_bytes()).decode(),
            },
        }

    def verify(
        self,
        receipt: dict,
        retirement_digest: str,
        *,
        attest: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        receipt_path = self.root / "receipt.json"
        value = self.attest_receipt(receipt) if attest else receipt
        receipt_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
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
                "--receipt-public-key",
                str(self.receipt_public_key),
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
        self.assertEqual(
            manifest["start_registry"],
            {
                "task_queue": (
                    "oos.generation-start-registry.v1."
                    f"{self.activation_digest.removeprefix('sha256:')}"
                ),
                "workflow_id": (
                    "oos:generation-start-registry:v1:"
                    f"{self.activation_digest.removeprefix('sha256:')}"
                ),
                "workflow_type": "generationStartRegistryV1",
            },
        )
        self.assertEqual(stat.S_IMODE(self.retirement_path.stat().st_mode), 0o600)
        result = self.verify(self.receipt(manifest, retirement_digest), retirement_digest)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["decision"], "accepted")
        self.assertEqual(summary["start_registry"]["registered_workflow_count"], 3)

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
        receipt["start_registry"]["uncommitted_registration_count"] = 0
        incomplete = self.verify(receipt, retirement_digest)
        self.assertEqual(incomplete.returncode, 2)
        self.assertIn("cover every registration", incomplete.stderr)

        receipt = self.receipt(manifest, retirement_digest)
        receipt["start_registry"]["seal_ref"] = (
            "platform-engineering://retirement/validation-readiness-run/v1/dev-integration/other"
        )
        wrong_seal = self.verify(receipt, retirement_digest)
        self.assertEqual(wrong_seal.returncode, 2)
        self.assertIn("start_registry.seal_ref", wrong_seal.stderr)

        receipt = self.receipt(manifest, retirement_digest)
        receipt["start_registry"]["sealed_at"] = timestamp(
            self.issued_at - timedelta(milliseconds=1)
        )
        early_seal = self.verify(receipt, retirement_digest)
        self.assertEqual(early_seal.returncode, 2)
        self.assertIn("inside its seal authorization", early_seal.stderr)

        receipt = self.receipt(manifest, retirement_digest)
        receipt["cancel_signal_target_count"] = 3
        excess_cancellation = self.verify(receipt, retirement_digest)
        self.assertEqual(excess_cancellation.returncode, 2)
        self.assertIn("exceed matched", excess_cancellation.stderr)

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

        receipt = self.receipt(manifest, retirement_digest)
        receipt["retirement_started_at"] = manifest["expires_at"]
        unauthorized = self.verify(receipt, retirement_digest)
        self.assertEqual(unauthorized.returncode, 2)
        self.assertIn("within the manifest lifetime", unauthorized.stderr)

        receipt = self.receipt(manifest, retirement_digest)
        receipt["retirement_started_at"] = timestamp(
            self.issued_at + timedelta(seconds=281)
        )
        stale_at_start = self.verify(receipt, retirement_digest)
        self.assertEqual(stale_at_start.returncode, 2)
        self.assertIn("old at retirement start", stale_at_start.stderr)

    def test_issue_refuses_to_overwrite_activation_evidence(self) -> None:
        command = self.issue_command()
        command[command.index("--output") + 1] = str(self.activation_path)
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("must not overwrite", result.stderr)

    def test_verify_rejects_registry_identity_outside_activation_generation(self) -> None:
        manifest, _ = self.issue()
        manifest["start_registry"]["task_queue"] = (
            f"oos.generation-start-registry.v1.{'d' * 64}"
        )
        retirement_raw = (json.dumps(manifest, indent=2) + "\n").encode()
        self.retirement_path.write_bytes(retirement_raw)
        retirement_digest = digest(retirement_raw)

        result = self.verify(
            self.receipt(manifest, retirement_digest), retirement_digest
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("start_registry.task_queue", result.stderr)

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

    def test_verify_accepts_completion_after_authorization_expiry(self) -> None:
        manifest, _ = self.issue()
        manifest["expires_at"] = timestamp(self.issued_at + timedelta(seconds=10))
        retirement_raw = (json.dumps(manifest, indent=2) + "\n").encode()
        self.retirement_path.write_bytes(retirement_raw)
        retirement_digest = digest(retirement_raw)
        receipt = self.receipt(manifest, retirement_digest)
        receipt["retirement_started_at"] = timestamp(
            self.issued_at + timedelta(seconds=1)
        )

        result = self.verify(receipt, retirement_digest)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_verify_rejects_a_forged_receipt(self) -> None:
        manifest, retirement_digest = self.issue()
        receipt = self.attest_receipt(self.receipt(manifest, retirement_digest))
        receipt["terminal_projection_count"] = 1
        payload = dict(receipt)
        payload.pop("attestation")
        payload_raw = json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode()
        receipt["attestation"]["payload_digest"] = digest(payload_raw)

        result = self.verify(receipt, retirement_digest, attest=False)

        self.assertEqual(result.returncode, 2)
        self.assertIn("signature verification failed", result.stderr)

    def test_verify_rejects_registry_counts_above_generation_capacity(self) -> None:
        manifest, retirement_digest = self.issue()
        receipt = self.receipt(manifest, retirement_digest)
        receipt["start_registry"]["registered_workflow_count"] = 513
        receipt["start_registry"]["matched_execution_count"] = 513
        receipt["start_registry"]["uncommitted_registration_count"] = 0
        receipt["terminal_projection_count"] = 513

        result = self.verify(receipt, retirement_digest)

        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot exceed 512 registrations", result.stderr)

    def test_refreshed_manifest_resumes_the_original_registry_seal(self) -> None:
        initial_manifest, initial_digest = self.issue()
        initial_path = self.root / "initial-retirement.json"
        initial_path.write_bytes(self.retirement_path.read_bytes())
        command = self.issue_command(
            "--resume-seal-manifest",
            str(initial_path),
            "--resume-seal-digest",
            initial_digest,
        )
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        refreshed_digest = json.loads(result.stdout)["retirement_evidence_digest"]
        refreshed_manifest = json.loads(
            self.retirement_path.read_text(encoding="utf-8")
        )
        self.assertNotEqual(refreshed_digest, initial_digest)
        self.assertEqual(
            refreshed_manifest["registry_seal_resume"],
            {
                "retirement_evidence_digest": initial_digest,
                "issued_at": initial_manifest["issued_at"],
                "expires_at": initial_manifest["expires_at"],
            },
        )
        receipt = self.receipt(refreshed_manifest, refreshed_digest)
        receipt["start_registry"]["seal_authorization_digest"] = initial_digest

        verification = self.verify(receipt, refreshed_digest)

        self.assertEqual(verification.returncode, 0, verification.stderr)


if __name__ == "__main__":
    unittest.main()
