from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

import yaml

import model_profile_lifecycle as lifecycle


REPO_ROOT = Path(__file__).resolve().parents[1]
OOS_ROOT = Path(os.environ["OOS_REPO_ROOT"]) if os.environ.get("OOS_REPO_ROOT") else next(
    ancestor / "operator-orchestration-service"
    for ancestor in REPO_ROOT.parents
    if (ancestor / "operator-orchestration-service").is_dir()
)
PROFILE_ID = "delivery-refinement-advisor-v1"


class ModelProfileLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="model-profile-lifecycle-test-")
        self.root = Path(self.temporary.name) / "platform-engineering"
        shutil.copytree(REPO_ROOT / "security", self.root / "security")
        for name in ("docs", "dev-integration"):
            (self.root / name).symlink_to(REPO_ROOT / name, target_is_directory=True)
        self.work = Path(self.temporary.name) / "work"
        self.work.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Agent Gary"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "agent@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "security", "docs", "dev-integration"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "baseline source"], check=True)
        self.base_version = subprocess.check_output(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True
        ).strip()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def profile(self) -> dict:
        registry = yaml.safe_load(
            (self.root / lifecycle.REGISTRY).read_text(encoding="utf-8")
        )
        profile = copy.deepcopy(registry["model_profiles"][PROFILE_ID])
        profile["status"] = "suspended"
        for binding in profile["bindings"].values():
            if binding["status"] != "retired":
                binding["status"] = "selected-not-active"
        return profile

    def projection(self, *, state: str = "implementing", recorded_at: str = "2026-10-09T00:00:00Z") -> dict:
        source = lifecycle.source_state(self.root, source_version=self.base_version)
        profile = self.profile()
        request = {
            "schema_version": 1,
            "request_id": "model-profile-request:test-amend",
            "intent": "amend",
            "requested_at": "2026-10-08T23:58:00Z",
            "operator_id": "operator:workspace-owner",
            "profile_intent": {
                "profile_id": PROFILE_ID,
                "source": {
                    "registry_ref": {
                        "uri": "repo://platform-engineering/security/governed-ai-model-profiles.yaml",
                        "digest": source["registry_digest"],
                    },
                    "source_version": self.base_version,
                },
                "display_name": "Delivery Refinement Advisor",
                "intended_purpose": "Apply a reviewed lifecycle amendment.",
                "requesting_owner": "operator-orchestration-service",
                "registered_callers": [
                    {
                        "caller_id": "operator-orchestration-service/refinement-assist",
                        "owner_repo": "operator-orchestration-service",
                    }
                ],
                "requested_environments": ["dev-integration"],
                "input_data_classification": "internal",
                "admitted_context_ref": {
                    "uri": "cgg://packets/model-profile-test",
                    "digest": "sha256:" + "1" * 64,
                },
                "required_output_schema_ref": {
                    "repo": profile["provider_output_schema_ref"]["repo"],
                    "path": profile["provider_output_schema_ref"]["path"],
                    "version": "1.0",
                },
                "human_approval_required": True,
                "operational_expectations": ["Fail closed on stale source."],
                "operator_justification": "Exercise the governed lifecycle path.",
            },
            "delivery_ref": "openproject://work_packages/1241",
            "correlation_id": "delivery-1203",
            "causation_id": "work-item-1241",
            "idempotency_key": "test-amend-request",
        }
        receipt = {
            "schema_version": 1,
            "receipt_id": "model-profile-receipt:111111111111111111111111",
            "request_id": request["request_id"],
            "request_revision": 5,
            "intent": "amend",
            "review_state": "approved",
            "fulfillment_state": state,
            "profile_id": PROFILE_ID,
            "actor": {
                "caller_id": lifecycle.ACTOR_ID,
                "operator_id": None,
            },
            "routed_owners": {
                "workflow_owner": "operator-orchestration-service",
                "fulfillment_owner": "platform-engineering",
                "security_owner": "security-architecture",
            },
            "delivery_ref": request["delivery_ref"],
            "source_ref": request["profile_intent"]["source"]["registry_ref"],
            "prior_receipt_ref": None,
            "recorded_at": recorded_at,
            "digest": "sha256:" + "0" * 64,
        }
        receipt["digest"] = lifecycle.digest_value(receipt, "digest")
        event = {
            "sequence": 1,
            "event_type": "fulfillment-implementing",
            "occurred_at": recorded_at,
            "actor_id": lifecycle.ACTOR_ID,
            "command_id": "fulfill-implementing-test",
            "review_state_before": "approved",
            "review_state_after": "approved",
            "fulfillment_state_before": "not-started",
            "fulfillment_state_after": state,
            "summary": "Platform fulfillment started.",
            "receipt_ref": {
                "uri": f"oos://model-profile-receipts/{receipt['receipt_id']}",
                "digest": receipt["digest"],
            },
        }
        fulfillment = {
            "schema_version": 1,
            "fulfillment_id": "fulfillment-implementing-test",
            "request_id": request["request_id"],
            "expected_revision": 4,
            "state": state,
            "actor_id": lifecycle.ACTOR_ID,
            "recorded_at": recorded_at,
            "source": None,
            "receipt_ref": None,
            "failure": None,
            "idempotency_key": "fulfill-implementing-test",
        }
        return {
            "schema_version": 1,
            "workflow_id": "model-profile-request",
            "request_id": request["request_id"],
            "revision": 5,
            "request": request,
            "review_state": "approved",
            "fulfillment_state": state,
            "requirements": [],
            "decision_ref": {
                "uri": "openproject://work_packages/1241",
                "digest": "sha256:" + "2" * 64,
            },
            "fulfillment": fulfillment,
            "latest_receipt": receipt,
            "history": [event],
            "next_action": "await-platform-fulfillment",
            "profile_lifecycle_changed": False,
        }

    def decision(self, projection: dict) -> dict:
        return {
            "schema_version": 1,
            "decision_id": "platform-model-profile-decision:test-amend",
            "request_id": projection["request_id"],
            "request_revision": projection["revision"],
            "request_receipt_digest": projection["latest_receipt"]["digest"],
            "intent": "amend",
            "actor_id": lifecycle.ACTOR_ID,
            "recorded_at": "2026-10-09T00:01:00Z",
            "expected_sources": lifecycle.source_state(self.root, source_version=self.base_version),
            "profile_id": PROFILE_ID,
            "target_profile": self.profile(),
            "activation_environment": None,
            "security_decision_ref": None,
            "idempotency_key": "platform-test-amend",
        }

    def write(self, name: str, value: dict) -> Path:
        path = self.work / name
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return path

    def write_private(self, name: str, value: dict | str) -> Path:
        path = self.work / name
        content = value if isinstance(value, str) else json.dumps(value, indent=2) + "\n"
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)
        return path

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts/model_profile_lifecycle.py"),
                "--repo-root",
                str(self.root),
                "--oos-repo-root",
                str(OOS_ROOT),
                *arguments,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def apply(self, projection: dict | None = None, decision: dict | None = None):
        projection = projection or self.projection()
        decision = decision or self.decision(projection)
        request_path = self.write("request.json", projection)
        decision_path = self.write("decision.json", decision)
        receipt = self.work / "receipt.json"
        rollback = self.work / "rollback.json"
        completed = self.run_cli(
            "apply",
            "--request-projection", str(request_path),
            "--decision", str(decision_path),
            "--receipt", str(receipt),
            "--rollback-bundle", str(rollback),
        )
        return completed, receipt, rollback

    def test_apply_project_restore_and_cleanup_are_exact(self) -> None:
        before = lifecycle.source_state(self.root, source_version=self.base_version)
        completed, receipt_path, rollback_path = self.apply()
        self.assertEqual(0, completed.returncode, completed.stderr)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual("applied", receipt["outcome"])
        self.assertEqual("active", receipt["lifecycle_before"])
        self.assertEqual("suspended", receipt["lifecycle_after"])
        self.assertEqual(
            "pending-source-review", receipt["oos_fulfillment"]["state"]
        )
        registry = yaml.safe_load((self.root / lifecycle.REGISTRY).read_text())
        self.assertEqual("suspended", registry["model_profiles"][PROFILE_ID]["status"])
        projected_value = lifecycle.projection_for(self.root, "candidate-source")
        projection = projected_value
        selected = next(item for item in projection["profiles"] if item["profile_id"] == PROFILE_ID)
        self.assertEqual("suspended", selected["lifecycle"])
        self.assertFalse(selected["activation"]["activation_allowed"])

        restore = self.run_cli(
            "restore",
            "--receipt", str(receipt_path),
            "--rollback-bundle", str(rollback_path),
            "--recorded-at", "2026-10-09T00:02:00Z",
            "--output", str(self.work / "restore-receipt.json"),
        )
        self.assertEqual(0, restore.returncode, restore.stderr)
        self.assertEqual(before, lifecycle.source_state(self.root, source_version=self.base_version))

    def test_source_projection_requires_exact_clean_git_head(self) -> None:
        projected = self.run_cli("project", "--source-version", self.base_version)
        self.assertEqual(0, projected.returncode, projected.stderr)
        value = json.loads(projected.stdout)
        self.assertEqual(self.base_version, value["source"]["source_version"])
        wrong = self.run_cli("project", "--source-version", "f" * 40)
        self.assertNotEqual(0, wrong.returncode)
        self.assertIn("does not match Platform HEAD", wrong.stderr)
        registry = self.root / lifecycle.REGISTRY
        registry.write_text(registry.read_text() + "# dirty\n", encoding="utf-8")
        dirty = self.run_cli("project")
        self.assertNotEqual(0, dirty.returncode)
        self.assertIn("clean Platform git worktree", dirty.stderr)

    def test_protocol_denies_not_started_stale_false_and_replay_conflicts(self) -> None:
        not_started = self.projection(state="not-started")
        not_started["fulfillment"] = None
        not_started["latest_receipt"]["fulfillment_state"] = "not-started"
        not_started["latest_receipt"]["digest"] = lifecycle.digest_value(
            not_started["latest_receipt"], "digest"
        )
        not_started["history"][-1]["fulfillment_state_after"] = "not-started"
        not_started["history"][-1]["receipt_ref"]["digest"] = not_started["latest_receipt"]["digest"]
        not_started["next_action"] = "begin-platform-fulfillment"
        completed, _, _ = self.apply(not_started, self.decision(not_started))
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("must be implementing", completed.stderr)

        stale = self.projection()
        stale_decision = self.decision(stale)
        stale_decision["expected_sources"]["registry_digest"] = "sha256:" + "9" * 64
        completed, _, _ = self.apply(stale, stale_decision)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("source binding is stale", completed.stderr)

        false_receipt = self.projection()
        false_receipt["latest_receipt"]["digest"] = "sha256:" + "8" * 64
        false_receipt["history"][-1]["receipt_ref"]["digest"] = "sha256:" + "8" * 64
        completed, _, _ = self.apply(false_receipt, self.decision(false_receipt))
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("receipt digest is false", completed.stderr)

        valid = self.projection()
        completed, receipt, rollback = self.apply(valid, self.decision(valid))
        self.assertEqual(0, completed.returncode, completed.stderr)
        replay = self.run_cli(
            "apply",
            "--request-projection", str(self.work / "request.json"),
            "--decision", str(self.work / "decision.json"),
            "--receipt", str(receipt),
            "--rollback-bundle", str(rollback),
        )
        self.assertEqual(0, replay.returncode, replay.stderr)
        conflict = self.decision(valid)
        conflict["idempotency_key"] = "conflicting-replay"
        self.write("decision-conflict.json", conflict)
        rejected = self.run_cli(
            "apply",
            "--request-projection", str(self.work / "request.json"),
            "--decision", str(self.work / "decision-conflict.json"),
            "--receipt", str(receipt),
            "--rollback-bundle", str(rollback),
        )
        self.assertNotEqual(0, rejected.returncode)
        self.assertIn("idempotency conflict", rejected.stderr)

    def test_denies_unauthorized_out_of_order_and_unapproved_activation(self) -> None:
        projection = self.projection()
        malformed = copy.deepcopy(projection)
        malformed.pop("workflow_id")
        completed, _, _ = self.apply(malformed, self.decision(projection))
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("invalid OOS model-profile projection", completed.stderr)

        unauthorized = self.decision(projection)
        unauthorized["actor_id"] = "operator:workspace-owner"
        completed, _, _ = self.apply(projection, unauthorized)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("actor_id", completed.stderr)

        out_of_order = self.decision(projection)
        out_of_order["recorded_at"] = "2026-10-08T23:59:00Z"
        completed, _, _ = self.apply(projection, out_of_order)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("precedes", completed.stderr)

        unsafe = self.decision(projection)
        unsafe["target_profile"]["provider_secret_value"] = "must-not-enter-source"
        completed, _, _ = self.apply(projection, unsafe)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("prohibited secret-shaped", completed.stderr)

        activation_projection = self.projection()
        activation_projection["request"]["intent"] = "activate"
        activation_projection["latest_receipt"]["intent"] = "activate"
        activation_projection["latest_receipt"]["digest"] = lifecycle.digest_value(
            activation_projection["latest_receipt"], "digest"
        )
        activation_projection["history"][-1]["receipt_ref"]["digest"] = activation_projection["latest_receipt"]["digest"]
        activation = self.decision(activation_projection)
        activation["intent"] = "activate"
        activation["request_receipt_digest"] = activation_projection["latest_receipt"]["digest"]
        activation["target_profile"]["status"] = "active"
        for binding in activation["target_profile"]["bindings"].values():
            binding["status"] = "active"
        activation["activation_environment"] = "dev-integration"
        completed, _, _ = self.apply(activation_projection, activation)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("requires an exact Security decision", completed.stderr)

    def test_restore_denies_dirty_result(self) -> None:
        completed, receipt, rollback = self.apply()
        self.assertEqual(0, completed.returncode, completed.stderr)
        registry_path = self.root / lifecycle.REGISTRY
        registry_path.write_text(registry_path.read_text() + "# drift\n", encoding="utf-8")
        restore = self.run_cli(
            "restore",
            "--receipt", str(receipt),
            "--rollback-bundle", str(rollback),
            "--recorded-at", "2026-10-09T00:02:00Z",
            "--output", str(self.work / "restore-receipt.json"),
        )
        self.assertNotEqual(0, restore.returncode)
        self.assertIn("current source differs", restore.stderr)

    def test_merged_readback_emits_exact_oos_fulfillment(self) -> None:
        completed, receipt, _rollback = self.apply()
        self.assertEqual(0, completed.returncode, completed.stderr)
        subprocess.run(["git", "-C", str(self.root), "add", "security", "docs", "dev-integration"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "merged lifecycle source"], check=True)
        head = subprocess.check_output(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True
        ).strip()
        output = self.work / "readback.json"
        readback = self.run_cli(
            "readback",
            "--receipt", str(receipt),
            "--source-version", head,
            "--review-uri", "https://github.com/mfshaf7/platform-engineering/pull/999",
            "--review-digest", "sha256:" + "7" * 64,
            "--recorded-at", "2026-10-09T00:03:00Z",
            "--output", str(output),
        )
        self.assertEqual(0, readback.returncode, readback.stderr)
        value = json.loads(output.read_text(encoding="utf-8"))
        fulfillment = value["oos_fulfillment"]
        self.assertEqual("applied", fulfillment["state"])
        self.assertEqual(head, fulfillment["source"]["result_version"])
        self.assertEqual(lifecycle.ACTOR_ID, fulfillment["actor_id"])

    def test_operating_verifier_reads_live_oos_and_console_and_exact_cleanup(self) -> None:
        completed, receipt_path, rollback_path = self.apply()
        self.assertEqual(0, completed.returncode, completed.stderr)
        subprocess.run(["git", "-C", str(self.root), "add", "security"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "applied source"], check=True)
        applied_head = subprocess.check_output(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True
        ).strip()
        readback_path = self.work / "readback.json"
        readback = self.run_cli(
            "readback",
            "--receipt", str(receipt_path),
            "--source-version", applied_head,
            "--review-uri", "https://github.com/mfshaf7/platform-engineering/pull/999",
            "--review-digest", "sha256:" + "7" * 64,
            "--recorded-at", "2026-10-09T00:03:00Z",
            "--output", str(readback_path),
        )
        self.assertEqual(0, readback.returncode, readback.stderr)
        restore_path = self.work / "restore.json"
        restored = self.run_cli(
            "restore",
            "--receipt", str(receipt_path),
            "--rollback-bundle", str(rollback_path),
            "--recorded-at", "2026-10-09T00:04:00Z",
            "--output", str(restore_path),
        )
        self.assertEqual(0, restored.returncode, restored.stderr)
        subprocess.run(["git", "-C", str(self.root), "add", "security"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "cleanup proof source"], check=True)
        proof_head = subprocess.check_output(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True
        ).strip()

        initial = self.projection()
        readback_value = json.loads(readback_path.read_text(encoding="utf-8"))
        final_receipt = copy.deepcopy(initial["latest_receipt"])
        final_receipt.update(
            {
                "receipt_id": "model-profile-receipt:222222222222222222222222",
                "request_revision": 6,
                "fulfillment_state": "applied",
                "recorded_at": "2026-10-09T00:03:00Z",
                "source_ref": readback_value["oos_fulfillment"]["source"]["review_ref"],
                "prior_receipt_ref": initial["history"][-1]["receipt_ref"],
            }
        )
        final_receipt["digest"] = lifecycle.digest_value(final_receipt, "digest")
        oos_projection = copy.deepcopy(initial)
        oos_projection.update(
            {
                "revision": 6,
                "fulfillment_state": "applied",
                "fulfillment": readback_value["oos_fulfillment"],
                "latest_receipt": final_receipt,
                "next_action": "refresh-authoritative-projections",
            }
        )
        oos_projection["history"].append(
            {
                "sequence": 2,
                "event_type": "fulfillment-applied",
                "occurred_at": "2026-10-09T00:03:00Z",
                "actor_id": lifecycle.ACTOR_ID,
                "command_id": "platform-model-profile-fulfillment:test",
                "review_state_before": "approved",
                "review_state_after": "approved",
                "fulfillment_state_before": "implementing",
                "fulfillment_state_after": "applied",
                "summary": "Platform source applied and read back.",
                "receipt_ref": {
                    "uri": f"oos://model-profile-receipts/{final_receipt['receipt_id']}",
                    "digest": final_receipt["digest"],
                },
            }
        )
        platform_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        console_projection = {
            "workflow_id": "model-operations-live-projection",
            "projection_state": "current",
            "next_action": "complete",
            "console_mutation_authority": False,
            "oos_request_ref": {
                "request_id": oos_projection["request_id"],
                "revision": oos_projection["revision"],
                "receipt_digest": final_receipt["digest"],
            },
            "platform_source_ref": {
                "lifecycle_receipt_digest": platform_receipt["digest"],
                "merged_readback_digest": readback_value["digest"],
            },
        }
        secret_path = self.write_private("oos.secret", "operating-secret\n")

        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler_self):
                if handler_self.path == "/oos":
                    if (
                        handler_self.headers.get("x-oos-caller-id") != "governance-operations-console"
                        or handler_self.headers.get("x-oos-caller-secret") != "operating-secret"
                    ):
                        handler_self.send_response(403)
                        handler_self.end_headers()
                        return
                    value = oos_projection
                elif handler_self.path == "/console":
                    value = console_projection
                else:
                    handler_self.send_response(404)
                    handler_self.end_headers()
                    return
                content = json.dumps(value).encode()
                handler_self.send_response(200)
                handler_self.send_header("Content-Type", "application/json")
                handler_self.send_header("Content-Length", str(len(content)))
                handler_self.end_headers()
                handler_self.wfile.write(content)

            def log_message(self, _format, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            now = datetime.now(timezone.utc)
            proof = {
                "schema_version": 1,
                "artifact_type": "model-profile-lifecycle-operating-proof",
                "proof_scope": "disposable-dev-integration",
                "recorded_at": (now - timedelta(seconds=5)).isoformat().replace("+00:00", "Z"),
                "expires_at": (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
                "source_revisions": {
                    "platform-engineering": proof_head,
                    "operator-orchestration-service": proof_head,
                    "governance-operations-console": proof_head,
                    "security-architecture": proof_head,
                },
                "oos": {
                    "url": f"http://127.0.0.1:{server.server_port}/oos",
                    "expected_digest": lifecycle.digest_value(oos_projection),
                    "caller_id": "governance-operations-console",
                    "secret_file": str(secret_path),
                },
                "console": {
                    "url": f"http://127.0.0.1:{server.server_port}/console",
                    "expected_digest": lifecycle.digest_value(console_projection),
                },
                "platform_artifacts": {
                    "lifecycle_receipt": str(receipt_path),
                    "merged_readback": str(readback_path),
                    "restore_receipt": str(restore_path),
                },
                "negative_outcomes": {
                    "stale_authority_denied": True,
                    "unsafe_input_denied": True,
                    "failed_handoff_denied": True,
                    "false_receipt_denied": True,
                    "prohibited_maturity_denied": True,
                },
                "cleanup": {
                    "temporary_source_removed": True,
                    "temporary_runtime_stopped": True,
                    "operator_secrets_removed": True,
                },
                "secret_values_embedded": False,
            }
            proof_path = self.write_private("operating-proof.json", proof)
            env = os.environ.copy()
            env.update(
                {
                    "OOS_DELIVERY_ART_EVIDENCE_EXECUTION": "true",
                    "OOS_DELIVERY_ART_EVIDENCE_MODE": "verification-only",
                }
            )
            command = [
                "python3", str(REPO_ROOT / "scripts/model_profile_lifecycle.py"),
                "--repo-root", str(self.root),
                "--oos-repo-root", str(OOS_ROOT),
            ]
            for name in proof["source_revisions"]:
                command.extend(["--repo-path", f"{name}={self.root}"])
            command.extend(["verify-operating", "--evidence", str(proof_path)])
            verified = subprocess.run(command, text=True, capture_output=True, env=env, check=False)
            self.assertEqual(0, verified.returncode, verified.stderr)
            self.assertEqual("verified", json.loads(verified.stdout)["outcome"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
