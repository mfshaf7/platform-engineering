#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("platform_operation_provider.py")
SPEC = importlib.util.spec_from_file_location("platform_operation_provider", SCRIPT)
assert SPEC and SPEC.loader
provider = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provider)


SOURCE = "a" * 40


def accepted_policy(root: Path) -> dict:
    value = provider.load_policy()
    value["workspace_root"] = str(root)
    value["runtime_state_root"] = str(root / "runtime")
    value["security"].update({
        "status": "accepted",
        "decision_uri": "security-architecture://decisions/platform-operation-v1",
        "decision_digest": "sha256:" + "b" * 64,
        "platform_revision": SOURCE,
        "platform_tree": provider.git_tree(),
    })
    return value


def command(policy: dict, *, action: str = "dev-integration.status", input_value: dict | None = None) -> dict:
    profile = policy["platform_operation_provider"]["profile_id"]
    value = {
        "schema_version": 1,
        "command_id": f"command:{profile}:{action.rsplit('.', 1)[1]}:1",
        "idempotency_key": f"idempotency:{profile}:{action.rsplit('.', 1)[1]}:1",
        "correlation_id": f"correlation:{profile}:1",
        "causation_id": None,
        "actor_ref": "operator:workspace-owner",
        "subject": {
            "kind": "dev-integration-profile",
            "ref": f"profile:{profile}",
            "expected_source_version": SOURCE,
        },
        "capability_id": f"dev-integration.{profile}.{action.rsplit('.', 1)[1]}",
        "action": action,
        "input": input_value if input_value is not None else {},
        "requested_at": "2026-10-15T00:00:00Z",
    }
    value["intent_digest"] = provider.canonical_digest(provider.command_intent(value))
    value["approval"] = {
        "decision": "approved",
        "operator_id": "operator:workspace-owner",
        "decision_ref": "approval:platform-operation:1",
        "decided_at": "2026-10-15T00:00:01Z",
        "intent_digest": value["intent_digest"],
    }
    return value


class PlatformOperationProviderTests(unittest.TestCase):
    def test_case_1291_positive_catalog_is_exact_and_finite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = accepted_policy(Path(temp_dir))
            catalog = provider.capability_catalog(policy, SOURCE, activated=True)
        self.assertEqual(catalog["freshness"], "current")
        self.assertEqual(catalog["subjects"][0]["ref"], "profile:accepted-idea-delivery")
        actions = {item["action"] for item in catalog["subjects"][0]["capabilities"]}
        self.assertEqual(actions, provider.ALLOWED_ACTIONS)
        self.assertTrue(all(item["approval_required"] for item in catalog["subjects"][0]["capabilities"]))
        self.assertEqual(
            [item["action"] for item in catalog["subjects"][0]["capabilities"] if item["destructive"]],
            ["dev-integration.stop"],
        )

    def test_case_1291_negative_pending_or_stale_security_blocks_provider(self) -> None:
        policy = provider.load_policy()
        with self.assertRaisesRegex(provider.ProviderError, "not accepted"):
            provider.require_security_activation(policy, SOURCE)
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = accepted_policy(Path(temp_dir))
            policy["security"]["platform_tree"] = "c" * 40
            with self.assertRaisesRegex(provider.ProviderError, "not the Security-accepted"):
                provider.ProviderService(
                    policy,
                    Path("policy.yaml"),
                    provider.OperationStore(Path(temp_dir) / "state"),
                    SOURCE,
                )

    def test_command_rejects_stale_source_extra_input_and_wrong_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = accepted_policy(Path(temp_dir))
            stale = command(policy)
            stale["subject"]["expected_source_version"] = "d" * 40
            stale["intent_digest"] = provider.canonical_digest(provider.command_intent(stale))
            stale["approval"]["intent_digest"] = stale["intent_digest"]
            with self.assertRaisesRegex(provider.ProviderError, "stale or invalid"):
                provider.validate_command(stale, policy, SOURCE)
            with self.assertRaisesRegex(provider.ProviderError, "no caller-selected input"):
                provider.validate_command(command(policy, input_value={"shell": "id"}), policy, SOURCE)
            invalid = command(policy)
            invalid["approval"]["operator_id"] = "operator:other"
            with self.assertRaisesRegex(provider.ProviderError, "exact operator approval"):
                provider.validate_command(invalid, policy, SOURCE)

    def test_submit_replays_exact_command_and_rejects_conflicting_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy = accepted_policy(root)
            policy_path = root / "policy.yaml"
            policy_path.write_text("schema_version: 1\n", encoding="utf-8")
            service = provider.ProviderService(
                policy,
                policy_path,
                provider.OperationStore(root / "state"),
                SOURCE,
            )
            exact = command(policy)
            with patch.object(provider, "spawn_worker"):
                first_status, first = service.submit({"command": exact})
                replay_status, replay = service.submit({"command": exact})
                conflict = json.loads(json.dumps(exact))
                conflict["requested_at"] = "2026-10-15T00:00:02Z"
                conflict["intent_digest"] = provider.canonical_digest(provider.command_intent(conflict))
                conflict["approval"]["intent_digest"] = conflict["intent_digest"]
                with self.assertRaisesRegex(provider.ProviderError, "another intent"):
                    service.submit({"command": conflict})
            self.assertEqual(first_status, 202)
            self.assertEqual(replay_status, 200)
            self.assertEqual(first["operation_id"], replay["operation_id"])

    def test_worker_records_truthful_success_and_failure_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy = accepted_policy(root)
            store = provider.OperationStore(root / "state")
            for index, return_code in enumerate((0, 7), start=1):
                exact = command(policy)
                exact["command_id"] = f"command:accepted-idea-delivery:status:{index}"
                exact["idempotency_key"] = f"idempotency:accepted-idea-delivery:status:{index}"
                exact["intent_digest"] = provider.canonical_digest(provider.command_intent(exact))
                exact["approval"]["intent_digest"] = exact["intent_digest"]
                record = provider.new_record(exact, SOURCE)
                store.write(record)
                completed = provider.subprocess.CompletedProcess([], return_code)
                with patch.object(provider.subprocess, "run", return_value=completed):
                    provider.execute_worker(store, policy, exact["command_id"])
                result = store.read(exact["command_id"])
                assert result
                expected = "succeeded" if return_code == 0 else "failed"
                self.assertEqual(result["state"], expected)
                self.assertEqual(result["receipt"]["outcome"], expected)
                self.assertEqual(result["receipt"]["effect"], "verified" if return_code == 0 else "none")

    def test_runner_mapping_has_no_caller_selected_command_or_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = accepted_policy(Path(temp_dir))
            start = provider.runner_command("dev-integration.start", policy)
            smoke = provider.runner_command("dev-integration.smoke", policy)
        self.assertIn("refinement-catalog", start)
        self.assertIn("accepted-idea-delivery", smoke)
        self.assertNotIn("shell", " ".join(start + smoke))

    def test_control_contract_rejects_wrong_operator_and_extra_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy = accepted_policy(root)
            store = provider.OperationStore(root / "state")
            service = provider.ProviderService(policy, root / "policy.yaml", store, SOURCE)
            exact = command(policy)
            record = provider.new_record(exact, SOURCE)
            record["state"] = "failed"
            record["retryable"] = True
            record["cancel_available"] = False
            record["failure"] = {"code": "failed", "detail": "failed", "owner": "platform-engineering"}
            record["receipt"] = provider.terminal_receipt(record, "failed", "none")
            provider.event(record, "failed", "failed")
            store.write(record)
            control = {
                "schema_version": 1,
                "control_id": "control:retry:1",
                "idempotency_key": "idempotency:retry:1",
                "action": "retry",
                "operator_id": "operator:other",
                "reason": "Retry after recovery.",
                "requested_at": "2026-10-15T00:00:00Z",
            }
            with self.assertRaisesRegex(provider.ProviderError, "binding is invalid"):
                service.control(record["operation_id"], {"control": control})
            control["operator_id"] = "operator:workspace-owner"
            control["extra"] = True
            with self.assertRaisesRegex(provider.ProviderError, "control is invalid"):
                service.control(record["operation_id"], {"control": control})

    def test_lost_worker_blocks_and_retries_without_killing_reused_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy = accepted_policy(root)
            store = provider.OperationStore(root / "state")
            service = provider.ProviderService(policy, root / "policy.yaml", store, SOURCE)
            exact = command(policy)
            record = provider.new_record(exact, SOURCE)
            record["worker"] = {
                "pid": 999999,
                "boot_id": "lost",
                "start_ticks": 1,
                "started_at": "2026-10-15T00:00:00Z",
            }
            provider.event(record, "running", "running")
            store.write(record)
            blocked = service.read(exact["command_id"])
            self.assertEqual(blocked["state"], "blocked")
            self.assertTrue(blocked["retryable"])
            self.assertEqual(blocked["blocker"]["code"], "platform_owner_worker_lost")
            control = {
                "schema_version": 1,
                "control_id": "control:retry:lost:1",
                "idempotency_key": "idempotency:retry:lost:1",
                "action": "retry",
                "operator_id": "operator:workspace-owner",
                "reason": "Retry after exact worker loss.",
                "requested_at": "2026-10-15T00:00:00Z",
            }
            with patch.object(provider, "spawn_worker"):
                retried = service.control(record["operation_id"], {"control": control})
            self.assertEqual(retried["state"], "queued")
            self.assertEqual(retried["attempt"], 2)

    def test_stale_activation_marker_withholds_effect_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy = accepted_policy(root)
            marker = Path(policy["runtime_state_root"]) / "active.json"
            marker.parent.mkdir(parents=True)
            marker.write_text(json.dumps({
                "schema_version": 1,
                "platform_revision": SOURCE,
                "platform_tree": provider.git_tree(),
                "security_decision_digest": "sha256:" + "0" * 64,
                "security_decision_uri": policy["security"]["decision_uri"],
                "activated_at": "2026-10-15T00:00:00Z",
            }), encoding="utf-8")
            service = provider.ProviderService(policy, root / "policy.yaml", provider.OperationStore(root / "state"), SOURCE)
            catalog = service.catalog()
            capabilities = {item["action"]: item for item in catalog["subjects"][0]["capabilities"]}
            self.assertTrue(capabilities["dev-integration.status"]["available"])
            self.assertFalse(capabilities["dev-integration.smoke"]["available"])


if __name__ == "__main__":
    unittest.main()
